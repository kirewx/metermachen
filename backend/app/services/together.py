"""Together-Matching (Spec 2026-10-05 Teil 1, 2.1): erkennt, dass Strava-
Aktivitäten verschiedener Mitglieder gemeinsam absolviert wurden, und führt
sie in `TrainingSession`s zusammen; Lebenszyklus (Spec 2.2–2.7: Bestätigen,
Ablehnen, Ablauf, Löschen) und Feed-Event `together` (Spec 3.1)."""

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from ..deps import addon_active
from ..models import (
    Activity,
    ActivityTrack,
    AddOn,
    SessionParticipant,
    TrainingSession,
    User,
)
from . import feed
from .notify import notify
from .together_geo import decode_polyline, route_overlap, times_overlap

AUTO_SHARE = 0.5
SUGGEST_SHARE = 0.3
MIN_KM = 2.0
SUGGESTION_DAYS = 14

ADDON_KEY = "together"

log = logging.getLogger(__name__)


def enabled(session: Session) -> bool:
    """True, wenn das Add-on `together` existiert und gerade aktiv ist."""
    addon = session.exec(select(AddOn).where(AddOn.key == ADDON_KEY)).first()
    return addon is not None and addon_active(addon, datetime.now(timezone.utc))


def participation_for(session: Session, activity_id: int) -> SessionParticipant | None:
    return session.exec(
        select(SessionParticipant).where(SessionParticipant.activity_id == activity_id)
    ).first()


def _classify(km: float, share: float) -> str | None:
    if share >= AUTO_SHARE and km >= MIN_KM:
        return "auto"
    if share >= SUGGEST_SHARE or km >= MIN_KM:
        return "suggest"
    return None


def _decode(polyline: str | None) -> list[tuple[float, float]] | None:
    if not polyline:
        return None
    try:
        points = decode_polyline(polyline)
    except ValueError:
        return None
    return points if len(points) >= 2 else None


def _candidates(session: Session, act: Activity, track: ActivityTrack):
    """(Track, Activity) anderer aktiver Nutzer mit detect_together, deren
    Zeitfenster sich mit `track` überlappt."""
    window = timedelta(days=1)
    rows = session.exec(
        select(ActivityTrack, Activity)
        .join(Activity, Activity.id == ActivityTrack.activity_id)
        .join(User, User.id == Activity.user_id)
        .where(
            Activity.user_id != act.user_id,
            User.is_active,
            User.detect_together,
            ActivityTrack.polyline.is_not(None),
            ActivityTrack.start_utc >= track.start_utc - window,
            ActivityTrack.start_utc <= track.start_utc + window,
        )
        .order_by(ActivityTrack.start_utc, ActivityTrack.id)
    ).all()
    return [
        (t, a) for t, a in rows
        if times_overlap(track.start_utc, track.elapsed_s, t.start_utc, t.elapsed_s)
    ]


def _pair_blocked(pa: SessionParticipant | None, pb: SessionParticipant | None) -> bool:
    """Schon in derselben Session, oder eine Seite hat ihre Teilnahme
    abgelehnt (Spec 2.3) — eine abgelehnte Aktivität zieht keine neuen
    Partner in ihre Session und löst keine Zusammenführung aus."""
    if any(p is not None and p.status == "declined" for p in (pa, pb)):
        return True
    return pa is not None and pb is not None and pa.session_id == pb.session_id


def _naive_utc(ts: datetime) -> datetime:
    """Frisch angelegte Objekte tragen eine zeitzonen-bewusste Zeit, aus
    SQLite geladene eine naive (UTC) — für Vergleiche vereinheitlichen."""
    return ts.astimezone(timezone.utc).replace(tzinfo=None) if ts.tzinfo else ts


def _age_key(obj) -> tuple[datetime, int]:
    """Sortierschlüssel (created_at naiv UTC, id)."""
    return _naive_utc(obj.created_at), obj.id


def _merge(session: Session, keep: TrainingSession, drop: TrainingSession) -> None:
    """Teilnahmen von `drop` nach `keep` umhängen und `drop` löschen. Hat der
    Nutzer in beiden Sessions eine Teilnahme, wird die jüngere verworfen."""
    in_keep = {
        p.user_id: p for p in session.exec(
            select(SessionParticipant).where(SessionParticipant.session_id == keep.id)
        ).all()
    }
    moving = []
    for p in session.exec(
        select(SessionParticipant).where(SessionParticipant.session_id == drop.id)
    ).all():
        other = in_keep.get(p.user_id)
        if other is not None and _age_key(other) <= _age_key(p):
            session.delete(p)
            continue
        if other is not None:
            session.delete(other)
        moving.append(p)
    session.flush()  # Löschungen vor dem Umhängen (unique session_id, user_id)
    for p in moving:
        p.session_id = keep.id
        session.add(p)
    session.flush()
    feed.remove_together_event(session, drop)
    session.delete(drop)
    session.flush()


def _choose_session(
    session: Session, pa: SessionParticipant | None, pb: SessionParticipant | None
) -> tuple[TrainingSession, int | None]:
    """Ziel-Session für das Paar und ggf. die id der darin aufgegangenen."""
    if pa is not None and pb is not None:
        sa = session.get(TrainingSession, pa.session_id)
        sb = session.get(TrainingSession, pb.session_id)
        keep, drop = sorted((sa, sb), key=_age_key)
        drop_id = drop.id
        _merge(session, keep, drop)
        return keep, drop_id
    if pb is not None:
        return session.get(TrainingSession, pb.session_id), None
    if pa is not None:
        return session.get(TrainingSession, pa.session_id), None
    ts = TrainingSession(source="auto")
    session.add(ts)
    session.flush()
    return ts, None


def _join(
    session: Session, ts: TrainingSession, act: Activity, status: str, km: float
) -> SessionParticipant | None:
    """Teilnahme für `act` in `ts` anlegen oder aktualisieren (nie herabstufen).
    Gibt die Teilnahme zurück, wenn sie neu angelegt wurde."""
    p = participation_for(session, act.id)
    if p is None:
        p = session.exec(
            select(SessionParticipant).where(
                SessionParticipant.session_id == ts.id,
                SessionParticipant.user_id == act.user_id,
            )
        ).first()
    if p is None:
        p = SessionParticipant(
            session_id=ts.id, user_id=act.user_id, activity_id=act.id,
            status=status, km_together=km,
        )
        session.add(p)
        session.flush()
        return p
    if p.activity_id is None:  # getaggt, jetzt per Auto-Match verknüpft
        p.activity_id = act.id
    if p.status == "suggested" and status == "confirmed":
        # Session-Werte stammen nur aus bestätigten Paaren (Spec 1.6)
        p.status = "confirmed"
        p.km_together = km
    elif p.status == status:
        p.km_together = max(p.km_together, km)
    session.add(p)
    session.flush()
    return None


def match_activity(session: Session, act: Activity, *, emit_feed: bool = True) -> None:
    """Sucht gemeinsame Aktivitäten zu `act` und legt/erweitert Sessions."""
    if not enabled(session):
        return
    user = session.get(User, act.user_id)
    if user is None or not user.is_active or not user.detect_together:
        return
    track = session.exec(
        select(ActivityTrack).where(ActivityTrack.activity_id == act.id)
    ).first()
    if track is None:
        return
    points_a = _decode(track.polyline)
    if points_a is None:
        return

    touched: dict[int, TrainingSession] = {}
    was_real: dict[int, bool] = {}  # Stand vor diesem Lauf je Session
    pending: list[tuple[int, str, dict]] = []
    for track_b, act_b in _candidates(session, act, track):
        pa, pb = participation_for(session, act.id), participation_for(session, act_b.id)
        if _pair_blocked(pa, pb):
            continue
        for p in (pa, pb):
            if p is not None and p.session_id not in was_real:
                was_real[p.session_id] = is_real(
                    session, session.get(TrainingSession, p.session_id)
                )
        points_b = _decode(track_b.polyline)
        if points_b is None:
            continue
        km, share = route_overlap(points_a, points_b, act.distance_km, act_b.distance_km)
        result = _classify(km, share)
        if result is None:
            continue

        ts, dropped = _choose_session(session, pa, pb)
        if dropped is not None:
            touched.pop(dropped, None)
            for _, _, payload in pending:
                if payload["session_id"] == dropped:
                    payload["session_id"] = ts.id
        touched[ts.id] = ts
        was_real.setdefault(ts.id, False)  # in diesem Lauf neu angelegt
        status = "confirmed" if result == "auto" else "suggested"
        kind = "together_auto" if result == "auto" else "together_suggested"
        for a in (act, act_b):
            new = _join(session, ts, a, status, km)
            if new is not None:
                pending.append((a.user_id, kind, {
                    "session_id": ts.id, "activity_id": a.id, "km_together": km,
                }))

    for ts in touched.values():
        refresh_session(
            session, ts, emit_feed=emit_feed, was_real=was_real.get(ts.id, False)
        )
    session.commit()
    for user_id, kind, payload in pending:
        notify(user_id, kind, payload)
    _check_achievements(session, touched.values())


def _confirmed(session: Session, ts: TrainingSession) -> list[SessionParticipant]:
    return list(session.exec(
        select(SessionParticipant).where(
            SessionParticipant.session_id == ts.id,
            SessionParticipant.status == "confirmed",
        )
    ).all())


def is_real(session: Session, ts: TrainingSession) -> bool:
    """Echt = mindestens zwei bestätigte Teilnahmen (Spec 2.1)."""
    return len(_confirmed(session, ts)) >= 2


def _now() -> datetime:
    """Jetzt als naive UTC-Zeit (so liest SQLite die Zeitstempel zurück)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check_achievements(session: Session, sessions: Iterable[TrainingSession]) -> None:
    """Nach dem Commit: Achievements aller bestätigten Teilnehmer echter
    Sessions prüfen (idempotent). Fehler brechen weder Matching noch
    Löschen ab."""
    from . import achievements  # function-level: achievements kennt bald together

    user_ids: list[int] = []
    for ts in sessions:
        confirmed = _confirmed(session, ts)
        if len(confirmed) >= 2:
            user_ids += [p.user_id for p in confirmed if p.user_id not in user_ids]
    for uid in user_ids:
        try:
            achievements.check_unlocks(session, uid)
        except Exception:
            log.exception("together: check_unlocks für Nutzer %s fehlgeschlagen", uid)
            session.rollback()


def _respond(
    session: Session, participant: SessionParticipant, status: str,
    was_real: bool | None = None,
) -> None:
    """`was_real` = Stand vor der Änderung, falls der Aufrufer vorher schon
    mutiert hat; sonst wird er hier ermittelt."""
    ts = session.get(TrainingSession, participant.session_id)
    if was_real is None:
        was_real = ts is not None and is_real(session, ts)
    participant.status = status
    participant.responded_at = _now()
    session.add(participant)
    session.flush()
    if ts is not None:
        refresh_session(session, ts, was_real=was_real)
    session.commit()
    if ts is not None:
        _check_achievements(session, [ts])


def _reference(
    session: Session, participant: SessionParticipant
) -> tuple[SessionParticipant, Activity] | None:
    """Älteste bestätigte Teilnahme (mit Aktivität) der Session außer der
    eigenen — Bezug für Datum (±1 Tag) und Distanz beim Verknüpfen."""
    others = sorted(
        (p for p in session.exec(
            select(SessionParticipant).where(
                SessionParticipant.session_id == participant.session_id,
                SessionParticipant.status == "confirmed",
                SessionParticipant.activity_id.is_not(None),
                SessionParticipant.user_id != participant.user_id,
            )
        ).all()),
        key=_age_key,
    )
    for p in others:
        act = session.get(Activity, p.activity_id)
        if act is not None:
            return p, act
    return None


def link_candidates(session: Session, participant: SessionParticipant) -> list[Activity]:
    """Eigene Aktivitäten ±1 Tag zum Bezugsdatum, die in keiner Session sind
    (Spec 2.5)."""
    ref = _reference(session, participant)
    if ref is None:
        return []
    day = ref[1].date
    linked = select(SessionParticipant.activity_id).where(
        SessionParticipant.activity_id.is_not(None)
    )
    return list(session.exec(
        select(Activity).where(
            Activity.user_id == participant.user_id,
            Activity.date >= day - timedelta(days=1),
            Activity.date <= day + timedelta(days=1),
            Activity.id.not_in(linked),
        ).order_by(Activity.date, Activity.id)
    ).all())


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def confirm(
    session: Session, participant: SessionParticipant, activity_id: int | None = None
) -> None:
    """Eigene Teilnahme bestätigen. Eine Teilnahme ohne Aktivität (Tag) braucht
    eine `activity_id`: eigene Aktivität, ±1 Tag zur ältesten bestätigten
    Aktivität der Session, in keiner anderen Session. `km_together` = kürzere
    der beiden Distanzen (Spec 2.5)."""
    if participant.activity_id is not None:
        if activity_id is not None and activity_id != participant.activity_id:
            raise _bad("Teilnahme ist bereits mit einer Aktivität verknüpft")
        _respond(session, participant, "confirmed")
        return
    if activity_id is None:
        raise _bad("Bitte eine eigene Aktivität wählen")
    act = session.get(Activity, activity_id)
    if act is None or act.user_id != participant.user_id:
        raise _bad("Aktivität unbekannt")
    if participation_for(session, act.id) is not None:
        raise _bad("Aktivität gehört schon zu einer gemeinsamen Session")
    ref = _reference(session, participant)
    if ref is not None and abs((act.date - ref[1].date).days) > 1:
        raise _bad("Aktivität liegt nicht am selben Tag (±1)")

    ts = session.get(TrainingSession, participant.session_id)
    was = ts is not None and is_real(session, ts)
    km = min(act.distance_km, ref[1].distance_km) if ref is not None else 0.0
    participant.activity_id = act.id
    participant.km_together = km
    if ref is not None:
        ref[0].km_together = max(ref[0].km_together, km)
        session.add(ref[0])
    _respond(session, participant, "confirmed", was_real=was)


def check_partners(session: Session, user_id: int, partner_ids: list[int] | None) -> None:
    """Partnerliste prüfen, ohne etwas zu ändern: 404 bei Add-on aus, 400 bei
    eigenem, unbekanntem, inaktivem oder Opt-out-Nutzer. Leer → nichts."""
    if not partner_ids:
        return
    if not enabled(session):
        raise HTTPException(status_code=404)
    for pid in set(partner_ids):
        u = session.get(User, pid)
        if pid == user_id or u is None or not u.is_active or not u.detect_together:
            raise _bad("Dieses Mitglied kann nicht getaggt werden")


def tag_partners(session: Session, act: Activity, partner_ids: list[int]) -> None:
    """Partner für `act` setzen (Spec 2.5). Neue Partner → `suggested` ohne
    Aktivität + `notify("together_tagged")`; aus der Liste entfernte, noch
    unverknüpfte Vorschläge werden gelöscht, bestätigte bleiben. Ohne Session
    entsteht eine `manual`-Session; bleibt sie ohne Partner, wird sie
    aufgelöst."""
    check_partners(session, act.user_id, partner_ids)
    wanted = set(partner_ids or [])
    own = participation_for(session, act.id)
    if own is None:
        if not wanted:
            return
        ts = TrainingSession(source="manual")
        session.add(ts)
        session.flush()
        own = SessionParticipant(
            session_id=ts.id, user_id=act.user_id, activity_id=act.id,
            status="confirmed", km_together=0.0, responded_at=_now(),
        )
        session.add(own)
        session.flush()
        was = False
    else:
        ts = session.get(TrainingSession, own.session_id)
        was = is_real(session, ts)
    if own.status == "declined" and wanted:
        raise _bad("Eigene Teilnahme ist abgelehnt")

    existing = {
        p.user_id: p for p in session.exec(
            select(SessionParticipant).where(SessionParticipant.session_id == ts.id)
        ).all()
    }
    pending: list[tuple[int, str, dict]] = []
    for uid in sorted(wanted - set(existing)):
        session.add(SessionParticipant(
            session_id=ts.id, user_id=uid, status="suggested", km_together=0.0,
        ))
        pending.append((uid, "together_tagged", {
            "session_id": ts.id, "activity_id": act.id, "by_user_id": act.user_id,
        }))
    for uid, p in existing.items():
        if uid not in wanted and p.status == "suggested" and p.activity_id is None:
            session.delete(p)
    session.flush()

    rest = session.exec(
        select(SessionParticipant).where(SessionParticipant.session_id == ts.id)
    ).all()
    if ts.source == "manual" and [p.id for p in rest] == [own.id]:
        session.delete(own)
        feed.remove_together_event(session, ts)
        session.delete(ts)
        session.commit()
        return
    refresh_session(session, ts, was_real=was)
    session.commit()
    for uid, kind, payload in pending:
        notify(uid, kind, payload)
    _check_achievements(session, [ts])


def decline(session: Session, participant: SessionParticipant) -> None:
    """„War ich nicht dabei“: Teilnahme bleibt als `declined` gespeichert
    (Spec 2.3), damit das Paar nicht erneut vorgeschlagen wird."""
    _respond(session, participant, "declined")


def expire_suggestions(session: Session, now: datetime | None = None) -> None:
    """Unbeantwortete Vorschläge älter als SUGGESTION_DAYS gelten als
    abgelehnt (Spec 2.4, lazy beim Abruf). `responded_at` bleibt leer — es
    gab keine Antwort."""
    cutoff = _naive_utc(now or datetime.now(timezone.utc)) - timedelta(days=SUGGESTION_DAYS)
    expired = [
        p for p in session.exec(
            select(SessionParticipant).where(SessionParticipant.status == "suggested")
        ).all()
        if _naive_utc(p.created_at) < cutoff
    ]
    if not expired:
        return
    affected: dict[int, TrainingSession] = {}
    was_real: dict[int, bool] = {}
    for p in expired:
        ts = session.get(TrainingSession, p.session_id)
        if ts is not None and ts.id not in affected:
            affected[ts.id] = ts
            was_real[ts.id] = is_real(session, ts)
    for p in expired:
        p.status = "declined"
        session.add(p)
    session.flush()
    for ts in affected.values():
        refresh_session(session, ts, was_real=was_real[ts.id])
    session.commit()
    _check_achievements(session, affected.values())


def remove_activity(session: Session, activity_id: int) -> None:
    """Teilnahme einer gelöschten Aktivität entfernen (Spec 2.6). Session
    ohne Teilnahmen wird samt Feed-Event gelöscht, sonst neu berechnet."""
    p = participation_for(session, activity_id)
    if p is None:
        return
    ts = session.get(TrainingSession, p.session_id)
    was = ts is not None and is_real(session, ts)
    session.delete(p)
    session.flush()
    if ts is None:
        session.commit()
        return
    rest = session.exec(
        select(SessionParticipant).where(SessionParticipant.session_id == ts.id)
    ).first()
    if rest is None:
        feed.remove_together_event(session, ts)
        session.delete(ts)
        session.commit()
        return
    refresh_session(session, ts, was_real=was)
    session.commit()
    _check_achievements(session, [ts])


def refresh_session(
    session: Session, ts: TrainingSession, *, was_real: bool, emit_feed: bool = True
) -> None:
    """`km_together`/`share` aus den bestätigten Teilnahmen neu berechnen
    (jeweils Maximum). `share` je Teilnahme = km_together / eigene Distanz,
    gedeckelt auf 1 — das Maximum darüber entspricht dem paarweisen Maximum.
    Danach Feed-Event angleichen: angelegt wird es nur beim Übergang nicht
    echt → echt (`was_real` = Stand vor der Änderung), sonst nur aktualisiert
    oder entfernt — eine im Backfill echt gewordene Session bekommt nie
    nachträglich ein Event. Committet nicht; Achievements prüft der Aufrufer
    nach dem Commit (`_check_achievements`)."""
    confirmed = _confirmed(session, ts)
    ts.km_together = max((p.km_together for p in confirmed), default=0)
    shares = []
    for p in confirmed:
        if p.activity_id is None:
            continue
        a = session.get(Activity, p.activity_id)
        if a is not None and a.distance_km > 0 and p.km_together > 0:
            shares.append(min(1.0, p.km_together / a.distance_km))
    ts.share = max(shares) if shares else None
    session.add(ts)
    session.flush()

    feed.sync_together_event(session, ts, emit=emit_feed and not was_real)
