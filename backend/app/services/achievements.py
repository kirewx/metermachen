"""Achievement-Definitionen + persistierte Unlocks (Spec §2).

Fortschritt wird live berechnet; beim ersten Erreichen wird ein
AchievementUnlock gespeichert (insert-or-ignore über den Unique-Constraint).
Einmal freigeschaltet bleibt freigeschaltet.
"""

import json
from collections import defaultdict
from datetime import date as date_type
from datetime import time as time_type
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import AchievementUnlock, Activity, Category, User
from .season_window import current_season, season_window

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

# Stufen-Ziele in rohen km. Gesenkt 07/2026: Gold = alte Bronze, denn mehr
# als 100 km zu schwimmen ist unrealistisch; Bronze/Silber = 25 %/50 % davon.
STUFEN_ZIELE: dict[str, dict[str, float]] = {
    RAD: {"bronze": 250.0, "silber": 500.0, "gold": 1000.0},
    LAUF: {"bronze": 60.0, "silber": 125.0, "gold": 250.0},
    SCHWIMM: {"bronze": 25.0, "silber": 50.0, "gold": 100.0},
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
    ("psychopath", "Psychopath",
     "Mehr als drei Aktivitäten zwischen 0 und 3 Uhr nachts gestartet.", "blitz"),
    ("langstreckenguru", "Langstreckenguru",
     "Über 200 MM in einer einzigen Aktivität.", "berg"),
    ("kurzstreckenprofi", "Kurzstreckenprofi",
     "Mehr als fünf Aktivitäten mit jeweils weniger als 5 MM.", "fahne"),
]

# Sichtbares Achievement, das jede Person bekommen kann (im Gegensatz zu
# EINMAL_DEFS gibt es kein Wettrennen) — Fortschritt: MM in der Warm-up-Phase.
FRUEHSTARTER_DEF = ("fruehstarter", "Frühstarter",
                    "Über 100 MM in der Warm-up-Phase getrackt.", "medaille")
FRUEHSTARTER_ZIEL_MM = 100.0

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
    "psychopath": "🔪",
    "langstreckenguru": "🛣️",
    "kurzstreckenprofi": "🐇",
    "fruehstarter": "🔥",
}

# Nachtfenster für "Psychopath": Start zwischen 00:00 (inkl.) und 03:00 (exkl.)
_NACHT_ENDE = time_type(3, 0)


def _gewertete_km(act: Activity, cats: dict[int, Category]) -> float:
    """MM einer einzelnen Aktivität: Kategorie-Faktor, ohne Admin-Handicap —
    gleiche Rechnung wie Testphasen-Sieger/Warm-up-Vergleich."""
    cat = cats.get(act.category_id)
    return act.distance_km * cat.factor if cat else 0.0


def warmup_mm(
    acts: list[Activity], cats: dict[int, Category], start: date_type
) -> float:
    """Gewertete km der Warm-up-Phase (vor Challenge-Start, im Season-Jahr)."""
    return sum(
        _gewertete_km(act, cats) for act in acts
        if act.date < start and act.date.year == start.year
    )


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

    if "psychopath" not in have:
        nachts = [
            act for act in acts
            if act.start_time is not None and act.start_time < _NACHT_ENDE
        ]
        if len(nachts) > 3 and _unlock(
            session, user_id, "psychopath", {"anzahl": len(nachts)}
        ):
            have.add("psychopath")

    if "langstreckenguru" not in have:
        treffer = next(
            (act for act in sorted(acts, key=lambda a: a.date)
             if _gewertete_km(act, cats) > 200.0),
            None,
        )
        if treffer is not None and _unlock(
            session, user_id, "langstreckenguru",
            {"datum": treffer.date.isoformat(),
             "mm": round(_gewertete_km(treffer, cats), 2)},
        ):
            have.add("langstreckenguru")

    if "kurzstreckenprofi" not in have:
        kurze = [act for act in acts if _gewertete_km(act, cats) < 5.0]
        if len(kurze) > 5 and _unlock(
            session, user_id, "kurzstreckenprofi", {"anzahl": len(kurze)}
        ):
            have.add("kurzstreckenprofi")

    # Saison-abhängige Achievements — brauchen Challenge-Start
    today = date_type.today()
    season = current_season(session)
    start = season.start_date if season else None

    # Frühstarter zählt Warm-up-MM und darf schon WÄHREND der Warm-up-Phase
    # freischalten — deshalb vor dem today<start-Guard.
    if "fruehstarter" not in have and start is not None:
        mm = warmup_mm(acts, cats, start)
        if mm > FRUEHSTARTER_ZIEL_MM and _unlock(
            session, user_id, "fruehstarter", {"mm": round(mm, 2)}
        ):
            have.add("fruehstarter")

    if start is None or today < start:
        return

    if "testphasen_sieger" not in have:
        ctx = _testphasen_platz1(session, user_id, start)
        if ctx is not None and _unlock(session, user_id, "testphasen_sieger", ctx):
            have.add("testphasen_sieger")

    if "wochenkoenig" not in have:
        _, saison_ende = season_window(season)
        bis = min(today, saison_ende) if saison_ende is not None else today
        ctx = _wochenkoenig_fenster(session, user_id, start, bis)
        if ctx is not None and _unlock(session, user_id, "wochenkoenig", ctx):
            have.add("wochenkoenig")


def _testphasen_platz1(session: Session, user_id: int, start: date_type) -> dict | None:
    """Gewertete km der Warm-up-Phase (Kategorie-Faktor, ohne Handicap) —
    gleiche Rechnung wie GET /api/comparison?phase=warmup. Bei Gleichstand
    bekommen alle Erstplatzierten das Achievement (jeweils in ihrem Lauf)."""
    aktive = {u.id for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    sums: dict[int, float] = defaultdict(float)
    for act in session.exec(select(Activity).where(Activity.date < start)).all():
        if act.user_id not in aktive or act.date.year != start.year:
            continue
        cat = cats.get(act.category_id)
        if cat is None:
            continue
        sums[act.user_id] += act.distance_km * cat.factor
    if not sums:
        return None
    best = round(max(sums.values()), 2)
    if round(sums.get(user_id, 0.0), 2) < best:
        return None
    return {"km": best}


def _wochenkoenig_fenster(
    session: Session, user_id: int, start: date_type, today: date_type
) -> dict | None:
    """Alleiniger Platz 1 der gewerteten km (Kategorie-Faktor × km_factor, wie
    Rennen-Tab) an 7 aufeinanderfolgenden Kalendertagen ab Challenge-Start.
    Geprüft gegen den aktuellen Datenstand (Spec: Randfälle)."""
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    if user_id not in users:
        return None
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    tages_km: dict[date_type, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    acts = session.exec(
        select(Activity).where(Activity.date >= start, Activity.date <= today)
    ).all()
    for act in acts:
        cat, u = cats.get(act.category_id), users.get(act.user_id)
        if cat is None or u is None:
            continue
        tages_km[act.date][act.user_id] += act.distance_km * cat.factor * u.km_factor
    kum: dict[int, float] = defaultdict(float)
    streak = 0
    d = start
    while d <= today:
        for uid, km in tages_km.get(d, {}).items():
            kum[uid] += km
        stand = {uid: round(km, 2) for uid, km in kum.items() if km > 0}
        best = max(stand.values(), default=0.0)
        fuehrende = [uid for uid, km in stand.items() if km == best]
        streak = streak + 1 if fuehrende == [user_id] else 0
        if streak >= 7:
            return {"von": (d - timedelta(days=6)).isoformat(), "bis": d.isoformat()}
        d += timedelta(days=1)
    return None
