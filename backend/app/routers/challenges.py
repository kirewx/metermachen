"""API fuer Challenges (Spec 2026-08-04).

Jeder GET loest zuerst faellige Statusuebergaenge auf (lazy, kein Cron) —
gleiches Muster wie bets_router.
"""

import json
from datetime import date as date_type
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_addon, require_admin
from ..models import Category, Challenge, ChallengeParticipant, User
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
    sieger_id: int | None
    kann_sieger_setzen: bool
    created_at: datetime
    resolved_at: datetime | None


class ChallengeCreateIn(BaseModel):
    title: str
    description: str = ""
    prize: str | None = None
    mode: str = "ziel"
    target: float | None = None
    top_n: int = 1
    metric: str = "mm"
    category_ids: list[int] = []
    streak_min_mm: float = 5.0
    join_mode: str = "auto"
    period_start: date_type
    period_end: date_type


class ChallengePatchIn(BaseModel):
    title: str | None = None
    description: str | None = None
    prize: str | None = None
    mode: str | None = None
    target: float | None = None
    top_n: int | None = None
    metric: str | None = None
    category_ids: list[int] | None = None
    streak_min_mm: float | None = None
    join_mode: str | None = None
    period_start: date_type | None = None
    period_end: date_type | None = None


class SiegerIn(BaseModel):
    user_id: int


# Felder, die nur solange status="geplant" geaendert werden duerfen —
# Spielregeln mitten im Lauf zu aendern waere unfair.
REGEL_FELDER = {
    "mode", "target", "top_n", "metric", "category_ids",
    "streak_min_mm", "join_mode", "period_start", "period_end",
}


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
        svc.emit_qualified(session, ch, roh)
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
        sieger_id=svc.sieger_id(ch),
        kann_sieger_setzen=(
            me.is_admin
            and ch.mode == "ziel"
            and ch.status == "beendet"
            and len(gewinner) > 0
        ),
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


def _geladene_challenge(session: Session, challenge_id: int) -> Challenge:
    ch = session.get(Challenge, challenge_id)
    if ch is None or ch.status == "abgebrochen":
        raise HTTPException(status_code=404, detail="Challenge nicht gefunden")
    return ch


@router.post("/{challenge_id}/join", response_model=ChallengeOut)
def join_challenge(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    svc.resolve_due(session)
    ch = _geladene_challenge(session, challenge_id)
    heute = date_type.today()
    if ch.join_mode != "opt_in":
        raise HTTPException(status_code=409, detail="Hier sind alle automatisch dabei")
    if heute > ch.period_end or ch.status == "beendet":
        raise HTTPException(status_code=409, detail="Die Challenge ist vorbei")
    vorhanden = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id,
            ChallengeParticipant.user_id == me.id,
        )
    ).first()
    if vorhanden is None:  # idempotent: zweiter Beitritt ist kein Fehler
        session.add(ChallengeParticipant(challenge_id=ch.id, user_id=me.id))
        session.commit()
    return _challenge_out(session, ch, me, heute)


@router.delete("/{challenge_id}/join", response_model=ChallengeOut)
def leave_challenge(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    svc.resolve_due(session)
    ch = _geladene_challenge(session, challenge_id)
    if ch.status not in ("geplant", "laufend"):
        raise HTTPException(status_code=409, detail="Die Challenge ist vorbei")
    zeile = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id,
            ChallengeParticipant.user_id == me.id,
        )
    ).first()
    if zeile is not None:
        session.delete(zeile)
        session.commit()
    return _challenge_out(session, ch, me, date_type.today())


def _pruefe_regeln(
    session: Session,
    *,
    mode: str,
    target: float | None,
    top_n: int,
    metric: str,
    category_ids: list[int],
    streak_min_mm: float,
    join_mode: str,
    period_start: date_type,
    period_end: date_type,
    neu: bool,
) -> None:
    if mode not in ("ziel", "rangliste"):
        raise HTTPException(status_code=422, detail="Unbekannter Modus")
    if metric not in ("mm", "streak", "anzahl"):
        raise HTTPException(status_code=422, detail="Unbekannte Metrik")
    if join_mode not in ("auto", "opt_in"):
        raise HTTPException(status_code=422, detail="Unbekannte Teilnahme-Art")
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Ende liegt vor dem Start")
    if neu and period_end < date_type.today():
        raise HTTPException(status_code=422, detail="Das Ende liegt in der Vergangenheit")
    if mode == "ziel" and target is None:
        raise HTTPException(status_code=422, detail="Ziel-Challenge braucht ein Ziel")
    if mode == "rangliste" and top_n < 1:
        raise HTTPException(status_code=422, detail="top_n muss mindestens 1 sein")
    if metric == "streak" and streak_min_mm <= 0:
        raise HTTPException(status_code=422, detail="Tages-Minimum muss groesser 0 sein")
    if category_ids:
        bekannt = {c.id for c in session.exec(select(Category)).all()}
        if not set(category_ids) <= bekannt:
            raise HTTPException(status_code=422, detail="Unbekannte Kategorie")


@router.post(
    "", response_model=ChallengeOut, status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_challenge(
    data: ChallengeCreateIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _pruefe_regeln(
        session,
        mode=data.mode, target=data.target, top_n=data.top_n, metric=data.metric,
        category_ids=data.category_ids, streak_min_mm=data.streak_min_mm,
        join_mode=data.join_mode, period_start=data.period_start,
        period_end=data.period_end, neu=True,
    )
    ch = Challenge(
        title=data.title,
        description=data.description,
        prize=data.prize,
        creator_id=me.id,
        mode=data.mode,
        target=data.target,
        top_n=data.top_n,
        metric=data.metric,
        category_ids_json=json.dumps(data.category_ids),
        streak_min_mm=data.streak_min_mm,
        join_mode=data.join_mode,
        period_start=data.period_start,
        period_end=data.period_end,
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    svc.resolve_due(session)
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())


@router.patch(
    "/{challenge_id}", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def patch_challenge(
    challenge_id: int,
    data: ChallengePatchIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    gesetzt = data.model_fields_set
    if gesetzt & REGEL_FELDER and ch.status != "geplant":
        raise HTTPException(
            status_code=409, detail="Wertungsregeln sind nach dem Start fest"
        )
    werte = {
        "mode": data.mode if data.mode is not None else ch.mode,
        "target": data.target if "target" in gesetzt else ch.target,
        "top_n": data.top_n if data.top_n is not None else ch.top_n,
        "metric": data.metric if data.metric is not None else ch.metric,
        "category_ids": data.category_ids
        if data.category_ids is not None
        else svc.category_ids(ch),
        "streak_min_mm": data.streak_min_mm
        if data.streak_min_mm is not None
        else ch.streak_min_mm,
        "join_mode": data.join_mode if data.join_mode is not None else ch.join_mode,
        "period_start": data.period_start or ch.period_start,
        "period_end": data.period_end or ch.period_end,
    }
    _pruefe_regeln(session, neu=False, **werte)

    if data.title is not None:
        ch.title = data.title
    if data.description is not None:
        ch.description = data.description
    if "prize" in gesetzt:
        ch.prize = data.prize
    ch.mode = werte["mode"]
    ch.target = werte["target"]
    ch.top_n = werte["top_n"]
    ch.metric = werte["metric"]
    ch.category_ids_json = json.dumps(werte["category_ids"])
    ch.streak_min_mm = werte["streak_min_mm"]
    ch.join_mode = werte["join_mode"]
    ch.period_start = werte["period_start"]
    ch.period_end = werte["period_end"]
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())


@router.delete(
    "/{challenge_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def cancel_challenge(challenge_id: int, session: Session = Depends(get_session)):
    ch = session.get(Challenge, challenge_id)
    if ch is not None:
        ch.status = "abgebrochen"  # nie loeschen, Historie bleibt
        session.add(ch)
        session.commit()


@router.put(
    "/{challenge_id}/sieger", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def set_sieger(
    challenge_id: int,
    data: SiegerIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    try:
        svc.setze_sieger(
            session, ch, datetime.now(timezone.utc), user_id=data.user_id
        )
    except svc.NichtQualifiziert as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())
