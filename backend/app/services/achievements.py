"""Achievement-Definitionen + persistierte Unlocks (Spec §2).

Fortschritt wird live berechnet; beim ersten Erreichen wird ein
AchievementUnlock gespeichert (insert-or-ignore über den Unique-Constraint).
Einmal freigeschaltet bleibt freigeschaltet.
"""

import json
from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import AchievementUnlock, Activity, Category, Season, User

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


DISZIPLIN_LABEL = {RAD: "Rad", LAUF: "Laufen", SCHWIMM: "Schwimmen"}
DISZIPLIN_ICON = {RAD: "rad", LAUF: "laufen", SCHWIMM: "schwimmen"}
TIERS = ("bronze", "silber", "gold")

# Stufen-Ziele in rohen km (Spec §2.3)
STUFEN_ZIELE: dict[str, dict[str, float]] = {
    RAD: {"bronze": 1000.0, "silber": 2500.0, "gold": 4000.0},
    LAUF: {"bronze": 250.0, "silber": 500.0, "gold": 1000.0},
    SCHWIMM: {"bronze": 100.0, "silber": 250.0, "gold": 400.0},
}


def stufen_key(bucket: str, tier: str) -> str:
    return f"stufe_{bucket}_{tier}"


def erster_key(bucket: str) -> str:
    return f"erster_gold_{bucket}"


# (key, titel, beschreibung, icon) — nur für die eigene Person maskiert, solange
# nicht freigeschaltet (Spec §2.3/§2.4)
HIDDEN_DEFS: list[tuple[str, str, str, str]] = [
    ("kletterkoenig", "Kletterkönig", "1000 Höhenmeter an einem Tag.", "berg"),
    ("hattrick", "Hattrick", "Drei Aktivitäten an einem Tag.", "blitz"),
    ("wochenkoenig", "Wochenkönig",
     "Sieben Tage am Stück alleiniger Platz 1 der Challenge.", "pokal"),
]

# (key, titel, beschreibung, icon) — bekommt genau eine Person (bzw. bei
# Gleichstand im Testphasen-Sieg alle Erstplatzierten)
EINMAL_DEFS: list[tuple[str, str, str, str]] = [
    ("erster_gold_rad", "Erster: Rad Gold",
     "Bekommt nur, wer die Gold-Stufe Rad als erste Person knackt.", "rad"),
    ("erster_gold_lauf", "Erster: Laufen Gold",
     "Bekommt nur, wer die Gold-Stufe Laufen als erste Person knackt.", "laufen"),
    ("erster_gold_schwimm", "Erster: Schwimmen Gold",
     "Bekommt nur, wer die Gold-Stufe Schwimmen als erste Person knackt.", "schwimmen"),
    ("testphasen_sieger", "Testphasen-Sieger",
     "Platz 1 der Warm-up-Phase zum Challenge-Start.", "pokal"),
]

# Special-Emojis (Spec §2.6). Stufen vergeben bewusst KEIN Emoji.
EMOJIS: dict[str, str] = {
    "testphasen_sieger": "🏆",
    "erster_gold_rad": "🚴",
    "erster_gold_lauf": "🏃",
    "erster_gold_schwimm": "🏊",
    "kletterkoenig": "🏔️",
    "hattrick": "🎩",
    "wochenkoenig": "👑",
}


def _existing_keys(session: Session, user_id: int) -> set[str]:
    rows = session.exec(
        select(AchievementUnlock.key).where(AchievementUnlock.user_id == user_id)
    ).all()
    return set(rows)


def _unlock(session: Session, user_id: int, key: str, context: dict | None = None) -> bool:
    """Insert-or-ignore: Race (Webhook + Seitenaufruf) fängt der Unique-Constraint ab."""
    session.add(AchievementUnlock(
        user_id=user_id, key=key, context_json=json.dumps(context or {})
    ))
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False


def check_unlocks(session: Session, user_id: int) -> None:
    """Prüft alle Unlock-Bedingungen für einen Nutzer und persistiert Neues.
    Idempotent; bereits vergebene Unlocks werden nie zurückgenommen."""
    have = _existing_keys(session, user_id)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(select(Activity).where(Activity.user_id == user_id)).all()

    # Stufen (rohe km je Bucket) + Erster-Bonus direkt nach dem Gold-Insert
    bucket_km: dict[str, float] = defaultdict(float)
    for act in acts:
        cat = cats.get(act.category_id)
        bucket = bucket_for_category(cat) if cat else None
        if bucket is not None:
            bucket_km[bucket] += act.distance_km
    for bucket, ziele in STUFEN_ZIELE.items():
        for tier in TIERS:
            key = stufen_key(bucket, tier)
            if key in have or bucket_km[bucket] < ziele[tier]:
                continue
            if _unlock(session, user_id, key, {"km": round(bucket_km[bucket], 2)}):
                have.add(key)
                if tier == "gold":
                    schon_vergeben = session.exec(
                        select(AchievementUnlock).where(
                            AchievementUnlock.key == erster_key(bucket)
                        )
                    ).first()
                    if schon_vergeben is None and _unlock(session, user_id, erster_key(bucket)):
                        have.add(erster_key(bucket))

    # Hidden: Tagesgrenzen über das Aktivitätsdatum (Kalendertag)
    if "kletterkoenig" not in have:
        hm_pro_tag: dict[date_type, float] = defaultdict(float)
        for act in acts:
            hm_pro_tag[act.date] += act.elevation_m or 0.0
        tag = next((d for d, hm in sorted(hm_pro_tag.items()) if hm >= 1000.0), None)
        if tag is not None and _unlock(
            session, user_id, "kletterkoenig",
            {"datum": tag.isoformat(), "hm": round(hm_pro_tag[tag], 1)},
        ):
            have.add("kletterkoenig")

    if "hattrick" not in have:
        eintraege_pro_tag: dict[date_type, int] = defaultdict(int)
        for act in acts:
            eintraege_pro_tag[act.date] += 1
        tag = next((d for d, n in sorted(eintraege_pro_tag.items()) if n >= 3), None)
        if tag is not None and _unlock(
            session, user_id, "hattrick", {"datum": tag.isoformat()}
        ):
            have.add("hattrick")
