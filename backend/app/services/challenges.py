"""Challenges: Metriken, Stand, Lebenszyklus (Spec 2026-08-04).

Der Stand wird zur Lesezeit aus den Activities gerechnet, solange die
Challenge laeuft — genau wie compute_comparison. Dadurch ziehen Strava-
Nachzuegler und Korrekturen automatisch mit und es braucht keinen Cron.
Erst beim Einfrieren wird das Ergebnis in result_json festgeschrieben.

Alle Metriken rechnen ohne User.km_factor: das Admin-Handicap gilt nur im
Saison-Ranking, eine 300-MM-Huerde soll fuer alle dieselbe Huerde sein.
"""

import json
from datetime import date as date_type

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


def metric_value(
    session: Session, user_id: int, ch: Challenge, heute: date_type | None = None
) -> float:
    if ch.metric == "mm":
        return metric_mm(session, user_id, ch)
    raise ValueError(f"Unbekannte Metrik: {ch.metric}")
