"""Zeitversionierte Kategorie-Faktoren (Spec 2026-09-01).

Der Faktor einer Aktivität richtet sich nach ihrem DATUM: Es gilt die
CategoryFactorChange-Zeile mit dem jüngsten valid_from <= Datum, davor der
Ur-Faktor Category.factor. Änderungen wirken nie rückwirkend. Dieser
Resolver ist die einzige Stelle, die Faktoren auflöst — Berechnungen
multiplizieren nirgendwo mehr direkt mit Category.factor.

Höhenmeter (Spec 2026-11-03): Ab HM_AB zählen je HM_PRO_KM Höhenmeter wie
1 km, danach greift der Kategorie-Faktor — MM = (km + hm / 100) × Faktor.
Kategorien mit counts_elevation=False (E-Bike) bleiben bei km × Faktor.
Wie Faktor-Änderungen nie rückwirkend: Aktivitäten vor HM_AB zählen ohne hm.
"""

from bisect import bisect_right
from datetime import date as date_type

from sqlmodel import Session, select

from ..models import Activity, Category, CategoryFactorChange

HM_PRO_KM = 100.0
HM_AB = date_type(2026, 11, 9)


class FactorResolver:
    def __init__(
        self,
        categories: list[Category],
        changes: list[CategoryFactorChange],
    ) -> None:
        self._base = {c.id: c.factor for c in categories}
        self._hm = {c.id for c in categories if c.counts_elevation}
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

    def km(self, act: Activity) -> float:
        """Distanz inkl. Höhenmeter-Bonus, noch ohne Kategorie-Faktor."""
        if act.elevation_m and act.category_id in self._hm and act.date >= HM_AB:
            return act.distance_km + act.elevation_m / HM_PRO_KM
        return act.distance_km

    def mm(self, act: Activity) -> float:
        return self.km(act) * self.factor(act.category_id, act.date)
