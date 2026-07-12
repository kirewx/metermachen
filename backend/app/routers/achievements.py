"""Achievements: kleine Erfolge über kumulierte (rohe, ungewertete) Kilometer.

Aktivitäten hängen an frei konfigurierbaren Kategorien, Achievements aber an
Sportarten. Die Zuordnung Kategorie -> Sport-Bucket läuft über drei Signale
(Icon, gemappte Strava-Sportarten, Name), damit sie auch nach Umbenennungen
oder bei selbst angelegten Kategorien greift.
"""

import json
from collections import defaultdict
from datetime import date as date_type

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, Season, User

router = APIRouter(prefix="/api/achievements", tags=["achievements"])

RAD, LAUF, SCHWIMM = "rad", "lauf", "schwimm"

_BUCKET_BY_ICON = {"rad": RAD, "laufen": LAUF, "schwimmen": SCHWIMM}
_BUCKET_BY_STRAVA = {
    "Ride": RAD, "MountainBikeRide": RAD, "GravelRide": RAD, "EBikeRide": RAD,
    "VirtualRide": RAD,
    "Run": LAUF, "TrailRun": LAUF, "VirtualRun": LAUF,
    "Swim": SCHWIMM,
}
_BUCKET_BY_NAME = {RAD: ("rad", "bike"), LAUF: ("lauf", "jogg"), SCHWIMM: ("schwimm",)}


def bucket_for_category(cat: Category) -> str | None:
    if cat.icon in _BUCKET_BY_ICON:
        return _BUCKET_BY_ICON[cat.icon]
    for sport in json.loads(cat.strava_sport_types or "[]"):
        if sport in _BUCKET_BY_STRAVA:
            return _BUCKET_BY_STRAVA[sport]
    name = cat.name.lower()
    for bucket, needles in _BUCKET_BY_NAME.items():
        if any(n in name for n in needles):
            return bucket
    return None


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
    season = session.exec(select(Season).where(Season.year == today.year)).first()
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
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    sums: dict[str, float] = defaultdict(float)
    for act in session.exec(select(Activity).where(Activity.user_id == user.id)).all():
        sums["gesamt"] += act.distance_km
        cat = cats.get(act.category_id)
        bucket = bucket_for_category(cat) if cat else None
        if bucket is not None:
            sums[bucket] += act.distance_km

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
    return out
