"""Achievement-Definitionen + persistierte Unlocks (Spec §2).

Fortschritt wird live berechnet; beim ersten Erreichen wird ein
AchievementUnlock gespeichert (insert-or-ignore über den Unique-Constraint).
Einmal freigeschaltet bleibt freigeschaltet.
"""

import json
import re
from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, timezone
from datetime import time as time_type
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import (
    AchievementUnlock,
    Activity,
    Category,
    SessionParticipant,
    User,
    utcnow,
)
from .factors import FactorResolver
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

# Stufen-Ziele in rohen km. Gesenkt 07/2026 — mehr als 100 km zu schwimmen
# ist unrealistisch, die anderen Disziplinen ziehen mit.
STUFEN_ZIELE: dict[str, dict[str, float]] = {
    RAD: {"bronze": 500.0, "silber": 1000.0, "gold": 2000.0},
    LAUF: {"bronze": 100.0, "silber": 200.0, "gold": 400.0},
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
     "Sieben Tage am Stück alleiniger Platz 1 der Saison.", "pokal"),
    ("psychopath", "Psychopath",
     "Mehr als drei Aktivitäten zwischen 0 und 3 Uhr nachts gestartet.", "blitz"),
    ("langstreckenguru", "Langstreckenguru",
     "Über 200 MM in einer einzigen Aktivität.", "berg"),
    ("kurzstreckenprofi", "Kurzstreckenprofi",
     "Mehr als fünf Aktivitäten mit jeweils weniger als 5 MM.", "fahne"),
    ("dauerbrenner_bronze", "Dauerbrenner Bronze",
     "Drei Tage in Folge eine Aktivität eingetragen.", "blitz"),
    ("dauerbrenner_silber", "Dauerbrenner Silber",
     "Zwei Wochen lang jeden Tag eine Aktivität eingetragen.", "blitz"),
    ("dauerbrenner_gold", "Dauerbrenner Gold",
     "Einen Monat lang jeden Tag eine Aktivität eingetragen.", "blitz"),
    # Ausbau 10/2026
    ("fruehaufsteher", "Frühaufsteher",
     "Fünf Aktivitäten vor 6 Uhr morgens gestartet.", "blitz"),
    ("nachteule", "Nachteule",
     "Fünf Aktivitäten ab 22 Uhr gestartet.", "blitz"),
    ("allrounder", "Allrounder",
     "Vier verschiedene Kategorien in einer Kalenderwoche.", "medaille"),
    ("doppelschicht", "Doppelschicht",
     "Zwei verschiedene Kategorien an einem Tag.", "medaille"),
    ("everest", "Everest",
     "8.848 Höhenmeter insgesamt gesammelt.", "berg"),
    ("gipfelsturm", "Gipfelsturm",
     "2.000 Höhenmeter an einem Tag.", "berg"),
    ("ueberholmanoever", "Überholmanöver",
     "An einem Tag drei Leute in der Saisonwertung überholt.", "pokal"),
    ("comeback", "Comeback",
     "Nach mindestens zwei Wochen Pause wieder eine Aktivität eingetragen.", "fahne"),
    ("wochenendkrieger", "Wochenendkrieger",
     "Vier Wochenenden in Folge samstags und sonntags aktiv.", "blitz"),
    ("schnapszahl", "Schnapszahl",
     "Eine Aktivität mit genau 11,11 / 22,22 / … / 99,99 km.", "medaille"),
    ("marathon_am_stueck", "Marathon am Stück",
     "Mindestens 42,2 km in einem einzigen Lauf.", "laufen"),
    ("neujahr", "Neujahrsvorsatz",
     "Am 1. Januar eine Aktivität eingetragen.", "fahne"),
    ("der_nimmt_alles_mit", "Der nimmt alles mit",
     "Eine Aktivität unter einer Minute oder unter 100 m eingetragen.", "medaille"),
]

# Tage in Folge mit mindestens einem Eintrag, je Stufe ein eigener Unlock
STREAK_ZIELE: dict[str, int] = {
    "dauerbrenner_bronze": 3,
    "dauerbrenner_silber": 14,
    "dauerbrenner_gold": 30,
}

# Sichtbares Achievement, das jede Person bekommen kann (im Gegensatz zu
# EINMAL_DEFS gibt es kein Wettrennen) — Fortschritt: MM in der Warm-up-Phase.
FRUEHSTARTER_DEF = ("fruehstarter", "Frühstarter",
                    "Über 100 MM in der Warm-up-Phase getrackt.", "medaille")
FRUEHSTARTER_ZIEL_MM = 100.0

# Sichtbar, jede Person kann es bekommen: Eintrag am ersten Challenge-Tag.
EARLY_BIRD_DEF = ("early_bird", "Early Bird",
                  "Schon am ersten Tag der Saison eine Aktivität eingetragen.",
                  "fahne")

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
     "Platz 1 der Warm-up-Phase zum Saison-Start.", "pokal"),
]

# (key, titel, beschreibung, icon) — Together-Achievements (Spec §3.3), nur
# sichtbar/prüfbar bei aktivem Add-on `together`. Jede Person kann sie bekommen.
TOGETHER_DEFS: list[tuple[str, str, str, str]] = [
    ("together_first", "Trainingspartner",
     "Zum ersten Mal gemeinsam unterwegs gewesen.", "medaille"),
    ("together_dream_team", "Dream Team",
     "10 gemeinsame Einheiten mit derselben Person.", "medaille"),
    ("together_pack", "Rudel",
     "Eine Einheit mit mindestens 4 Leuten.", "medaille"),
    ("together_social_butterfly", "Social Butterfly",
     "Mit 5 verschiedenen Leuten gemeinsam trainiert.", "medaille"),
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
    "early_bird": "🐦",
    "dauerbrenner_bronze": "🌱",
    "dauerbrenner_silber": "🌿",
    "dauerbrenner_gold": "🌳",
    "fruehaufsteher": "🌅",
    "nachteule": "🦉",
    "allrounder": "🎨",
    "doppelschicht": "🔁",
    "everest": "🗻",
    "gipfelsturm": "⛰️",
    "ueberholmanoever": "🏎️",
    "comeback": "🔙",
    "wochenendkrieger": "⚔️",
    "schnapszahl": "🎰",
    "marathon_am_stueck": "🎽",
    "neujahr": "🎆",
    "der_nimmt_alles_mit": "🧹",
    "mm_club_1k": "⚡",
    "mm_club_5k": "🚀",
    "mm_club_10k": "🤯",
    "together_first": "🤝",
    "together_dream_team": "💞",
    "together_pack": "🐺",
    "together_social_butterfly": "🦋",
}

# MM-Club: Leiter über gewertete MM (Kategorie-Faktor, ohne Handicap), alle
# Aktivitäten. (key, stufe, titel, beschreibung, ziel_mm)
MM_CLUB_DEFS: list[tuple[str, str, str, str, float]] = [
    ("mm_club_1k", "1k", "1k MM", "1.000 MM gesammelt.", 1000.0),
    ("mm_club_5k", "5k", "5k MM", "5.000 MM gesammelt.", 5000.0),
    ("mm_club_10k", "10k", "10k MM — Insane", "10.000 MM gesammelt. Insane.", 10000.0),
]

# Zeit-Leitern je Kategorie (nur echte Dauer, duration_min). Stufen in Stunden.
ZEIT_STUFEN: tuple[int, ...] = (1, 10, 100, 1000)
ZEIT_EMOJI = "⏳"  # nur die 1000-h-Stufe


def zeit_key(category_id: int, stunden: int) -> str:
    return f"zeit_{category_id}_{stunden}h"


_ZEIT_KEY = re.compile(r"^zeit_(\d+)_(\d+)h$")

# Monatssieger: ein Unlock pro gewonnenem Monat, key "monatssieger_YYYY-MM"
MONATSSIEGER_PREFIX = "monatssieger_"
MONATSSIEGER_EMOJI = "🥇"
_MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember")


def _showcase_info() -> dict[str, tuple[str, str, str]]:
    """key -> (emoji, titel, beschreibung) für alle Emoji-Achievements."""
    titel_desc = {
        key: (titel, desc)
        for key, titel, desc, _icon in
        (*HIDDEN_DEFS, *EINMAL_DEFS, *TOGETHER_DEFS, FRUEHSTARTER_DEF, EARLY_BIRD_DEF)
    } | {key: (titel, desc) for key, _stufe, titel, desc, _ziel in MM_CLUB_DEFS}
    return {
        key: (emoji, *titel_desc[key])
        for key, emoji in EMOJIS.items()
        if key in titel_desc
    }


SHOWCASE_INFO = _showcase_info()


def achievement_info(key: str, context: dict | None = None) -> tuple[str, str | None, str]:
    """(titel, emoji|None, beschreibung) für jeden Unlock-Key — auch Stufen
    ohne Emoji. Dynamische Keys (Monatssieger, Zeit-Leitern) lesen Details
    aus dem Unlock-Kontext."""
    info = SHOWCASE_INFO.get(key)
    if info is not None:
        emoji, titel, desc = info
        return titel, emoji, desc
    if key.startswith(MONATSSIEGER_PREFIX):
        jahr, monat = key.removeprefix(MONATSSIEGER_PREFIX).split("-")
        return (
            f"Monatssieger {monat}/{jahr}",
            MONATSSIEGER_EMOJI,
            f"Die meisten MM im {_MONATE[int(monat) - 1]} {jahr}.",
        )
    m = _ZEIT_KEY.match(key)
    if m is not None:
        stunden = int(m.group(2))
        kategorie = (context or {}).get("kategorie", "Kategorie")
        return (
            f"{kategorie}: {stunden} h",
            ZEIT_EMOJI if stunden == ZEIT_STUFEN[-1] else None,
            f"{stunden} Stunden {kategorie} aufgezeichnet.",
        )
    for bucket, label in DISZIPLIN_LABEL.items():
        for tier in TIERS:
            if key == stufen_key(bucket, tier):
                ziel = STUFEN_ZIELE[bucket][tier]
                return (
                    f"{label} {tier.capitalize()}",
                    None,
                    f"{ziel:g} km {label} insgesamt gesammelt.",
                )
    return key, None, ""


def showcase_info(key: str, context: dict | None = None) -> tuple[str, str, str] | None:
    """(emoji, titel, beschreibung) für Unlocks mit Emoji, sonst None."""
    titel, emoji, desc = achievement_info(key, context)
    return (emoji, titel, desc) if emoji else None

# Nachtfenster für "Psychopath": Start zwischen 00:00 (inkl.) und 03:00 (exkl.)
_NACHT_ENDE = time_type(3, 0)

# Challenge-Tage beginnen um Mitternacht deutscher Zeit. Fester Sommerzeit-
# Offset wie in seed.py und countdown.ts — reicht, solange die Stichtage im
# Sommer liegen.
_MESZ = timezone(timedelta(hours=2))


def _gewertete_km(act: Activity, resolver: FactorResolver) -> float:
    """MM einer einzelnen Aktivität: Kategorie-Faktor (datumsabhängig), ohne
    Admin-Handicap — gleiche Rechnung wie Testphasen-Sieger/Warm-up-Vergleich."""
    return resolver.mm(act)


def warmup_mm(
    acts: list[Activity], resolver: FactorResolver, start: date_type
) -> float:
    """Gewertete km der Warm-up-Phase (vor Challenge-Start, im Season-Jahr)."""
    return sum(
        _gewertete_km(act, resolver) for act in acts
        if act.date < start and act.date.year == start.year
    )


def _existing_keys(session: Session, user_id: int) -> set[str]:
    rows = session.exec(
        select(AchievementUnlock.key).where(AchievementUnlock.user_id == user_id)
    ).all()
    return set(rows)


def _unlock(
    session: Session, user_id: int, key: str, context: dict | None = None,
    unlocked_at: datetime | None = None,
) -> bool:
    """Insert-or-ignore: Race (Webhook + Seitenaufruf) fängt der Unique-Constraint ab."""
    ul = AchievementUnlock(user_id=user_id, key=key, context_json=json.dumps(context or {}))
    if unlocked_at is not None:
        ul.unlocked_at = unlocked_at.astimezone(timezone.utc)
    session.add(ul)
    try:
        session.commit()

        from .feed import _emit

        titel, emoji, beschreibung = achievement_info(key, context)
        _emit(session, type_="achievement", user_id=user_id, payload={
            "key": key, "title": titel, "emoji": emoji,
            "description": beschreibung, "context": context or {},
        }, created_at=unlocked_at)
        return True
    except IntegrityError:
        session.rollback()
        return False


def check_unlocks(session: Session, user_id: int) -> None:
    """Prüft alle Unlock-Bedingungen für einen Nutzer und persistiert Neues.
    Idempotent; bereits vergebene Unlocks werden nie zurückgenommen."""
    have = _existing_keys(session, user_id)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    resolver = FactorResolver.load(session)
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
             if _gewertete_km(act, resolver) > 200.0),
            None,
        )
        if treffer is not None and _unlock(
            session, user_id, "langstreckenguru",
            {"datum": treffer.date.isoformat(),
             "mm": round(_gewertete_km(treffer, resolver), 2)},
        ):
            have.add("langstreckenguru")

    if "kurzstreckenprofi" not in have:
        kurze = [act for act in acts if _gewertete_km(act, resolver) < 5.0]
        if len(kurze) > 5 and _unlock(
            session, user_id, "kurzstreckenprofi", {"anzahl": len(kurze)}
        ):
            have.add("kurzstreckenprofi")

    # Dauerbrenner: längste Kette aufeinanderfolgender Kalendertage mit Eintrag
    if any(key not in have for key in STREAK_ZIELE):
        serie, von, bis = _laengste_serie(sorted({act.date for act in acts}))
        for key, ziel in STREAK_ZIELE.items():
            if key in have or serie < ziel:
                continue
            ctx = {"tage": serie, "von": von.isoformat(), "bis": bis.isoformat()}
            if _unlock(session, user_id, key, ctx):
                have.add(key)

    # MM-Club: gewertete MM aller Aktivitäten (Kategorie-Faktor, ohne Handicap)
    if any(key not in have for key, *_ in MM_CLUB_DEFS):
        mm_gesamt = sum(_gewertete_km(act, resolver) for act in acts)
        for key, _stufe, _titel, _desc, ziel in MM_CLUB_DEFS:
            if key not in have and mm_gesamt >= ziel and _unlock(
                session, user_id, key, {"mm": round(mm_gesamt, 2)}
            ):
                have.add(key)

    # Zeit-Leitern: echte Dauer je Kategorie
    for cat_id, stunden in zeit_pro_kategorie(acts).items():
        cat = cats.get(cat_id)
        if cat is None:
            continue
        for stufe in ZEIT_STUFEN:
            key = zeit_key(cat_id, stufe)
            if key in have or stunden < stufe:
                continue
            ctx = {"kategorie": cat.name, "stunden": round(stunden, 1)}
            if _unlock(session, user_id, key, ctx):
                have.add(key)

    _check_hidden_ausbau(session, user_id, acts, cats, have)

    from . import together  # function-level: together kennt achievements.check_unlocks

    if together.enabled(session):
        _check_together(session, user_id, have)

    # Saison-abhängige Achievements — brauchen Challenge-Start
    today = date_type.today()
    season = current_season(session)
    start = season.start_date if season else None

    # Frühstarter zählt Warm-up-MM und darf schon WÄHREND der Warm-up-Phase
    # freischalten — deshalb vor dem today<start-Guard.
    if "fruehstarter" not in have and start is not None:
        mm = warmup_mm(acts, resolver, start)
        if mm > FRUEHSTARTER_ZIEL_MM and _unlock(
            session, user_id, "fruehstarter", {"mm": round(mm, 2)}
        ):
            have.add("fruehstarter")

    if start is None or today < start:
        return

    if "early_bird" not in have and any(act.date == start for act in acts):
        if _unlock(session, user_id, "early_bird", {"datum": start.isoformat()}):
            have.add("early_bird")

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

    if "ueberholmanoever" not in have:
        _, saison_ende = season_window(season)
        bis = min(today, saison_ende) if saison_ende is not None else today
        ctx = _ueberhol_tag(session, user_id, start, bis)
        if ctx is not None and _unlock(session, user_id, "ueberholmanoever", ctx):
            have.add("ueberholmanoever")


def _check_together(session: Session, user_id: int, have: set[str]) -> None:
    """Together-Achievements (Spec §3.3): gezählt über echte Sessions
    (>= 2 bestätigte Teilnahmen) mit eigener `confirmed`-Teilnahme, all-time,
    nie zurückgenommen. Wird nur aufgerufen, wenn das Add-on aktiv ist."""
    mine = session.exec(
        select(SessionParticipant).where(
            SessionParticipant.user_id == user_id,
            SessionParticipant.status == "confirmed",
        )
    ).all()
    real: list[list[SessionParticipant]] = []
    for p in mine:
        confirmed = session.exec(
            select(SessionParticipant).where(
                SessionParticipant.session_id == p.session_id,
                SessionParticipant.status == "confirmed",
            )
        ).all()
        if len(confirmed) >= 2:
            real.append(confirmed)

    if "together_first" not in have and real:
        if _unlock(session, user_id, "together_first"):
            have.add("together_first")

    if "together_pack" not in have:
        if any(len(confirmed) >= 4 for confirmed in real) and _unlock(
            session, user_id, "together_pack"
        ):
            have.add("together_pack")

    partner_sessions: dict[int, int] = defaultdict(int)
    for confirmed in real:
        for p in confirmed:
            if p.user_id != user_id:
                partner_sessions[p.user_id] += 1

    if "together_dream_team" not in have:
        if any(n >= 10 for n in partner_sessions.values()) and _unlock(
            session, user_id, "together_dream_team"
        ):
            have.add("together_dream_team")

    if "together_social_butterfly" not in have:
        if len(partner_sessions) >= 5 and _unlock(
            session, user_id, "together_social_butterfly"
        ):
            have.add("together_social_butterfly")


def zeit_pro_kategorie(acts: list[Activity]) -> dict[int, float]:
    """Aufgezeichnete Stunden je Kategorie — nur Aktivitäten mit echter Dauer."""
    stunden: dict[int, float] = defaultdict(float)
    for act in acts:
        if act.duration_min:
            stunden[act.category_id] += act.duration_min / 60.0
    return stunden


_FRUEH_ENDE = time_type(6, 0)
_SPAET_START = time_type(22, 0)
_SCHNAPSZAHLEN = {f"{d}{d}.{d}{d}" for d in range(1, 10)}


def _check_hidden_ausbau(
    session: Session, user_id: int, acts: list[Activity],
    cats: dict[int, Category], have: set[str],
) -> None:
    """Hidden-Achievements aus dem Ausbau 10/2026 — reine Eigen-Daten."""

    def frei(key: str, ctx: dict | None = None) -> None:
        if _unlock(session, user_id, key, ctx):
            have.add(key)

    nach_datum = sorted(acts, key=lambda a: (a.date, a.start_time or time_type.min))

    if "fruehaufsteher" not in have:
        n = sum(1 for a in acts if a.start_time is not None and a.start_time < _FRUEH_ENDE)
        if n >= 5:
            frei("fruehaufsteher", {"anzahl": n})

    if "nachteule" not in have:
        n = sum(1 for a in acts if a.start_time is not None and a.start_time >= _SPAET_START)
        if n >= 5:
            frei("nachteule", {"anzahl": n})

    if "allrounder" not in have:
        pro_woche: dict[tuple[int, int], set[int]] = defaultdict(set)
        for a in acts:
            iso = a.date.isocalendar()
            pro_woche[(iso.year, iso.week)].add(a.category_id)
        woche = next((w for w, k in sorted(pro_woche.items()) if len(k) >= 4), None)
        if woche is not None:
            frei("allrounder", {"kw": f"{woche[0]}-W{woche[1]:02d}"})

    pro_tag_kats: dict[date_type, set[int]] = defaultdict(set)
    hm_pro_tag: dict[date_type, float] = defaultdict(float)
    for a in acts:
        pro_tag_kats[a.date].add(a.category_id)
        hm_pro_tag[a.date] += a.elevation_m or 0.0

    if "doppelschicht" not in have:
        tag = next((d for d, k in sorted(pro_tag_kats.items()) if len(k) >= 2), None)
        if tag is not None:
            frei("doppelschicht", {"datum": tag.isoformat()})

    if "everest" not in have:
        hm = sum(hm_pro_tag.values())
        if hm >= 8848.0:
            frei("everest", {"hm": round(hm, 1)})

    if "gipfelsturm" not in have:
        tag = next((d for d, hm in sorted(hm_pro_tag.items()) if hm >= 2000.0), None)
        if tag is not None:
            frei("gipfelsturm", {"datum": tag.isoformat(), "hm": round(hm_pro_tag[tag], 1)})

    tage = sorted(pro_tag_kats)
    if "comeback" not in have:
        paar = next(
            ((a, b) for a, b in zip(tage, tage[1:]) if b - a >= timedelta(days=15)), None
        )
        if paar is not None:
            frei("comeback", {"pause_tage": (paar[1] - paar[0]).days - 1,
                              "datum": paar[1].isoformat()})

    if "wochenendkrieger" not in have:
        aktiv = set(tage)
        samstage = sorted(
            d for d in aktiv if d.weekday() == 5 and d + timedelta(days=1) in aktiv
        )
        voll = set(samstage)
        start = next(
            (s for s in samstage
             if all(s + timedelta(weeks=w) in voll for w in range(1, 4))),
            None,
        )
        if start is not None:
            frei("wochenendkrieger", {"von": start.isoformat(),
                                      "bis": (start + timedelta(weeks=3, days=1)).isoformat()})

    def erste(bedingung) -> Activity | None:
        return next((a for a in nach_datum if bedingung(a)), None)

    if "schnapszahl" not in have:
        a = erste(lambda a: f"{a.distance_km:.2f}" in _SCHNAPSZAHLEN)
        if a is not None:
            frei("schnapszahl", {"datum": a.date.isoformat(), "km": a.distance_km})

    if "marathon_am_stueck" not in have:
        def ist_marathon(a: Activity) -> bool:
            cat = cats.get(a.category_id)
            return (cat is not None and bucket_for_category(cat) == LAUF
                    and a.distance_km >= 42.2)
        a = erste(ist_marathon)
        if a is not None:
            frei("marathon_am_stueck", {"datum": a.date.isoformat(), "km": a.distance_km})

    if "neujahr" not in have:
        a = erste(lambda a: a.date.month == 1 and a.date.day == 1)
        if a is not None:
            frei("neujahr", {"datum": a.date.isoformat()})

    if "der_nimmt_alles_mit" not in have:
        a = erste(lambda a: a.distance_km < 0.1
                  or (a.duration_min is not None and a.duration_min <= 1))
        if a is not None:
            frei("der_nimmt_alles_mit", {"datum": a.date.isoformat(), "km": a.distance_km})


def _ueberhol_tag(
    session: Session, user_id: int, start: date_type, today: date_type
) -> dict | None:
    """Erster Tag, an dem die Person mindestens drei andere in der Saison-
    wertung (gewertete km × km_factor, wie Rennen-Tab) überholt hat: vor dem
    Tag echt dahinter, am Tagesende echt davor."""
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    if user_id not in users:
        return None
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    resolver = FactorResolver.load(session)
    tages_km: dict[date_type, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for act in session.exec(
        select(Activity).where(Activity.date >= start, Activity.date <= today)
    ).all():
        u = users.get(act.user_id)
        if u is None or act.category_id not in cats:
            continue
        tages_km[act.date][act.user_id] += resolver.mm(act) * u.km_factor
    kum: dict[int, float] = defaultdict(float)
    for d in sorted(tages_km):
        vorher = {uid: round(km, 2) for uid, km in kum.items()}
        for uid, km in tages_km[d].items():
            kum[uid] += km
        if user_id not in tages_km[d]:
            continue
        ich_vorher = vorher.get(user_id, 0.0)
        ich = round(kum[user_id], 2)
        ueberholt = [
            uid for uid in users
            if uid != user_id
            and vorher.get(uid, 0.0) > ich_vorher
            and round(kum.get(uid, 0.0), 2) < ich
        ]
        if len(ueberholt) >= 3:
            return {"datum": d.isoformat(), "anzahl": len(ueberholt)}
    return None


def ensure_monatssieger(session: Session, now: datetime | None = None) -> None:
    """Vergibt für jeden abgeschlossenen Saisonmonat (ab Challenge-Start) den
    Monatssieger: meiste MM im Monat, Wertung wie Rennen-Tab inkl. Handicap.
    Fällig am Monatsersten 00:00 deutscher Zeit (= unlocked_at), bei
    Gleichstand alle Erstplatzierten. Lazy + idempotent, auch rückwirkend."""
    season = current_season(session)
    if season is None or season.start_date is None:
        return
    now = (now or datetime.now(tz=_MESZ)).astimezone(_MESZ)
    _, saison_ende = season_window(season)
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    resolver: FactorResolver | None = None

    erster = season.start_date.replace(day=1)
    while saison_ende is None or erster <= saison_ende:
        naechster = (erster.replace(day=28) + timedelta(days=4)).replace(day=1)
        faellig = datetime.combine(naechster, time_type(0, 0), tzinfo=_MESZ)
        if faellig > now:
            break
        key = f"{MONATSSIEGER_PREFIX}{erster:%Y-%m}"
        vergeben = session.exec(
            select(AchievementUnlock).where(AchievementUnlock.key == key)
        ).first()
        if vergeben is None:
            von = max(erster, season.start_date)
            bis = naechster - timedelta(days=1)
            if saison_ende is not None:
                bis = min(bis, saison_ende)
            resolver = resolver or FactorResolver.load(session)
            mm: dict[int, float] = defaultdict(float)
            for a in session.exec(
                select(Activity).where(Activity.date >= von, Activity.date <= bis)
            ).all():
                if a.user_id in users and a.category_id in cats:
                    mm[a.user_id] += resolver.mm(a) * users[a.user_id].km_factor
            stand = {uid: round(km, 2) for uid, km in mm.items() if km > 0}
            best = max(stand.values(), default=0.0)
            for uid in sorted(uid for uid, km in stand.items() if km == best and best > 0):
                _unlock(session, uid, key, {"monat": f"{erster:%Y-%m}", "mm": best},
                        unlocked_at=faellig)
        erster = naechster


def _laengste_serie(
    tage: list[date_type],
) -> tuple[int, date_type | None, date_type | None]:
    """Längste Kette aufeinanderfolgender Kalendertage: (länge, von, bis)."""
    beste, beste_bis = 0, None
    lauf, prev = 0, None
    for d in tage:
        lauf = lauf + 1 if prev is not None and d - prev == timedelta(days=1) else 1
        prev = d
        if lauf > beste:
            beste, beste_bis = lauf, d
    if beste_bis is None:
        return 0, None, None
    return beste, beste_bis - timedelta(days=beste - 1), beste_bis


def fuehrungs_zeit(session: Session, user_id: int) -> tuple[float, bool]:
    """Kumulierte Sekunden als alleiniger Platz 1 der Challenge (gewertete km
    wie im Rennen-Tab), rekonstruiert über die Eintrags-Zeitpunkte (created_at).
    Löschen/Editieren verschiebt die Historie rückwirkend — für einen
    fortlaufenden Timer akzeptabel. Rückgabe: (sekunden, läuft gerade)."""
    season = current_season(session)
    start = season.start_date if season else None
    if start is None:
        return 0.0, False
    start_dt = datetime.combine(start, time_type.min, tzinfo=_MESZ)
    jetzt = utcnow()
    _, saison_ende = season_window(season)
    bis = jetzt
    if saison_ende is not None:
        ende_dt = datetime.combine(
            saison_ende + timedelta(days=1), time_type.min, tzinfo=_MESZ
        )
        bis = min(jetzt, ende_dt)
    if bis <= start_dt:
        return 0.0, False

    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    if user_id not in users:
        return 0.0, False
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    resolver = FactorResolver.load(session)
    stmt = select(Activity).where(Activity.date >= start)
    if saison_ende is not None:
        stmt = stmt.where(Activity.date <= saison_ende)
    acts = [
        a for a in session.exec(stmt).all()
        if a.user_id in users and a.category_id in cats
    ]

    def eintrag_zeit(a: Activity) -> datetime:
        t = a.created_at
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return min(max(t, start_dt), bis)

    acts.sort(key=eintrag_zeit)
    kum: dict[int, float] = defaultdict(float)
    vorn: int | None = None
    prev = start_dt
    sekunden = 0.0
    for a in acts:
        t = eintrag_zeit(a)
        if vorn == user_id:
            sekunden += (t - prev).total_seconds()
        prev = t
        kum[a.user_id] += resolver.mm(a) * users[a.user_id].km_factor
        stand = {uid: round(km, 2) for uid, km in kum.items() if km > 0}
        best = max(stand.values(), default=0.0)
        fuehrende = [uid for uid, km in stand.items() if km == best]
        vorn = fuehrende[0] if len(fuehrende) == 1 else None
    if vorn == user_id:
        sekunden += (bis - prev).total_seconds()
    return sekunden, vorn == user_id and bis == jetzt


def _testphasen_platz1(session: Session, user_id: int, start: date_type) -> dict | None:
    """Gewertete km der Warm-up-Phase (Kategorie-Faktor, ohne Handicap) —
    gleiche Rechnung wie GET /api/comparison?phase=warmup. Bei Gleichstand
    bekommen alle Erstplatzierten das Achievement (jeweils in ihrem Lauf)."""
    aktive = {u.id for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    resolver = FactorResolver.load(session)
    sums: dict[int, float] = defaultdict(float)
    for act in session.exec(select(Activity).where(Activity.date < start)).all():
        if act.user_id not in aktive or act.date.year != start.year:
            continue
        cat = cats.get(act.category_id)
        if cat is None:
            continue
        sums[act.user_id] += resolver.mm(act)
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
    resolver = FactorResolver.load(session)
    tages_km: dict[date_type, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    acts = session.exec(
        select(Activity).where(Activity.date >= start, Activity.date <= today)
    ).all()
    for act in acts:
        cat, u = cats.get(act.category_id), users.get(act.user_id)
        if cat is None or u is None:
            continue
        tages_km[act.date][act.user_id] += resolver.mm(act) * u.km_factor
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
