import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, SessionParticipant, User
from ..schemas import (
    ActivityCreate,
    ActivityOut,
    ActivityPatch,
    TogetherOut,
    TogetherPartnerBrief,
)
from ..models import utcnow
from ..services import activity_delete, feed, together
from ..services.achievements import check_unlocks
from ..services.factors import FactorResolver
from ..services.season_window import in_window, window_bounds

router = APIRouter(prefix="/api/activities", tags=["activities"])

log = logging.getLogger(__name__)


def _validate_category(session: Session, category_id: int) -> Category:
    cat = session.get(Category, category_id)
    if cat is None or not cat.is_active:
        raise HTTPException(status_code=422, detail="Kategorie unbekannt oder inaktiv")
    return cat


def _together_map(
    session: Session, activities: list[Activity], *, own: bool = True
) -> dict[int, TogetherOut]:
    """Together-Badge-Daten (Spec 4.3); ein Fehler wird nur geloggt — die
    Liste bricht nie, sie kommt dann ohne Badges."""
    try:
        return _build_together_map(session, activities, own=own)
    except Exception:
        log.exception("together: Badge-Daten fehlgeschlagen")
        return {}


def _build_together_map(
    session: Session, activities: list[Activity], *, own: bool
) -> dict[int, TogetherOut]:
    """Badge-Daten für mehrere Aktivitäten in wenigen Abfragen (kein N+1 je
    Aktivität): nur, wenn das Add-on aktiv ist und die Teilnahme des
    Besitzers nicht `declined` ist; `partners` = andere `confirmed`.
    Eigene Listen (`own`): `confirmed`/`suggested`, aber nur, solange noch
    ein anderer nicht abgelehnter Teilnehmer da ist. Fremde Profile: nur
    `confirmed` in echten Sessions (≥ 2 bestätigt)."""
    ids = [a.id for a in activities if a.id is not None]
    if not ids or not together.enabled(session):
        return {}
    mine = {
        p.activity_id: p
        for p in session.exec(
            select(SessionParticipant).where(SessionParticipant.activity_id.in_(ids))
        ).all()
        if p.status != "declined"
    }
    if not mine:
        return {}
    session_ids = {p.session_id for p in mine.values()}
    all_parts = session.exec(
        select(SessionParticipant).where(SessionParticipant.session_id.in_(session_ids))
    ).all()
    by_session: dict[int, list[SessionParticipant]] = {}
    for p in all_parts:
        by_session.setdefault(p.session_id, []).append(p)
    user_ids = {p.user_id for p in all_parts if p.status == "confirmed"}
    users = (
        {u.id: u for u in session.exec(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )
    result: dict[int, TogetherOut] = {}
    for activity_id, p in mine.items():
        members = by_session.get(p.session_id, [])
        if own:
            if not any(o.id != p.id and o.status != "declined" for o in members):
                continue
        elif p.status != "confirmed" or sum(
            o.status == "confirmed" for o in members
        ) < 2:
            continue
        partners = [
            TogetherPartnerBrief(user_id=o.user_id, display_name=users[o.user_id].display_name)
            for o in members
            if o.status == "confirmed" and o.user_id != p.user_id and o.user_id in users
        ]
        result[activity_id] = TogetherOut(
            session_id=p.session_id,
            participant_id=p.id,
            status=p.status,
            partners=partners,
            km_together=p.km_together,
        )
    return result


def _to_out(
    activity: Activity, resolver: FactorResolver, together_out: TogetherOut | None = None
) -> ActivityOut:
    # The factor depends on the activity date (cutover changes), never on the
    # category's stored base factor alone.
    strava_url = (
        f"https://www.strava.com/activities/{activity.external_id}"
        if activity.source == "strava" and activity.external_id
        else None
    )
    return ActivityOut(
        id=activity.id,
        category_id=activity.category_id,
        date=activity.date,
        distance_km=activity.distance_km,
        duration_min=activity.duration_min,
        start_time=activity.start_time,
        elevation_m=activity.elevation_m,
        note=activity.note,
        scaled_km=round(resolver.mm(activity), 2),
        edited=activity.updated_at is not None,
        source=activity.source,
        strava_url=strava_url,
        together=together_out,
    )


def _together_safely(session: Session, act: Activity, fn, *args) -> None:
    """Together-Schritt nach dem Speichern der Aktivität: ein Fehler wird
    geloggt und zurückgerollt, die Aktivität bleibt gespeichert (kein 500).
    HTTPExceptions laufen weiter — `check_partners` hat vor dem Speichern
    geprüft, sie kommen hier nicht mehr vor."""
    try:
        fn(*args)
    except HTTPException:
        raise
    except Exception:
        log.exception("together: Nachverarbeitung für activity_id=%s fehlgeschlagen", act.id)
        session.rollback()


def _tag_safely(session: Session, act: Activity, partner_ids: list[int]) -> None:
    _together_safely(session, act, together.tag_partners, session, act, partner_ids)


def _own_activity(session: Session, user: User, activity_id: int) -> Activity:
    act = session.get(Activity, activity_id)
    if act is None or act.user_id != user.id:
        raise HTTPException(status_code=404)
    return act


@router.get("", response_model=list[ActivityOut])
def list_my_activities(
    year: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    acts = session.exec(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.date.desc(), Activity.id.desc())
    ).all()
    window = window_bounds(session, year)
    visible = [a for a in acts if in_window(a.date, window)]
    resolver = FactorResolver.load(session)
    together_map = _together_map(session, visible)
    return [_to_out(a, resolver, together_map.get(a.id)) for a in visible]


@router.post("", response_model=ActivityOut, status_code=201)
def create_activity(
    data: ActivityCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _validate_category(session, data.category_id)
    # Partner vor dem Anlegen prüfen — bei 400/404 entsteht keine Aktivität.
    together.check_partners(session, user.id, data.partner_ids)
    order_before = feed.challenge_order(session)
    total_before = feed.challenge_total(session, user.id)
    act = Activity(user_id=user.id, **data.model_dump(exclude={"partner_ids"}))
    session.add(act)
    session.commit()
    session.refresh(act)
    check_unlocks(session, user.id)
    feed.activity_event(session, act)
    feed.milestone_events(session, user.id, total_before, feed.challenge_total(session, user.id))
    feed.rank_events(session, order_before, feed.challenge_order(session))
    if data.partner_ids:
        _tag_safely(session, act, data.partner_ids)
    resolver = FactorResolver.load(session)
    return _to_out(act, resolver, _together_map(session, [act]).get(act.id))


@router.patch("/{activity_id}", response_model=ActivityOut)
def patch_activity(
    activity_id: int,
    data: ActivityPatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    act = _own_activity(session, user, activity_id)
    order_before = feed.challenge_order(session)
    total_before = feed.challenge_total(session, user.id)
    changes = {
        key: value
        for key, value in data.model_dump(exclude_unset=True, exclude={"partner_ids"}).items()
        if value is not None
        or key in ("note", "duration_min", "start_time", "elevation_m")
    }
    if "category_id" in changes:
        _validate_category(session, changes["category_id"])
    together.check_partners(session, user.id, data.partner_ids, act)
    for key, value in changes.items():
        setattr(act, key, value)
    if changes:  # nur Partner taggen ist keine Bearbeitung (Strava-Sync bleibt aktiv)
        act.updated_at = utcnow()
    session.add(act)
    session.commit()
    session.refresh(act)
    check_unlocks(session, user.id)
    # Kein neues activity-Event beim Bearbeiten — Spec B5.
    feed.milestone_events(session, user.id, total_before, feed.challenge_total(session, user.id))
    feed.rank_events(session, order_before, feed.challenge_order(session))
    if changes.keys() & {"distance_km", "category_id", "date"}:
        _together_safely(session, act, together.activity_changed, session, act)
    if data.partner_ids is not None:
        _tag_safely(session, act, data.partner_ids)
    resolver = FactorResolver.load(session)
    return _to_out(act, resolver, _together_map(session, [act]).get(act.id))


@router.delete("/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    act = _own_activity(session, user, activity_id)
    order_before = feed.challenge_order(session)
    activity_delete.delete_activity(session, act, ignore_strava=True)
    feed.rank_events(session, order_before, feed.challenge_order(session))
