"""Achievements: kleine Erfolge über kumulierte (rohe, ungewertete) Kilometer.

Aktivitäten hängen an frei konfigurierbaren Kategorien, Achievements aber an
Sportarten. Die Zuordnung Kategorie -> Sport-Bucket läuft über drei Signale
(Icon, gemappte Strava-Sportarten, Name), damit sie auch nach Umbenennungen
oder bei selbst angelegten Kategorien greift.
"""

from collections import defaultdict
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import AchievementUnlock, Activity, Category, User
from ..services.achievements import (
    DISZIPLIN_ICON,
    DISZIPLIN_LABEL,
    EARLY_BIRD_DEF,
    EINMAL_DEFS,
    EMOJIS,
    FRUEHSTARTER_DEF,
    FRUEHSTARTER_ZIEL_MM,
    HIDDEN_DEFS,
    LAUF,
    RAD,
    SCHWIMM,
    STUFEN_ZIELE,
    TIERS,
    bucket_for_category,
    check_unlocks,
    fuehrungs_zeit,
    stufen_key,
    warmup_mm,
)
from ..services.season_window import current_season

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


class Part(BaseModel):
    label: str
    current_km: float
    target_km: float


class AchievementOut(BaseModel):
    key: str
    title: str
    description: str
    icon: str
    achieved: bool
    progress: float  # 0..1, min über alle Teile
    parts: list[Part]
    hidden: bool = False
    tier: str | None = None  # "bronze" | "silber" | "gold"
    discipline: str | None = None
    unlocked_at: datetime | None = None
    emoji: str | None = None
    showcased: bool | None = None  # nur beim eigenen Emoji-Unlock gesetzt
    claimed_by: str | None = None  # Einmal-Achievements: wer es schon hat
    timer_hours: float | None = None  # fortlaufend (Zeit an der Spitze)
    timer_running: bool | None = None  # Timer tickt gerade (aktuell Platz 1)


# (key, title, description, icon, {bucket: ziel_km})
# "gesamt" = alle Aktivitäten unabhängig vom Bucket.
DEFINITIONS: list[tuple[str, str, str, str, dict[str, float]]] = [
    (
        "startschuss", "Startschuss",
        "Deine erste Aktivität ist im Kasten.",
        "fahne", {"gesamt": 0.01},
    ),
    (
        "marathon", "Marathon",
        "42,2 km gelaufen — die Königsdisziplin, in Etappen.",
        "laufen", {LAUF: 42.2},
    ),
    (
        "aermelkanal", "Ärmelkanal",
        "34 km geschwommen — einmal Dover–Calais.",
        "schwimmen", {SCHWIMM: 34.0},
    ),
    (
        "transalp", "Transalp",
        "500 km geradelt — einmal quer über die Alpen.",
        "berg", {RAD: 500.0},
    ),
    (
        # Ricks Hausnummern (190/42/4), bewusst nicht die offiziellen
        # Ironman-Distanzen (180/42,2/3,86).
        "ironman", "Ironman",
        "190 km Rad, 42 km Laufen und 4 km Schwimmen — die volle Distanz.",
        "pokal", {RAD: 190.0, LAUF: 42.0, SCHWIMM: 4.0},
    ),
    (
        "tausender", "Tausender-Club",
        "1000 km insgesamt zurückgelegt, quer durch alle Sportarten.",
        "blitz", {"gesamt": 1000.0},
    ),
]


class WarmupWinner(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    km: float


class WarmupAchievement(BaseModel):
    key: str
    title: str
    icon: str
    winners: list[WarmupWinner]  # bei Gleichstand mehrere


class WarmupOut(BaseModel):
    final: bool  # True sobald die Challenge gestartet ist
    start_date: date_type | None
    achievements: list[WarmupAchievement]


# (key, titel, icon, bucket) — "gesamt" = gewertete km (Kategorie-Faktor),
# Sport-Buckets = rohe km. Admin-Handicap zählt hier bewusst nicht.
_WARMUP_DEFS = [
    ("guter_start", "Guter Start", "fahne", "gesamt"),
    ("warmup_laeufer", "Warm-up-Läufer", "laufen", LAUF),
    ("warmup_radler", "Warm-up-Radler", "rad", RAD),
    ("warmup_schwimmer", "Warm-up-Schwimmer", "schwimmen", SCHWIMM),
]


@router.get(
    "/warmup", response_model=WarmupOut, dependencies=[Depends(get_current_user)]
)
def warmup_achievements(session: Session = Depends(get_session)):
    today = date_type.today()
    season = current_season(session)
    start = season.start_date if season else None
    if start is None:
        return WarmupOut(final=False, start_date=None, achievements=[])

    cats = {c.id: c for c in session.exec(select(Category)).all()}
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    # {bucket bzw. "gesamt": {user_id: km}}
    sums: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for act in session.exec(select(Activity).where(Activity.date < start)).all():
        if act.user_id not in users or act.date.year != start.year:
            continue
        cat = cats.get(act.category_id)
        if cat is None:
            continue
        sums["gesamt"][act.user_id] += act.distance_km * cat.factor
        bucket = bucket_for_category(cat)
        if bucket is not None:
            sums[bucket][act.user_id] += act.distance_km

    out = []
    for key, title, icon, bucket in _WARMUP_DEFS:
        totals = sums.get(bucket, {})
        if not totals:
            continue
        best = max(totals.values())
        winners = [
            WarmupWinner(
                user_id=uid,
                display_name=users[uid].display_name,
                avatar=users[uid].avatar,
                km=round(km, 2),
            )
            for uid, km in sorted(totals.items(), key=lambda kv: -kv[1])
            if km == best
        ]
        out.append(WarmupAchievement(key=key, title=title, icon=icon, winners=winners))
    return WarmupOut(final=today >= start, start_date=start, achievements=out)


@router.get("", response_model=list[AchievementOut])
def achievements(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    # „Platz 1 gehalten"/Testphasen-Sieg können ohne eigene Aktivität eintreten —
    # deshalb wird beim Abruf für die anfragende Person geprüft (Spec §2.2).
    check_unlocks(session, user.id)

    cats = {c.id: c for c in session.exec(select(Category)).all()}
    user_acts = session.exec(
        select(Activity).where(Activity.user_id == user.id)
    ).all()
    sums: dict[str, float] = defaultdict(float)
    for act in user_acts:
        sums["gesamt"] += act.distance_km
        cat = cats.get(act.category_id)
        bucket = bucket_for_category(cat) if cat else None
        if bucket is not None:
            sums[bucket] += act.distance_km

    own = {
        u.key: u
        for u in session.exec(
            select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
        ).all()
    }
    einmal_keys = [key for key, *_ in EINMAL_DEFS]
    inhaber: dict[str, str] = {}
    rows = session.exec(
        select(AchievementUnlock, User)
        .join(User, AchievementUnlock.user_id == User.id)
        .where(AchievementUnlock.key.in_(einmal_keys))
        .order_by(AchievementUnlock.unlocked_at)
    ).all()
    for ul, u in rows:
        inhaber.setdefault(ul.key, u.display_name)

    _LABELS = {RAD: "Rad", LAUF: "Laufen", SCHWIMM: "Schwimmen", "gesamt": "Gesamt"}
    out = []
    for key, title, description, icon, targets in DEFINITIONS:
        parts = [
            Part(
                label=_LABELS[bucket],
                current_km=round(min(sums[bucket], target), 2),
                target_km=target,
            )
            for bucket, target in targets.items()
        ]
        progress = min(p.current_km / p.target_km for p in parts)
        out.append(
            AchievementOut(
                key=key,
                title=title,
                description=description,
                icon=icon,
                achieved=progress >= 1.0,
                progress=round(min(progress, 1.0), 4),
                parts=parts,
            )
        )

    # Stufen: 9 Einträge, Frontend gruppiert über tier/discipline
    for bucket in (RAD, LAUF, SCHWIMM):
        for tier in TIERS:
            key = stufen_key(bucket, tier)
            ziel = STUFEN_ZIELE[bucket][tier]
            ul = own.get(key)
            out.append(
                AchievementOut(
                    key=key,
                    title=f"{DISZIPLIN_LABEL[bucket]} {tier.capitalize()}",
                    description=f"{int(ziel)} km {DISZIPLIN_LABEL[bucket]} insgesamt.",
                    icon=DISZIPLIN_ICON[bucket],
                    achieved=ul is not None or sums[bucket] >= ziel,
                    progress=round(min(sums[bucket] / ziel, 1.0), 4),
                    parts=[Part(
                        label=DISZIPLIN_LABEL[bucket],
                        current_km=round(min(sums[bucket], ziel), 2),
                        target_km=ziel,
                    )],
                    tier=tier,
                    discipline=bucket,
                    unlocked_at=ul.unlocked_at if ul else None,
                )
            )

    # Einmal-Achievements: Erster-Bonus + Testphasen-Sieger
    for key, title, description, icon in EINMAL_DEFS:
        ul = own.get(key)
        out.append(
            AchievementOut(
                key=key,
                title=title,
                description=description,
                icon=icon,
                achieved=ul is not None,
                progress=1.0 if ul else 0.0,
                parts=[],
                unlocked_at=ul.unlocked_at if ul else None,
                emoji=EMOJIS.get(key),
                showcased=ul.showcased if ul else None,
                claimed_by=inhaber.get(key),
            )
        )

    # Frühstarter: sichtbar, kann jede Person bekommen — Fortschritt sind die
    # gewerteten Warm-up-MM (Kategorie-Faktor, ohne Handicap)
    season = current_season(session)
    start = season.start_date if season else None
    mm = warmup_mm(user_acts, cats, start) if start is not None else 0.0
    key, title, description, icon = FRUEHSTARTER_DEF
    ul = own.get(key)
    out.append(
        AchievementOut(
            key=key,
            title=title,
            description=description,
            icon=icon,
            achieved=ul is not None,
            progress=1.0 if ul else round(min(mm / FRUEHSTARTER_ZIEL_MM, 1.0), 4),
            parts=[Part(
                label="Warm-up",
                current_km=round(min(mm, FRUEHSTARTER_ZIEL_MM), 2),
                target_km=FRUEHSTARTER_ZIEL_MM,
            )],
            unlocked_at=ul.unlocked_at if ul else None,
            emoji=EMOJIS.get(key),
            showcased=ul.showcased if ul else None,
        )
    )

    # Early Bird: sichtbar, jede Person — Eintrag am ersten Challenge-Tag
    key, title, description, icon = EARLY_BIRD_DEF
    ul = own.get(key)
    out.append(
        AchievementOut(
            key=key,
            title=title,
            description=description,
            icon=icon,
            achieved=ul is not None,
            progress=1.0 if ul else 0.0,
            parts=[],
            unlocked_at=ul.unlocked_at if ul else None,
            emoji=EMOJIS.get(key),
            showcased=ul.showcased if ul else None,
        )
    )

    # Zeit an der Spitze: fortlaufender Timer statt Zielwert — kumulierte Zeit
    # als alleiniger Platz 1 seit Challenge-Start
    sekunden, laeuft = fuehrungs_zeit(session, user.id)
    stunden = sekunden / 3600.0
    out.append(
        AchievementOut(
            key="zeit_an_der_spitze",
            title="Zeit an der Spitze",
            description="Deine Gesamtzeit als alleiniger Platz 1 der Challenge.",
            icon="pokal",
            achieved=stunden > 0,
            progress=1.0 if stunden > 0 else 0.0,
            parts=[],
            timer_hours=round(stunden, 2),
            timer_running=laeuft,
        )
    )

    # Hidden: maskiert, solange nicht freigeschaltet (Spec §2.4)
    for key, title, description, icon in HIDDEN_DEFS:
        ul = own.get(key)
        if ul is None:
            out.append(AchievementOut(
                key=key, title="???", description="", icon="medaille",
                achieved=False, progress=0.0, parts=[], hidden=True,
            ))
        else:
            out.append(AchievementOut(
                key=key, title=title, description=description, icon=icon,
                achieved=True, progress=1.0, parts=[], hidden=True,
                unlocked_at=ul.unlocked_at, emoji=EMOJIS.get(key),
                showcased=ul.showcased,
            ))
    return out


class ShowcasePatch(BaseModel):
    showcased: bool


@router.patch("/{key}")
def patch_showcase(
    key: str,
    data: ShowcasePatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ul = session.exec(
        select(AchievementUnlock).where(
            AchievementUnlock.user_id == user.id, AchievementUnlock.key == key
        )
    ).first()
    if ul is None:
        raise HTTPException(status_code=404)
    ul.showcased = data.showcased
    session.add(ul)
    session.commit()
    return {"key": key, "showcased": ul.showcased}
