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
from datetime import timedelta

from sqlmodel import Session, select

from ..models import Activity, Category, Challenge


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
