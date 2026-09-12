"""API fuer Challenges (Spec 2026-08-04).

Jeder GET loest zuerst faellige Statusuebergaenge auf (lazy, kein Cron) —
gleiches Muster wie bets_router.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as date_type
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_addon, require_admin
from ..models import Category, Challenge, ChallengeParticipant, User
from ..services import challenge_groups as groups_svc
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


class GroupOut(BaseModel):
    id: int
    name: str
    size: int
    sum: float
    value: float  # per head
    rank: int
    geschafft: bool
    members: list[StandingEntryOut]


class GroupIn(BaseModel):
    id: int
    name: str
    member_ids: list[int]


class GroupsIn(BaseModel):
    groups: list[GroupIn]


class SeedingEntryOut(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    value: float


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
    team_mode: bool
    group_count: int | None
    seeding_days: int
    groups_drawn: bool
    groups: list[GroupOut]
    unassigned: list[StandingEntryOut]  # planned group challenges: pool without a group
    meine_gruppe_id: int | None
    sieger_group_id: int | None
    kann_gruppen_bearbeiten: bool
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
    team_mode: bool = False
    group_count: int | None = None
    seeding_days: int = 30


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
    team_mode: bool | None = None
    group_count: int | None = None
    seeding_days: int | None = None


class SiegerIn(BaseModel):
    user_id: int | None = None
    group_id: int | None = None


# Felder, die nur solange status="geplant" geaendert werden duerfen —
# Spielregeln mitten im Lauf zu aendern waere unfair.
REGEL_FELDER = {
    "mode", "target", "top_n", "metric", "category_ids",
    "streak_min_mm", "join_mode", "period_start", "period_end",
    "team_mode", "group_count", "seeding_days",
}


def _users(session: Session) -> dict[int, User]:
    return {u.id: u for u in session.exec(select(User)).all()}


@dataclass
class _GroupBlock:
    """Everything a ChallengeOut says about groups. Empty for non-team
    challenges, so the response builder needs no second code path."""

    groups: list[GroupOut] = field(default_factory=list)
    unassigned: list[StandingEntryOut] = field(default_factory=list)
    pool: list[int] = field(default_factory=list)
    gewinner_ids: list[int] = field(default_factory=list)
    gewinner_group_ids: list[int] = field(default_factory=list)


def _group_block(
    session: Session,
    ch: Challenge,
    gruppen_roh: list[dict],
    gruppen_json: list[dict],
    eintrag: Callable[[dict], StandingEntryOut],
) -> _GroupBlock:
    """gruppen_roh is the already aggregated group standing and gruppen_json the
    already parsed groups_json, so both happen exactly once per response."""
    # Per-person "geschafft" says nothing in a team challenge — the winners are
    # exactly the members of the groups that made it.
    geschaffte = [g for g in gruppen_roh if g["geschafft"]]
    block = _GroupBlock(
        groups=[
            GroupOut(
                id=g["id"],
                name=g["name"],
                size=g["size"],
                sum=g["sum"],
                value=g["value"],
                rank=g["rank"],
                geschafft=g["geschafft"],
                members=[eintrag(m) for m in g["members"]],
            )
            for g in gruppen_roh
        ],
        gewinner_ids=[uid for g in geschaffte for uid in g["member_ids"]],
        gewinner_group_ids=[g["id"] for g in geschaffte],
    )
    if ch.status == "geplant":
        block.pool = groups_svc.pool(session, ch)
        zugeteilt = {uid for g in gruppen_json for uid in g["member_ids"]}
        block.unassigned = [
            eintrag({"user_id": uid, "value": 0.0})
            for uid in block.pool
            if uid not in zugeteilt
        ]
    return block


def _challenge_out(
    session: Session, ch: Challenge, me: User, heute: date_type
) -> ChallengeOut:
    users = _users(session)
    teilnehmer = svc.teilnehmer_ids(session, ch)
    ergebnis = json.loads(ch.result_json or "{}")
    sieger = ergebnis.get("sieger") or {}
    gruppen_json = svc.groups(ch)
    beendet = ch.status == "beendet"
    if beendet:
        roh = [
            {**e, "nicht_mehr_schaffbar": False} for e in ergebnis.get("entries", [])
        ]
        gewinner = ergebnis.get("gewinner_ids", [])
        gewinner_gruppen = ergebnis.get("gewinner_group_ids", [])
    else:
        roh = svc.standings(session, ch, heute)
        gewinner = [e["user_id"] for e in roh if e["geschafft"]]
        gewinner_gruppen = []

    def eintrag(e: dict) -> StandingEntryOut:
        """Works for standings entries and for the leaner group member dicts,
        which only carry user_id and value."""
        u = users.get(e["user_id"])
        return StandingEntryOut(
            user_id=e["user_id"],
            display_name=u.display_name if u else "?",
            avatar=u.avatar if u else "icon:laufen",
            value=e["value"],
            rank=e.get("rank", 0),
            geschafft=e.get("geschafft", False),
            nicht_mehr_schaffbar=e.get("nicht_mehr_schaffbar", False),
        )

    # A finished team challenge re-aggregates the live groups over the frozen
    # entries only to attach display data (names, sizes, members); that cannot
    # diverge from the frozen snapshot because groups are immutable after
    # "geplant".
    gruppen_roh = svc.group_standings(ch, roh) if ch.team_mode else None
    if not beendet:
        svc.emit_qualified(session, ch, roh, gruppen=gruppen_roh)
    block = (
        _group_block(session, ch, gruppen_roh, gruppen_json, eintrag)
        if gruppen_roh is not None
        else _GroupBlock()
    )
    if ch.team_mode and not beendet:
        gewinner = block.gewinner_ids
        gewinner_gruppen = block.gewinner_group_ids

    meine_gruppe = next(
        (g for g in gruppen_json if me.id in g["member_ids"]), None
    )
    bin_dabei = me.id in teilnehmer or (
        ch.team_mode and ch.status == "geplant" and me.id in block.pool
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
        bin_dabei=bin_dabei,
        kann_beitreten=(
            ch.join_mode == "opt_in"
            and not bin_dabei
            and ch.status in ("geplant", "laufend")
            and heute <= ch.period_end
            and (not ch.team_mode or ch.status == "geplant")
        ),
        standings=liste,
        mein_stand=next((e for e in liste if e.user_id == me.id), None),
        gewinner_ids=gewinner,
        sieger_id=sieger.get("user_id"),
        kann_sieger_setzen=(
            me.is_admin
            and ch.mode == "ziel"
            and ch.status == "beendet"
            and len(gewinner) > 0
            and (not ch.team_mode or len(gewinner_gruppen) > 0)
        ),
        team_mode=ch.team_mode,
        group_count=ch.group_count,
        seeding_days=ch.seeding_days,
        groups_drawn=len(gruppen_json) > 0,
        groups=block.groups,
        unassigned=block.unassigned,
        meine_gruppe_id=meine_gruppe["id"] if meine_gruppe else None,
        sieger_group_id=sieger.get("group_id"),
        kann_gruppen_bearbeiten=(
            me.is_admin and ch.team_mode and ch.status == "geplant"
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
    if ch.team_mode and ch.status != "geplant":
        raise HTTPException(status_code=409, detail="Die Gruppen stehen bereits fest")
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
    if ch.team_mode and ch.status != "geplant":
        raise HTTPException(status_code=409, detail="Die Gruppen stehen bereits fest")
    zeile = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id,
            ChallengeParticipant.user_id == me.id,
        )
    ).first()
    if zeile is not None:
        session.delete(zeile)
        if ch.team_mode:  # leaving also gives up the seat in the group
            svc.remove_group_member(ch, me.id)
            session.add(ch)
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
    team_mode: bool,
    group_count: int | None,
    seeding_days: int,
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
    if seeding_days < 1:
        raise HTTPException(
            status_code=422, detail="Setzliste braucht mindestens 1 Tag"
        )
    if team_mode:
        if metric not in ("mm", "anzahl"):
            raise HTTPException(
                status_code=422, detail="Gruppen-Challenges werten nur MM oder Anzahl"
            )
        if group_count is None or group_count < 2:
            raise HTTPException(status_code=422, detail="Mindestens 2 Gruppen")


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
        period_end=data.period_end, team_mode=data.team_mode,
        group_count=data.group_count, seeding_days=data.seeding_days, neu=True,
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
        team_mode=data.team_mode,
        group_count=data.group_count if data.team_mode else None,
        seeding_days=data.seeding_days,
    )
    # In auto mode the pool is already known, so the draw happens right away —
    # before the first commit, so a failing draw leaves no half-built challenge.
    if data.team_mode and data.join_mode == "auto":
        try:
            groups_svc.draw(session, ch, date_type.today(), datetime.now(timezone.utc))
        except (groups_svc.TooFewPeople, groups_svc.InvalidGroups) as e:
            raise HTTPException(status_code=422, detail=str(e))
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
        "team_mode": data.team_mode if data.team_mode is not None else ch.team_mode,
        "group_count": data.group_count
        if "group_count" in gesetzt
        else ch.group_count,
        "seeding_days": data.seeding_days
        if data.seeding_days is not None
        else ch.seeding_days,
    }
    _pruefe_regeln(session, neu=False, **werte)
    # A different number of groups (or switching the mode on or off) invalidates
    # the draw; the admin has to draw again rather than get a silent reshuffle.
    gruppen_neu = (
        werte["group_count"] != ch.group_count or werte["team_mode"] != ch.team_mode
    )

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
    ch.team_mode = werte["team_mode"]
    ch.group_count = werte["group_count"] if werte["team_mode"] else None
    ch.seeding_days = werte["seeding_days"]
    if gruppen_neu:
        svc.set_groups(ch, [])
        ch.groups_drawn_at = None
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


def _nur_team_geplant(ch: Challenge) -> None:
    """Groups are rule data: only a planned group challenge may be reshuffled."""
    if not ch.team_mode:
        raise HTTPException(status_code=409, detail="Keine Gruppen-Challenge")
    if ch.status != "geplant":
        raise HTTPException(status_code=409, detail="Die Gruppen stehen bereits fest")


@router.post(
    "/{challenge_id}/draw", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def draw_groups(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    _nur_team_geplant(ch)
    try:
        groups_svc.draw(session, ch, date_type.today(), datetime.now(timezone.utc))
    except (groups_svc.TooFewPeople, groups_svc.InvalidGroups) as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())


@router.put(
    "/{challenge_id}/groups", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def save_groups(
    challenge_id: int,
    data: GroupsIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    _nur_team_geplant(ch)
    try:
        groups_svc.save_groups(session, ch, [g.model_dump() for g in data.groups])
    except groups_svc.InvalidGroups as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _challenge_out(session, ch, me, date_type.today())


@router.get(
    "/{challenge_id}/seeding", response_model=list[SeedingEntryOut],
    dependencies=[Depends(require_admin)],
)
def seeding_list(challenge_id: int, session: Session = Depends(get_session)):
    """Every active user with their seeding value, for the group editor."""
    ch = _geladene_challenge(session, challenge_id)
    _nur_team_geplant(ch)
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    return [
        SeedingEntryOut(
            user_id=uid,
            display_name=users[uid].display_name,
            avatar=users[uid].avatar,
            value=wert,
        )
        for uid, wert in groups_svc.seeding(
            session, ch, date_type.today(), sorted(users.keys())
        )
    ]


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
    if (data.user_id is None) == (data.group_id is None):
        raise HTTPException(
            status_code=422, detail="Entweder user_id oder group_id"
        )
    try:
        svc.setze_sieger(
            session, ch, datetime.now(timezone.utc),
            user_id=data.user_id, group_id=data.group_id,
        )
    except svc.NichtQualifiziert as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())
