"""KM-Metriken für Wetten.

Wett-km = distance_km * Kategorie-Faktor, bewusst OHNE User.km_factor:
das Admin-Handicap gilt nur im Haupt-Ranking, Handicaps in Wetten sind
Verhandlungssache der Wettpartner (Faktoren/Vorsprung in den Wett-Params).
"""

from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta

from sqlmodel import Session, select

from ..models import Activity, Category


def scaled_km(
    session: Session, user_id: int, start: date_type, end: date_type
) -> float:
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= start,
            Activity.date <= end,
        )
    ).all()
    return round(
        sum(
            a.distance_km * cats[a.category_id].factor
            for a in acts
            if a.category_id in cats
        ),
        2,
    )


def group_scaled_km(
    session: Session, user_ids: list[int], start: date_type, end: date_type
) -> float:
    return round(sum(scaled_km(session, uid, start, end) for uid in user_ids), 2)


def longest_streak(
    session: Session, user_id: int, start: date_type, end: date_type
) -> int:
    """Längste Serie von Tagen mit >= 1 km roh im Zeitraum."""
    per_day: dict[date_type, float] = defaultdict(float)
    for a in session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= start,
            Activity.date <= end,
        )
    ).all():
        per_day[a.date] += a.distance_km
    best = run = 0
    day = start
    while day <= end:
        run = run + 1 if per_day[day] >= 1.0 else 0
        best = max(best, run)
        day += timedelta(days=1)
    return best
