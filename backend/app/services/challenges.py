"""Challenges: Metriken, Stand, Lebenszyklus (Spec 2026-08-04).

Der Stand wird zur Lesezeit aus den Activities gerechnet, solange die
Challenge laeuft — genau wie compute_comparison. Dadurch ziehen Strava-
Nachzuegler und Korrekturen automatisch mit und es braucht keinen Cron.
Erst beim Einfrieren wird das Ergebnis in result_json festgeschrieben.

Alle Metriken rechnen ohne User.km_factor: das Admin-Handicap gilt nur im
Saison-Ranking, eine 300-MM-Huerde soll fuer alle dieselbe Huerde sein.
"""

import json
from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from datetime import time as time_type

from sqlmodel import Session, select

from ..models import Activity, Category, Challenge, ChallengeParticipant, User
from . import feed

# Karenz nach Challenge-Ende: Einfrieren erst am Folgetag um 06:00 deutscher
# Zeit. Deckt einen ausstehenden Strava-Sync und eine Aktivitaet kurz vor
# Mitternacht ab, die erst am naechsten Morgen eingetragen wird.
KARENZ_STUNDE = 6
# Fester Sommerzeit-Offset wie in services/feed.py und services/achievements.py.
_MESZ = timezone(timedelta(hours=2))


def category_ids(ch: Challenge) -> list[int]:
    """Leere Liste = alle Kategorien."""
    return json.loads(ch.category_ids_json or "[]")


def _rows(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> list[tuple[Activity, Category]]:
    """Aktivitaeten des Users im Challenge-Zeitraum, Kategorie-gefiltert."""
    erlaubt = set(category_ids(ch))
    ende = ch.period_end if bis is None else min(ch.period_end, bis)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= ch.period_start,
            Activity.date <= ende,
        )
    ).all()
    return [
        (a, cats[a.category_id])
        for a in acts
        if a.category_id in cats and (not erlaubt or a.category_id in erlaubt)
    ]


def metric_mm(session: Session, user_id: int, ch: Challenge) -> float:
    return round(sum(a.distance_km * c.factor for a, c in _rows(session, user_id, ch)), 2)


def metric_anzahl(session: Session, user_id: int, ch: Challenge) -> int:
    return len(_rows(session, user_id, ch))


def per_day(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> dict[date_type, float]:
    """MM je Kalendertag im Zeitraum (Kategorie-gefiltert)."""
    tage: dict[date_type, float] = defaultdict(float)
    for a, c in _rows(session, user_id, ch, bis):
        tage[a.date] += a.distance_km * c.factor
    return tage


def laengste_serie(
    tage: dict[date_type, float], von: date_type, bis: date_type, min_mm: float
) -> int:
    best = run = 0
    tag = von
    while tag <= bis:
        run = run + 1 if tage.get(tag, 0.0) >= min_mm else 0
        best = max(best, run)
        tag += timedelta(days=1)
    return best


def serie_endend_am(
    tage: dict[date_type, float], von: date_type, bis: date_type, min_mm: float
) -> int:
    """Laenge der Serie, die genau am Tag `bis` endet. 0, wenn `bis` nicht zaehlt."""
    run = 0
    tag = bis
    while tag >= von and tage.get(tag, 0.0) >= min_mm:
        run += 1
        tag -= timedelta(days=1)
    return run


def metric_streak(
    session: Session, user_id: int, ch: Challenge, heute: date_type
) -> int:
    bis = min(heute, ch.period_end)
    if bis < ch.period_start:
        return 0
    return laengste_serie(
        per_day(session, user_id, ch, bis), ch.period_start, bis, ch.streak_min_mm
    )


def metric_value(
    session: Session, user_id: int, ch: Challenge, heute: date_type | None = None
) -> float:
    heute = heute or date_type.today()
    if ch.metric == "mm":
        return metric_mm(session, user_id, ch)
    if ch.metric == "anzahl":
        return metric_anzahl(session, user_id, ch)
    if ch.metric == "streak":
        return metric_streak(session, user_id, ch, heute)
    raise ValueError(f"Unbekannte Metrik: {ch.metric}")


def streak_noch_moeglich(
    session: Session, user_id: int, ch: Challenge, heute: date_type
) -> bool:
    """False, sobald das Streak-Ziel rechnerisch nicht mehr erreichbar ist.

    Gilt nur fuer mode='ziel' + metric='streak' — bei mm/anzahl gibt es kein
    Tageslimit, dort ist Unmoeglichkeit nie beweisbar.
    """
    if ch.mode != "ziel" or ch.metric != "streak" or ch.target is None:
        return True
    if heute < ch.period_start:
        return True
    bis = min(heute, ch.period_end)
    tage = per_day(session, user_id, ch, ch.period_end)
    beste = laengste_serie(tage, ch.period_start, bis, ch.streak_min_mm)
    if beste >= ch.target:
        return True
    gestern = min(heute - timedelta(days=1), ch.period_end)
    laufend = (
        serie_endend_am(tage, ch.period_start, gestern, ch.streak_min_mm)
        if gestern >= ch.period_start
        else 0
    )
    resttage = max((ch.period_end - heute).days + 1, 0)
    return laufend + resttage >= ch.target


def teilnehmer_ids(session: Session, ch: Challenge) -> list[int]:
    """Bei 'auto' alle aktiven User, bei 'opt_in' die Beigetretenen.
    Inaktive User fallen in beiden Faellen raus."""
    aktive = {
        u.id for u in session.exec(select(User).where(User.is_active)).all()
    }
    if ch.join_mode == "auto":
        return sorted(aktive)
    rows = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id
        )
    ).all()
    return sorted(r.user_id for r in rows if r.user_id in aktive)


def standings(
    session: Session, ch: Challenge, heute: date_type | None = None
) -> list[dict]:
    """Aktueller Stand, absteigend nach Wert. Gleichstand teilt sich den Rang,
    der Folgerang wird uebersprungen (1, 2, 2, 4)."""
    heute = heute or date_type.today()
    eintraege = [
        {
            "user_id": uid,
            "value": metric_value(session, uid, ch, heute),
            "rank": 0,
            "geschafft": False,
            "nicht_mehr_schaffbar": False,
        }
        for uid in teilnehmer_ids(session, ch)
    ]
    eintraege.sort(key=lambda e: (-e["value"], e["user_id"]))

    letzter_wert = None
    letzter_rang = 0
    for i, e in enumerate(eintraege, start=1):
        if letzter_wert is not None and e["value"] == letzter_wert:
            e["rank"] = letzter_rang
        else:
            e["rank"] = i
            letzter_rang = i
            letzter_wert = e["value"]

    for e in eintraege:
        if ch.mode == "ziel":
            e["geschafft"] = ch.target is not None and e["value"] >= ch.target
            if not e["geschafft"]:
                e["nicht_mehr_schaffbar"] = not streak_noch_moeglich(
                    session, e["user_id"], ch, heute
                )
        else:
            e["geschafft"] = e["rank"] <= ch.top_n
    return eintraege


def freeze_at(ch: Challenge) -> datetime:
    """UTC-Zeitpunkt, ab dem das Ergebnis feststeht."""
    tag = ch.period_end + timedelta(days=1)
    return datetime.combine(
        tag, time_type(KARENZ_STUNDE, 0), tzinfo=_MESZ
    ).astimezone(timezone.utc)


def ist_vorlaeufig(ch: Challenge, heute: date_type) -> bool:
    """Zeitraum vorbei, Ergebnis aber noch nicht eingefroren."""
    return ch.status == "laufend" and heute > ch.period_end


def _einfrieren(session: Session, ch: Challenge, jetzt: datetime, heute: date_type) -> None:
    eintraege = standings(session, ch, heute)
    gewinner = [e["user_id"] for e in eintraege if e["geschafft"]]
    ch.result_json = json.dumps(
        {
            "entries": [
                {k: e[k] for k in ("user_id", "value", "rank", "geschafft")}
                for e in eintraege
            ],
            "gewinner_ids": gewinner,
        }
    )
    ch.status = "beendet"
    ch.resolved_at = jetzt
    session.add(ch)
    session.commit()
    feed.challenge_end_event(session, ch, gewinner)


def resolve_due(session: Session, jetzt: datetime | None = None) -> None:
    """Faellige Statusuebergaenge, lazy beim Request — kein Cron.
    Gleiches Muster wie bets.resolve_due."""
    jetzt = jetzt or datetime.now(timezone.utc)
    heute = jetzt.astimezone(_MESZ).date()

    for ch in session.exec(
        select(Challenge).where(Challenge.status == "geplant").order_by(Challenge.id)
    ).all():
        if heute >= ch.period_start:
            ch.status = "laufend"
            session.add(ch)
            session.commit()
            feed.challenge_start_event(session, ch)

    for ch in session.exec(
        select(Challenge).where(Challenge.status == "laufend").order_by(Challenge.id)
    ).all():
        if jetzt >= freeze_at(ch):
            _einfrieren(session, ch, jetzt, heute)


def emit_qualified(session: Session, ch: Challenge, eintraege: list[dict]) -> None:
    """Feed-Event fuer alle, die das Ziel geknackt haben. Idempotent."""
    if ch.mode != "ziel" or ch.status != "laufend":
        return
    for e in eintraege:
        if e["geschafft"]:
            feed.challenge_qualified_event(session, ch, e["user_id"])


class NichtQualifiziert(ValueError):
    """Sieger steht nicht auf der Liste der Qualifizierten — 422, nicht 409."""


def sieger_id(ch: Challenge) -> int | None:
    return json.loads(ch.result_json or "{}").get("sieger", {}).get("user_id")


def setze_sieger(
    session: Session, ch: Challenge, user_id: int, jetzt: datetime
) -> None:
    """Traegt den offline ermittelten Preistraeger ein. Ueberschreibbar —
    anders als eine Auslosung ist das ein festgehaltener Fakt, und ein
    Vertipper muss sich korrigieren lassen."""
    if ch.mode != "ziel":
        raise ValueError("Ranglisten haben ihren Sieger bereits")
    if ch.status != "beendet":
        raise ValueError("Erst nach dem Ende der Challenge")
    ergebnis = json.loads(ch.result_json or "{}")
    if user_id not in ergebnis.get("gewinner_ids", []):
        raise NichtQualifiziert("Diese Person hat das Ziel nicht erreicht")
    ergebnis["sieger"] = {"user_id": user_id, "gesetzt_am": jetzt.isoformat()}
    ch.result_json = json.dumps(ergebnis)
    session.add(ch)
    session.commit()
    feed.challenge_sieger_event(session, ch, user_id)
