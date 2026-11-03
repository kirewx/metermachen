"""Zeitversionierte Kategorie-Faktoren (Spec 2026-09-01).

Der Faktor einer Aktivität richtet sich nach ihrem DATUM: Es gilt die
CategoryFactorChange-Zeile mit dem jüngsten valid_from <= Datum, davor der
Ur-Faktor Category.factor. Änderungen wirken nie rückwirkend. Dieser
Resolver ist die einzige Stelle, die Faktoren auflöst — Berechnungen
multiplizieren nirgendwo mehr direkt mit Category.factor.

Höhenmeter (Spec 2026-11-03): Zählt eine Kategorie Höhenmeter, gelten je
HM_PRO_KM Höhenmeter wie 1 km, danach greift der Kategorie-Faktor —
MM = (km + hm / 100) × Faktor. Ob eine Kategorie Höhenmeter zählt, ist wie
der Faktor zeitversioniert: CategoryElevationChange mit dem jüngsten
valid_from <= Datum, davor Category.counts_elevation. Der Admin-Schalter
legt eine Änderung ab heute an (elevation_start) — nie rückwirkend.
"""

from bisect import bisect_right
from datetime import date as date_type

from sqlmodel import Session, select

from ..models import Activity, Category, CategoryElevationChange, CategoryFactorChange

HM_PRO_KM = 100.0
# Frühester Start der Höhenmeter-Wertung. Läuft der Deploy später, beginnt
# sie am Deploy-Tag (elevation_start) — die Migration schreibt das Datum fest.
HM_AB = date_type(2026, 11, 5)


def elevation_start(today: date_type | None = None) -> date_type:
    """Ab wann eine heute angelegte Höhenmeter-Änderung gilt."""
    return max(HM_AB, today or date_type.today())

# Standard für counts_elevation: nur Draußen-Fortbewegung, bei der man
# Höhenmeter selbst macht. Alles andere (Schwimmen, Tanzen, Tennis, Ski mit
# Lift, E-Bike, Indoor, unbekannt) startet aus — Admin kann umschalten.
_HM_SPORTS = {
    "Run", "TrailRun", "Walk", "Hike", "Ride", "MountainBikeRide", "GravelRide",
    "InlineSkate", "Skateboard", "NordicSki", "BackcountrySki", "Snowshoe",
}
_HM_ICONS = {"laufen", "gehen", "wandern", "rad", "inline"}
_NO_HM_SPORTS = {"EBikeRide", "EMountainBikeRide", "VirtualRide", "VirtualRun"}


def default_counts_elevation(name: str, icon: str, sports: list[str]) -> bool:
    name_l = name.lower().replace("-", "")
    if "ebike" in name_l or "indoor" in name_l or _NO_HM_SPORTS & set(sports):
        return False
    if sports:
        return bool(_HM_SPORTS & set(sports))
    return icon in _HM_ICONS


class FactorResolver:
    def __init__(
        self,
        categories: list[Category],
        changes: list[CategoryFactorChange],
        elevation_changes: list[CategoryElevationChange] | None = None,
    ) -> None:
        self._base = {c.id: c.factor for c in categories}
        self._hm_base = {c.id: c.counts_elevation for c in categories}
        self._changes: dict[int, tuple[list[date_type], list[float]]] = {}
        for ch in sorted(changes, key=lambda c: (c.category_id, c.valid_from)):
            dates, factors = self._changes.setdefault(ch.category_id, ([], []))
            dates.append(ch.valid_from)
            factors.append(ch.factor)
        self._hm_changes: dict[int, tuple[list[date_type], list[bool]]] = {}
        for ec in sorted(elevation_changes or [], key=lambda c: (c.category_id, c.valid_from)):
            dates, werte = self._hm_changes.setdefault(ec.category_id, ([], []))
            dates.append(ec.valid_from)
            werte.append(ec.counts_elevation)

    @classmethod
    def load(cls, session: Session) -> "FactorResolver":
        return cls(
            list(session.exec(select(Category)).all()),
            list(session.exec(select(CategoryFactorChange)).all()),
            list(session.exec(select(CategoryElevationChange)).all()),
        )

    def counts_elevation(self, category_id: int, on: date_type) -> bool:
        dates, werte = self._hm_changes.get(category_id, ([], []))
        i = bisect_right(dates, on)
        if i:
            return werte[i - 1]
        return self._hm_base.get(category_id, False)

    def factor(self, category_id: int, on: date_type) -> float:
        dates, factors = self._changes.get(category_id, ([], []))
        i = bisect_right(dates, on)
        if i:
            return factors[i - 1]
        return self._base.get(category_id, 0.0)

    def km(self, act: Activity) -> float:
        """Distanz inkl. Höhenmeter-Bonus, noch ohne Kategorie-Faktor."""
        if act.elevation_m and self.counts_elevation(act.category_id, act.date):
            return act.distance_km + act.elevation_m / HM_PRO_KM
        return act.distance_km

    def mm(self, act: Activity) -> float:
        return self.km(act) * self.factor(act.category_id, act.date)


def set_counts_elevation(
    session: Session, cat: Category, value: bool, today: date_type | None = None
) -> None:
    """Admin-Schalter: Höhenmeter ab elevation_start an/aus, nie rückwirkend.
    Noch nicht wirksame Änderungen werden ersetzt. Committet nicht."""
    start = elevation_start(today)
    pending = session.exec(
        select(CategoryElevationChange).where(
            CategoryElevationChange.category_id == cat.id,
            CategoryElevationChange.valid_from >= start,
        )
    ).all()
    for ec in pending:
        session.delete(ec)
    session.flush()
    resolver = FactorResolver([cat], [], list(session.exec(
        select(CategoryElevationChange).where(CategoryElevationChange.category_id == cat.id)
    ).all()))
    if resolver.counts_elevation(cat.id, start) != value:
        session.add(CategoryElevationChange(
            category_id=cat.id, counts_elevation=value, valid_from=start,
        ))
    session.flush()
