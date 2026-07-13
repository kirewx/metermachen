"""API für Wetten, Punkte und Wett-Achievements.

Jeder GET /api/bets löst zuerst fällige Wetten auf (lazy, kein Cron) und
legt bei Bedarf die Monats-Tipprunde an.
"""

import json
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Bet, BetParticipant, PointTransaction, User
from ..services import bet_metrics, bets, points

router = APIRouter(prefix="/api/bets", tags=["bets"])
points_router = APIRouter(prefix="/api/points", tags=["points"])


# ------------------------------------------------------------------ Schemas


class BetCreateIn(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=120)
    stake: int = Field(gt=0)
    period_start: date_type
    period_end: date_type
    params: dict = {}


class BetRespondIn(BaseModel):
    action: str  # accept | decline | dagegenhalten | ueber | unter | tippen
    stake: int | None = Field(default=None, gt=0)
    choice: dict | None = None


class ParticipantOut(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    role: str
    stake: int
    payout: int | None
    choice: dict


class BetOut(BaseModel):
    id: int
    type: str
    creator_id: int
    title: str
    stake: int
    period_start: date_type
    period_end: date_type
    status: str
    jackpot: int
    created_at: datetime
    resolved_at: datetime | None
    params: dict
    result: dict
    participants: list[ParticipantOut]
    standing: dict  # Live-Zwischenstand für laufende Wetten
    my_role: str | None


class PointTransactionOut(BaseModel):
    amount: int
    reason: str
    bet_id: int | None
    created_at: datetime


class PointsInfo(BaseModel):
    balance: int
    transactions: list[PointTransactionOut]


class PointsRankingEntry(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    balance: int
    rank: int


class BetAchievementOut(BaseModel):
    key: str
    title: str
    description: str
    icon: str
    achieved: bool
    progress: float  # 0..1


# ------------------------------------------------------------------ Helpers


def _standing(session: Session, bet: Bet, users: dict[int, User]) -> dict:
    """Live-Zwischenstand; nach der Auflösung stehen die Werte in result_json."""
    if bet.status not in ("offen", "laufend"):
        return {}
    heute = date_type.today()
    von = bet.period_start
    bis = min(bet.period_end, heute)
    if von > heute:
        return {}
    p = json.loads(bet.params_json or "{}")
    if bet.type == "duell":
        opp_id = int(p.get("opponent_id", 0))
        return {
            "creator_km": bet_metrics.scaled_km(session, bet.creator_id, von, bis),
            "opponent_km": bet_metrics.scaled_km(session, opp_id, von, bis),
        }
    if bet.type in ("ziel", "streak"):
        if bet.type == "streak":
            return {
                "streak": bet_metrics.longest_streak(session, bet.creator_id, von, bis)
            }
        return {"km": bet_metrics.scaled_km(session, bet.creator_id, von, bis)}
    if bet.type == "ueber_unter":
        return {
            "gruppen_km": bet_metrics.group_scaled_km(
                session, list(users.keys()), von, bis
            )
        }
    if bet.type == "monats_tipp":
        totals = {
            uid: round(
                bet_metrics.scaled_km(session, uid, von, bis) * u.km_factor, 2
            )
            for uid, u in users.items()
        }
        fuehrender = max(totals, key=totals.get) if totals else None
        return {"fuehrender_user_id": fuehrender}
    return {}


def _bet_out(session: Session, bet: Bet, me: User, users: dict[int, User]) -> BetOut:
    parts = session.exec(
        select(BetParticipant)
        .where(BetParticipant.bet_id == bet.id)
        .order_by(BetParticipant.id)
    ).all()
    my_role = next((t.role for t in parts if t.user_id == me.id), None)
    return BetOut(
        id=bet.id,
        type=bet.type,
        creator_id=bet.creator_id,
        title=bet.title,
        stake=bet.stake,
        period_start=bet.period_start,
        period_end=bet.period_end,
        status=bet.status,
        jackpot=bet.jackpot,
        created_at=bet.created_at,
        resolved_at=bet.resolved_at,
        params=json.loads(bet.params_json or "{}"),
        result=json.loads(bet.result_json or "{}"),
        participants=[
            ParticipantOut(
                user_id=t.user_id,
                display_name=users[t.user_id].display_name
                if t.user_id in users
                else "?",
                avatar=users[t.user_id].avatar if t.user_id in users else "icon:laufen",
                role=t.role,
                stake=t.stake,
                payout=t.payout,
                choice=json.loads(t.choice_json or "{}"),
            )
            for t in parts
        ],
        standing=_standing(session, bet, users),
        my_role=my_role,
    )


def _all_users(session: Session) -> dict[int, User]:
    return {u.id: u for u in session.exec(select(User)).all()}


def _active_users(session: Session) -> dict[int, User]:
    return {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}


# ------------------------------------------------------------------ Wetten


@router.get("", response_model=list[BetOut])
def list_bets(
    me: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    bets.ensure_monthly_tip(session)
    bets.resolve_due(session)
    users = _all_users(session)
    aktive = _active_users(session)
    alle = session.exec(select(Bet).order_by(Bet.created_at.desc())).all()
    return [
        _bet_out(session, b, me, aktive if b.type in ("ueber_unter", "monats_tipp") else users)
        for b in alle
    ]


@router.post("", response_model=BetOut, status_code=201)
def create_bet(
    data: BetCreateIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    try:
        bet = bets.create_bet(
            session,
            me,
            type=data.type,
            title=data.title,
            stake=data.stake,
            period_start=data.period_start,
            period_end=data.period_end,
            params=data.params,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _bet_out(session, bet, me, _all_users(session))


@router.post("/{bet_id}/respond", response_model=BetOut)
def respond_bet(
    bet_id: int,
    data: BetRespondIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    bet = session.get(Bet, bet_id)
    if bet is None:
        raise HTTPException(status_code=404, detail="Wette nicht gefunden")
    try:
        bet = bets.respond(
            session, bet, me, action=data.action, stake=data.stake, choice=data.choice
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _bet_out(session, bet, me, _all_users(session))


@router.post("/{bet_id}/cancel", response_model=BetOut)
def cancel_bet(
    bet_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    bet = session.get(Bet, bet_id)
    if bet is None:
        raise HTTPException(status_code=404, detail="Wette nicht gefunden")
    try:
        bet = bets.cancel(session, bet, me)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _bet_out(session, bet, me, _all_users(session))


# ------------------------------------------------------- Wett-Achievements


_BET_ACHIEVEMENTS = [
    ("zocker", "Zocker", "10 Wetten abgeschlossen — egal wie sie ausgingen.", "medaille"),
    ("david", "David gegen Goliath", "Ein Duell gegen jemanden gewonnen, der im KM-Ranking über dir stand.", "blitz"),
    ("high_roller", "High Roller", "Eine Wette mit mindestens 50 Punkten Einsatz gewonnen.", "pokal"),
    ("orakel", "Orakel", "3 Monats-Tipps richtig gelegen.", "fahne"),
]


@router.get("/achievements", response_model=list[BetAchievementOut])
def bet_achievements(
    me: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    rows = session.exec(
        select(BetParticipant, Bet)
        .join(Bet, BetParticipant.bet_id == Bet.id)
        .where(BetParticipant.user_id == me.id, Bet.status == "entschieden")
    ).all()
    abgeschlossen = len(rows)
    gewonnen = [
        (t, b)
        for t, b in rows
        if me.id in json.loads(b.result_json or "{}").get("winner_ids", [])
    ]
    david = any(
        b.type == "duell" and json.loads(b.result_json or "{}").get("david")
        for _, b in gewonnen
    )
    high_roller = any(t.stake >= 50 for t, _ in gewonnen)
    orakel = sum(1 for _, b in gewonnen if b.type == "monats_tipp")

    werte = {
        "zocker": min(abgeschlossen / 10, 1.0),
        "david": 1.0 if david else 0.0,
        "high_roller": 1.0 if high_roller else 0.0,
        "orakel": min(orakel / 3, 1.0),
    }
    return [
        BetAchievementOut(
            key=key,
            title=title,
            description=desc,
            icon=icon,
            achieved=werte[key] >= 1.0,
            progress=round(werte[key], 4),
        )
        for key, title, desc, icon in _BET_ACHIEVEMENTS
    ]


# ------------------------------------------------------------------ Punkte


@points_router.get("", response_model=PointsInfo)
def my_points(
    me: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    points.refresh_user(session, me.id)
    txs = session.exec(
        select(PointTransaction)
        .where(PointTransaction.user_id == me.id)
        .order_by(PointTransaction.created_at.desc(), PointTransaction.id.desc())
    ).all()
    return PointsInfo(
        balance=points.balance(session, me.id),
        transactions=[
            PointTransactionOut(
                amount=t.amount, reason=t.reason, bet_id=t.bet_id, created_at=t.created_at
            )
            for t in txs
        ],
    )


@points_router.get(
    "/ranking",
    response_model=list[PointsRankingEntry],
    dependencies=[Depends(get_current_user)],
)
def points_ranking(session: Session = Depends(get_session)):
    users = session.exec(select(User).where(User.is_active).order_by(User.id)).all()
    for u in users:
        points.refresh_user(session, u.id)
    eintraege = sorted(
        (
            PointsRankingEntry(
                user_id=u.id,
                display_name=u.display_name,
                avatar=u.avatar,
                balance=points.balance(session, u.id),
                rank=0,
            )
            for u in users
        ),
        key=lambda e: -e.balance,
    )
    for i, e in enumerate(eintraege):
        e.rank = i + 1
    return eintraege
