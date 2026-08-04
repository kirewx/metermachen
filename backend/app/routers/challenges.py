"""API fuer Challenges (Spec 2026-08-04).

Jeder GET loest zuerst faellige Statusuebergaenge auf (lazy, kein Cron) —
gleiches Muster wie bets_router.
"""

import json
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_addon
from ..models import Challenge, User
from ..services import challenges as svc

router = APIRouter(
    prefix="/api/challenges",
    tags=["challenges"],
    dependencies=[Depends(require_addon("challenges"))],
)


class StandingEntryOut(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    value: float
    rank: int
    geschafft: bool
    nicht_mehr_schaffbar: bool


class ChallengeOut(BaseModel):
    id: int
    title: str
    description: str
    prize: str | None
    creator_id: int
    mode: str
    target: float | None
    top_n: int
    metric: str
    category_ids: list[int]
    streak_min_mm: float
    join_mode: str
    period_start: date_type
    period_end: date_type
    status: str
    vorlaeufig: bool
    bin_dabei: bool
    kann_beitreten: bool
    standings: list[StandingEntryOut]
    mein_stand: StandingEntryOut | None  # eigener Eintrag, fuer die Hero-Karte
    gewinner_ids: list[int]
    created_at: datetime
    resolved_at: datetime | None


def _users(session: Session) -> dict[int, User]:
    return {u.id: u for u in session.exec(select(User)).all()}


def _challenge_out(
    session: Session, ch: Challenge, me: User, heute: date_type
) -> ChallengeOut:
    users = _users(session)
    teilnehmer = svc.teilnehmer_ids(session, ch)
    if ch.status == "beendet":
        ergebnis = json.loads(ch.result_json or "{}")
        roh = [
            {**e, "nicht_mehr_schaffbar": False} for e in ergebnis.get("entries", [])
        ]
        gewinner = ergebnis.get("gewinner_ids", [])
    else:
        roh = svc.standings(session, ch, heute)
        gewinner = [e["user_id"] for e in roh if e["geschafft"]]

    def eintrag(e: dict) -> StandingEntryOut:
        u = users.get(e["user_id"])
        return StandingEntryOut(
            user_id=e["user_id"],
            display_name=u.display_name if u else "?",
            avatar=u.avatar if u else "icon:laufen",
            value=e["value"],
            rank=e["rank"],
            geschafft=e["geschafft"],
            nicht_mehr_schaffbar=e["nicht_mehr_schaffbar"],
        )

    liste = [eintrag(e) for e in roh]
    return ChallengeOut(
        id=ch.id,
        title=ch.title,
        description=ch.description,
        prize=ch.prize,
        creator_id=ch.creator_id,
        mode=ch.mode,
        target=ch.target,
        top_n=ch.top_n,
        metric=ch.metric,
        category_ids=svc.category_ids(ch),
        streak_min_mm=ch.streak_min_mm,
        join_mode=ch.join_mode,
        period_start=ch.period_start,
        period_end=ch.period_end,
        status=ch.status,
        vorlaeufig=svc.ist_vorlaeufig(ch, heute),
        bin_dabei=me.id in teilnehmer,
        kann_beitreten=(
            ch.join_mode == "opt_in"
            and me.id not in teilnehmer
            and ch.status in ("geplant", "laufend")
            and heute <= ch.period_end
        ),
        standings=liste,
        mein_stand=next((e for e in liste if e.user_id == me.id), None),
        gewinner_ids=gewinner,
        created_at=ch.created_at,
        resolved_at=ch.resolved_at,
    )


@router.get("", response_model=list[ChallengeOut])
def list_challenges(
    me: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    svc.resolve_due(session)
    heute = date_type.today()
    alle = session.exec(
        select(Challenge)
        .where(Challenge.status != "abgebrochen")
        .order_by(Challenge.period_end, Challenge.id)
    ).all()
    return [_challenge_out(session, ch, me, heute) for ch in alle]


@router.get("/{challenge_id}", response_model=ChallengeOut)
def get_challenge(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    svc.resolve_due(session)
    ch = session.get(Challenge, challenge_id)
    if ch is None or ch.status == "abgebrochen":
        raise HTTPException(status_code=404, detail="Challenge nicht gefunden")
    return _challenge_out(session, ch, me, date_type.today())
