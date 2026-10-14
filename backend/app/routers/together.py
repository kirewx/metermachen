"""API für Together-Vorschläge, Bestätigen/Ablehnen und Partner-Statistik
(Spec 2026-10-05, 4.3). Hängt komplett am Add-on `together`: aus liefert
jeder Endpoint 404."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_addon
from ..models import Activity, SessionParticipant, TrainingSession, User
from ..schemas import ActivityOut, PartnerActivityBrief, TogetherPartnerBrief
from ..services import together
from ..services.factors import FactorResolver
from .activities import _to_out, _together_map

router = APIRouter(
    prefix="/api/together",
    tags=["together"],
    dependencies=[Depends(require_addon("together"))],
)


class ConfirmIn(BaseModel):
    activity_id: int | None = None


class SuggestionOut(BaseModel):
    participant_id: int
    session_id: int
    source: str
    partners: list[TogetherPartnerBrief]
    km_together: float
    share: float | None
    my_activity: ActivityOut | None
    partner_activity: PartnerActivityBrief | None
    candidates: list[ActivityOut]


class PartnerOut(BaseModel):
    user_id: int
    display_name: str
    sessions: int
    km_together: float


def _own_participant(session: Session, user: User, participant_id: int) -> SessionParticipant:
    p = session.get(SessionParticipant, participant_id)
    if p is None or p.user_id != user.id:
        raise HTTPException(status_code=404)
    return p


def _other_partners(
    session: Session, session_id: int, exclude_user_id: int
) -> list[TogetherPartnerBrief]:
    """Andere, nicht abgelehnte Teilnehmer der Session (Spec 4.3: `partners`
    für `SuggestionOut` = alle nicht-`declined` außer sich selbst)."""
    rows = session.exec(
        select(SessionParticipant).where(
            SessionParticipant.session_id == session_id,
            SessionParticipant.user_id != exclude_user_id,
            SessionParticipant.status != "declined",
        )
    ).all()
    if not rows:
        return []
    users = {
        u.id: u for u in session.exec(
            select(User).where(User.id.in_({p.user_id for p in rows}))
        ).all()
    }
    return [
        TogetherPartnerBrief(user_id=p.user_id, display_name=users[p.user_id].display_name)
        for p in rows
        if p.user_id in users
    ]


@router.get("/suggestions", response_model=list[SuggestionOut])
def suggestions(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
) -> list[SuggestionOut]:
    """Eigene offene Vorschläge und Tags (Spec 4.3), inkl. Kandidaten-
    Aktivitäten vom Tag ±1 für Tags ohne eigene Aktivität."""
    together.expire_suggestions(session)
    resolver = FactorResolver.load(session)
    rows = session.exec(
        select(SessionParticipant)
        .where(
            SessionParticipant.user_id == user.id,
            SessionParticipant.status == "suggested",
        )
        .order_by(SessionParticipant.created_at, SessionParticipant.id)
    ).all()
    out: list[SuggestionOut] = []
    for p in rows:
        ts = session.get(TrainingSession, p.session_id)
        my_activity = None
        candidates: list[ActivityOut] = []
        if p.activity_id is not None:
            act = session.get(Activity, p.activity_id)
            if act is not None:
                together_out = _together_map(session, [act]).get(act.id)
                my_activity = _to_out(act, resolver, together_out)
        else:
            candidates = [
                _to_out(a, resolver) for a in together.link_candidates(session, p)
            ]
        out.append(SuggestionOut(
            participant_id=p.id,
            session_id=p.session_id,
            source=ts.source if ts is not None else "auto",
            partners=_other_partners(session, p.session_id, user.id),
            km_together=p.km_together,
            share=ts.share if ts is not None else None,
            my_activity=my_activity,
            partner_activity=together.partner_activity_brief(session, p),
            candidates=candidates,
        ))
    return out


@router.post("/participants/{participant_id}/confirm", status_code=204)
def confirm_participant(
    participant_id: int,
    data: ConfirmIn | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    p = _own_participant(session, user, participant_id)
    activity_id = data.activity_id if data is not None else None
    together.confirm(session, p, activity_id=activity_id)


@router.post("/participants/{participant_id}/decline", status_code=204)
def decline_participant(
    participant_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    p = _own_participant(session, user, participant_id)
    together.decline(session, p)


@router.get("/partners/{user_id}", response_model=list[PartnerOut])
def partners(
    user_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[PartnerOut]:
    """Partner-Statistik fürs Profil (Spec 3.2), für jeden eingeloggten
    Nutzer einsehbar."""
    target = session.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    return [PartnerOut(**row) for row in together.partner_stats(session, user_id)]
