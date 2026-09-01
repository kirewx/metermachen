"""Zeitversionierte Kategorie-Faktoren (Spec 2026-09-01).

Der Faktor einer Aktivität richtet sich nach ihrem DATUM: Es gilt die
CategoryFactorChange-Zeile mit dem jüngsten valid_from <= Datum, davor der
Ur-Faktor Category.factor. Änderungen wirken nie rückwirkend. Dieser
Resolver ist die einzige Stelle, die Faktoren auflöst — Berechnungen
multiplizieren nirgendwo mehr direkt mit Category.factor.
"""

from bisect import bisect_right
from datetime import date as date_type

from sqlmodel import Session, select

from ..models import Activity, Category, CategoryFactorChange


class FactorResolver:
    def __init__(
        self,
        categories: list[Category],
        changes: list[CategoryFactorChange],
    ) -> None:
        self._base = {c.id: c.factor for c in categories}
        self._changes: dict[int, tuple[list[date_type], list[float]]] = {}
        for ch in sorted(changes, key=lambda c: (c.category_id, c.valid_from)):
            dates, factors = self._changes.setdefault(ch.category_id, ([], []))
            dates.append(ch.valid_from)
            factors.append(ch.factor)

    @classmethod
    def load(cls, session: Session) -> "FactorResolver":
        return cls(
            list(session.exec(select(Category)).all()),
            list(session.exec(select(CategoryFactorChange)).all()),
        )

    def factor(self, category_id: int, on: date_type) -> float:
        dates, factors = self._changes.get(category_id, ([], []))
        i = bisect_right(dates, on)
        if i:
            return factors[i - 1]
        return self._base.get(category_id, 0.0)

    def mm(self, act: Activity) -> float:
        return act.distance_km * self.factor(act.category_id, act.date)
