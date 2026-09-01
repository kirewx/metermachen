# Kategorie-Faktoren ab Stichtag — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Der Admin kann Kategorie-Faktoren ab einem Stichtag ändern (nicht rückwirkend); alle Live-Berechnungen rechnen datumsabhängig.

**Architecture:** Neue Tabelle `CategoryFactorChange` (eine Zeile = eine Änderung ab `valid_from`); `Category.factor` bleibt der Ur-Faktor. Ein `FactorResolver` (neu: `services/factors.py`) ist die einzige Stelle, die Faktoren auflöst; alle Berechnungsstellen stellen von `distance_km * cat.factor` auf ihn um. API liefert in `CategoryOut.factor` den heute gültigen Faktor, Admin-Endpoints legen Änderungen an / löschen sie.

**Tech Stack:** FastAPI + SQLModel (SQLite, handgeschriebene Migrationen — neue Tabelle kommt via `create_all`, kein Migrationscode nötig), React + TanStack Query, pytest, vitest.

**Spec:** `docs/superpowers/specs/2026-09-01-faktor-aenderungen-design.md`

**Arbeitsverzeichnisse:** Backend-Kommandos aus `backend/`, Frontend-Kommandos aus `frontend/`.

---

### Task 1: Modell `CategoryFactorChange`

**Files:**
- Modify: `backend/app/models.py` (nach der `Category`-Klasse, ~Zeile 38)
- Test: `backend/tests/test_factor_changes.py` (neu)

- [ ] **Step 1: Failing Test schreiben**

`backend/tests/test_factor_changes.py` anlegen:

```python
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import CategoryFactorChange
from tests.conftest import make_category


def make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1)):
    ch = CategoryFactorChange(category_id=cat.id, factor=factor, valid_from=valid_from)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def test_factor_change_unique_pro_kategorie_und_tag(session):
    cat = make_category(session)
    make_change(session, cat)
    with pytest.raises(IntegrityError):
        make_change(session, cat, factor=20.0)  # gleicher Tag → verboten
    session.rollback()
    # Gleicher Tag bei ANDERER Kategorie ist ok.
    andere = make_category(session, name="Rad", factor=1.0)
    make_change(session, andere)
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: FAIL / ERROR mit `ImportError: cannot import name 'CategoryFactorChange'`

- [ ] **Step 3: Modell implementieren**

In `backend/app/models.py` direkt nach der `Category`-Klasse einfügen:

```python
class CategoryFactorChange(SQLModel, table=True):
    """Faktor-Änderung ab Stichtag (Spec 2026-09-01). Category.factor bleibt
    der Ur-Faktor vor der ältesten Änderung; maßgeblich ist das
    Aktivitätsdatum — nie rückwirkend."""

    __table_args__ = (UniqueConstraint("category_id", "valid_from"),)

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    factor: float
    valid_from: date_type
    created_at: datetime = Field(default_factory=utcnow)
```

(`UniqueConstraint`, `date_type`, `utcnow` sind in models.py bereits importiert.)

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_factor_changes.py
git commit -m "feat(faktoren): Modell CategoryFactorChange"
```

---

### Task 2: `FactorResolver` in `services/factors.py`

**Files:**
- Create: `backend/app/services/factors.py`
- Test: `backend/tests/test_factor_changes.py` (erweitern)

- [ ] **Step 1: Failing Tests schreiben**

In `backend/tests/test_factor_changes.py` ergänzen:

```python
from app.models import Activity
from app.services.factors import FactorResolver


def test_resolver_ohne_aenderungen_nutzt_urfaktor(session):
    cat = make_category(session)  # factor=4.0
    r = FactorResolver.load(session)
    assert r.factor(cat.id, date(2026, 8, 31)) == 4.0


def test_resolver_stichtag_und_mehrere_aenderungen(session):
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    make_change(session, cat, factor=20.0, valid_from=date(2026, 10, 1))
    r = FactorResolver.load(session)
    assert r.factor(cat.id, date(2026, 8, 31)) == 30.0  # vor Stichtag: Ur-Faktor
    assert r.factor(cat.id, date(2026, 9, 1)) == 25.0   # genau am Stichtag: neu
    assert r.factor(cat.id, date(2026, 9, 30)) == 25.0
    assert r.factor(cat.id, date(2026, 10, 1)) == 20.0  # jüngste Änderung gewinnt


def test_resolver_mm_und_unbekannte_kategorie(session):
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    r = FactorResolver.load(session)
    alt = Activity(user_id=1, category_id=cat.id, date=date(2026, 8, 31), distance_km=2.0)
    neu = Activity(user_id=1, category_id=cat.id, date=date(2026, 9, 1), distance_km=2.0)
    assert r.mm(alt) == 60.0
    assert r.mm(neu) == 50.0
    # Unbekannte Kategorie → 0.0 (entspricht dem bisherigen Überspringen).
    fremd = Activity(user_id=1, category_id=999, date=date(2026, 9, 1), distance_km=2.0)
    assert r.mm(fremd) == 0.0
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'app.services.factors'`

- [ ] **Step 3: Resolver implementieren**

`backend/app/services/factors.py` anlegen:

```python
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
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: PASS (alle 4)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/factors.py backend/tests/test_factor_changes.py
git commit -m "feat(faktoren): FactorResolver löst Faktoren datumsabhängig auf"
```

---

### Task 3: `CategoryOut` liefert effektiven Faktor + Änderungslisten

**Files:**
- Modify: `backend/app/schemas.py` (CategoryOut, ~Zeile 36)
- Modify: `backend/app/routers/categories.py`
- Test: `backend/tests/test_factor_changes.py` (erweitern)

- [ ] **Step 1: Failing Test schreiben**

In `backend/tests/test_factor_changes.py` ergänzen (`login`, `make_user` in den bestehenden conftest-Import aufnehmen):

```python
def test_categories_liefern_effektiven_faktor_und_listen(client, session):
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    heute = date.today()
    make_change(session, cat, factor=25.0, valid_from=heute)  # wirksam
    make_change(session, cat, factor=20.0, valid_from=heute + timedelta(days=30))
    r = client.get("/api/categories")
    assert r.status_code == 200
    c = r.json()[0]
    assert c["factor"] == 25.0        # heute gültig
    assert c["base_factor"] == 30.0   # Ur-Faktor
    assert [p["factor"] for p in c["pending_changes"]] == [20.0]
    assert [h["factor"] for h in c["history"]] == [25.0]


def test_categories_ohne_aenderungen_wie_bisher(client, session):
    make_category(session)  # factor=4.0
    c = client.get("/api/categories").json()[0]
    assert c["factor"] == 4.0
    assert c["base_factor"] == 4.0
    assert c["pending_changes"] == [] and c["history"] == []
```

Oben in der Datei `from datetime import date, timedelta` (statt nur `date`).

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: FAIL mit `KeyError: 'base_factor'`

- [ ] **Step 3: Schemas erweitern**

In `backend/app/schemas.py`: oben bei den Category-Schemas ergänzen und `CategoryOut` ersetzen. `CategoryFactorChange` in den models-Import aufnehmen; `from datetime import date as date_type` existiert bereits.

```python
class FactorChangeOut(BaseModel):
    id: int
    factor: float
    valid_from: date_type


class CategoryOut(BaseModel):
    id: int
    name: str
    factor: float  # der HEUTE gültige Faktor (berechnet, nie gespeichert)
    base_factor: float  # Ur-Faktor vor der ältesten Änderung
    color: str
    icon: str
    default_km: float
    is_active: bool
    strava_sport_types: list[str]
    pending_changes: list[FactorChangeOut] = []
    history: list[FactorChangeOut] = []

    @classmethod
    def from_category(
        cls, cat: Category, changes: list["CategoryFactorChange"] | None = None
    ) -> "CategoryOut":
        changes = sorted(changes or [], key=lambda c: c.valid_from)
        heute = date_type.today()
        wirksam = [c for c in changes if c.valid_from <= heute]
        return cls(
            id=cat.id,
            name=cat.name,
            factor=wirksam[-1].factor if wirksam else cat.factor,
            base_factor=cat.factor,
            color=cat.color,
            icon=cat.icon,
            default_km=cat.default_km,
            is_active=cat.is_active,
            strava_sport_types=json.loads(cat.strava_sport_types or "[]"),
            pending_changes=[
                FactorChangeOut(id=c.id, factor=c.factor, valid_from=c.valid_from)
                for c in changes
                if c.valid_from > heute
            ],
            history=[
                FactorChangeOut(id=c.id, factor=c.factor, valid_from=c.valid_from)
                for c in wirksam
            ],
        )
```

- [ ] **Step 4: Router-GET erweitern**

In `backend/app/routers/categories.py` den models-Import um `CategoryFactorChange` ergänzen, oben `from collections import defaultdict` einfügen und `list_categories` ersetzen:

```python
@router.get("", response_model=list[CategoryOut])
def list_categories(session: Session = Depends(get_session)):
    cats = session.exec(select(Category).order_by(Category.id)).all()
    by_cat: dict[int, list[CategoryFactorChange]] = defaultdict(list)
    for ch in session.exec(select(CategoryFactorChange)).all():
        by_cat[ch.category_id].append(ch)
    return [CategoryOut.from_category(c, by_cat.get(c.id)) for c in cats]
```

`create_category`/`patch_category` bleiben unverändert — `from_category` ohne zweites Argument funktioniert weiter (frische bzw. gepatchte Kategorie: Listen bewusst leer bzw. beim Patch irrelevant, das Frontend lädt danach neu). ABER: `patch_category` soll die Änderungen mitliefern, damit `factor` im Response stimmt. Deshalb dort vor dem `return`:

```python
    changes = list(
        session.exec(
            select(CategoryFactorChange).where(
                CategoryFactorChange.category_id == cat.id
            )
        ).all()
    )
    return CategoryOut.from_category(cat, changes)
```

- [ ] **Step 5: Alle Kategorie-Tests laufen lassen**

Run: `python -m pytest tests/test_factor_changes.py tests/test_categories.py -v`
Expected: PASS (Bestandstests unverändert grün, da ohne Änderungen `factor == base_factor` gilt)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/categories.py backend/tests/test_factor_changes.py
git commit -m "feat(faktoren): CategoryOut mit effektivem Faktor, Historie und anstehenden Änderungen"
```

---

### Task 4: Admin-Endpoints POST/DELETE factor-changes

**Files:**
- Modify: `backend/app/routers/categories.py`
- Modify: `backend/app/schemas.py` (FactorChangeCreate)
- Test: `backend/tests/test_factor_changes.py` (erweitern)

- [ ] **Step 1: Failing Tests schreiben**

```python
def test_factor_change_anlegen_nur_admin(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 25.0, "valid_from": date.today().isoformat()},
    )
    assert r.status_code == 403


def test_factor_change_anlegen_validierung(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    login(client, username="chef")
    gestern = (date.today() - timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 25.0, "valid_from": gestern},
    )
    assert r.status_code == 400  # nicht rückwirkend
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 0, "valid_from": date.today().isoformat()},
    )
    assert r.status_code == 422  # factor > 0
    r = client.post(
        "/api/categories/999/factor-changes",
        json={"factor": 25.0, "valid_from": date.today().isoformat()},
    )
    assert r.status_code == 404


def test_factor_change_anlegen_und_duplikat(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    login(client, username="chef")
    morgen = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 25.0, "valid_from": morgen},
    )
    assert r.status_code == 201
    assert r.json()["factor"] == 25.0
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 20.0, "valid_from": morgen},
    )
    assert r.status_code == 409  # gleicher Tag doppelt


def test_factor_change_loeschen(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    heute = make_change(session, cat, factor=25.0, valid_from=date.today())
    alt = make_change(session, cat, factor=28.0, valid_from=date(2026, 1, 1))
    login(client, username="chef")
    r = client.delete(f"/api/categories/{cat.id}/factor-changes/{heute.id}")
    assert r.status_code == 204  # valid_from >= heute → löschbar (Vertipper-Korrektur)
    r = client.delete(f"/api/categories/{cat.id}/factor-changes/{alt.id}")
    assert r.status_code == 409  # Historie ist unantastbar
    r = client.delete(f"/api/categories/{cat.id}/factor-changes/9999")
    assert r.status_code == 404
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: FAIL, 404/405-Statuscodes statt der erwarteten (Route existiert nicht)

- [ ] **Step 3: Schema + Endpoints implementieren**

`backend/app/schemas.py`, bei den Category-Schemas:

```python
class FactorChangeCreate(BaseModel):
    factor: float = Field(gt=0)
    valid_from: date_type
```

`backend/app/routers/categories.py` (Imports: `FactorChangeCreate`, `FactorChangeOut` aus schemas; `date` aus datetime):

```python
@router.post(
    "/{category_id}/factor-changes",
    response_model=FactorChangeOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_factor_change(
    category_id: int, data: FactorChangeCreate, session: Session = Depends(get_session)
):
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    if data.valid_from < date.today():
        raise HTTPException(
            status_code=400, detail="Faktor-Änderungen gelten nicht rückwirkend"
        )
    doppelt = session.exec(
        select(CategoryFactorChange).where(
            CategoryFactorChange.category_id == category_id,
            CategoryFactorChange.valid_from == data.valid_from,
        )
    ).first()
    if doppelt is not None:
        raise HTTPException(
            status_code=409,
            detail="Für diesen Tag existiert schon eine Änderung — erst löschen",
        )
    ch = CategoryFactorChange(
        category_id=category_id, factor=data.factor, valid_from=data.valid_from
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return FactorChangeOut(id=ch.id, factor=ch.factor, valid_from=ch.valid_from)


@router.delete(
    "/{category_id}/factor-changes/{change_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
def delete_factor_change(
    category_id: int, change_id: int, session: Session = Depends(get_session)
):
    ch = session.get(CategoryFactorChange, change_id)
    if ch is None or ch.category_id != category_id:
        raise HTTPException(status_code=404)
    if ch.valid_from < date.today():
        raise HTTPException(
            status_code=409, detail="Wirksam gewordene Änderungen sind Historie"
        )
    session.delete(ch)
    session.commit()
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/categories.py backend/tests/test_factor_changes.py
git commit -m "feat(faktoren): Admin-Endpoints zum Anlegen/Löschen von Faktor-Änderungen"
```

---

### Task 5: Rechenkern I — bet_metrics, points, challenges

**Files:**
- Modify: `backend/app/services/bet_metrics.py`
- Modify: `backend/app/services/points.py:50-66`
- Modify: `backend/app/services/challenges.py:57-72`
- Test: `backend/tests/test_factor_changes.py` (Regressionstests)

- [ ] **Step 1: Failing Regressionstest schreiben**

```python
from app.services import bet_metrics
from app.services.challenges import metric_mm
from app.models import Challenge


def test_wett_metriken_rechnen_datumsabhaengig(client, session):
    user = make_user(session)
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 31), distance_km=2.0))  # 60 MM
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 9, 1), distance_km=2.0))   # 50 MM
    session.commit()
    assert bet_metrics.scaled_km(
        session, user.id, date(2026, 8, 1), date(2026, 9, 30)
    ) == 110.0


def test_challenge_metrik_rechnet_datumsabhaengig(client, session):
    user = make_user(session)
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    ch = Challenge(
        title="Test", creator_id=user.id, mode="ziel", target=1000.0, metric="mm",
        join_mode="auto", period_start=date(2026, 8, 1), period_end=date(2026, 9, 30),
        status="laufend",
    )
    session.add(ch)
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 31), distance_km=2.0))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 9, 1), distance_km=2.0))
    session.commit()
    assert metric_mm(session, user.id, ch) == 110.0
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: FAIL, `120.0 != 110.0` (beide rechnen noch flach mit 30)

- [ ] **Step 3: bet_metrics umstellen**

In `backend/app/services/bet_metrics.py`: Import `Category` entfällt, dafür `from .factors import FactorResolver`.

`scaled_km` — die beiden cats-Zeilen ersetzen:

```python
def scaled_km(
    session: Session, user_id: int, start: date_type, end: date_type
) -> float:
    resolver = FactorResolver.load(session)
    acts = session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= start,
            Activity.date <= end,
        )
    ).all()
    # Unbekannte Kategorien liefern Faktor 0.0 — wie das frühere Überspringen.
    return round(sum(resolver.mm(a) for a in acts), 2)
```

`longest_streak` — cats-Dict raus, Schleifenkörper:

```python
    resolver = FactorResolver.load(session)
    per_day: dict[date_type, float] = defaultdict(float)
    for a in session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= start,
            Activity.date <= end,
        )
    ).all():
        per_day[a.date] += resolver.mm(a)
```

- [ ] **Step 4: points umstellen**

In `backend/app/services/points.py`, `scaled_km_since_start`: cats-Dict raus (`Category`-Import entfernen, `from .factors import FactorResolver` rein), Summe ersetzen:

```python
    resolver = FactorResolver.load(session)
    ...
    return sum(resolver.mm(a) * user.km_factor for a in acts)
```

- [ ] **Step 5: challenges umstellen**

In `backend/app/services/challenges.py` (`from .factors import FactorResolver` importieren; `_rows` und seine Category-Nutzung bleiben — der Kategorie-Filter braucht das Dict weiterhin):

```python
def metric_mm(session: Session, user_id: int, ch: Challenge) -> float:
    resolver = FactorResolver.load(session)
    return round(sum(resolver.mm(a) for a, _ in _rows(session, user_id, ch)), 2)
```

```python
def per_day(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> dict[date_type, float]:
    """MM je Kalendertag im Zeitraum (Kategorie-gefiltert)."""
    resolver = FactorResolver.load(session)
    tage: dict[date_type, float] = defaultdict(float)
    for a, _ in _rows(session, user_id, ch, bis):
        tage[a.date] += resolver.mm(a)
    return tage
```

- [ ] **Step 6: Alle betroffenen Tests laufen lassen**

Run: `python -m pytest tests/test_factor_changes.py tests/test_bet_metrics.py tests/test_bets_resolution.py tests/test_points.py tests/test_challenges_metrics.py -v`
Expected: PASS (Bestandstests unverändert — ohne Änderungszeilen rechnet der Resolver identisch)

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/bet_metrics.py backend/app/services/points.py backend/app/services/challenges.py backend/tests/test_factor_changes.py
git commit -m "feat(faktoren): Wett-, Punkte- und Challenge-Metriken rechnen datumsabhängig"
```

---

### Task 6: Rechenkern II — achievements, feed, comparison

**Files:**
- Modify: `backend/app/services/achievements.py` (Zeilen 183-187, 195, 293-304, 420, 444, 471)
- Modify: `backend/app/services/feed.py` (Zeilen 49-70, 91, 210, 355)
- Modify: `backend/app/routers/comparison.py` (Zeile 128)
- Test: `backend/tests/test_factor_changes.py` (Comparison-Regressionstest)

- [ ] **Step 1: Failing Regressionstest schreiben**

```python
from app.models import Season


def test_comparison_rechnet_datumsabhaengig(client, session):
    user = make_user(session)
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    session.add(Season(year=2026, goal_km=1000.0, start_date=date(2026, 7, 20)))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 31), distance_km=2.0))  # 60 MM
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 9, 1), distance_km=2.0))   # 50 MM
    session.commit()
    login(client)
    erik = client.get("/api/comparison/2026").json()["users"][0]
    assert erik["total_scaled_km"] == 110.0
    assert [s["scaled_km"] for s in erik["segments"]] == [60.0, 50.0]
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `python -m pytest tests/test_factor_changes.py -v`
Expected: FAIL, `120.0 != 110.0`

- [ ] **Step 3: comparison umstellen**

In `backend/app/routers/comparison.py`: `from ..services.factors import FactorResolver` importieren. In `compute_comparison` (nach dem Laden der `rows`, vor der `result_users`-Schleife) `resolver = FactorResolver.load(session)` einfügen und Zeile 128 ersetzen:

```python
            scaled = round(a.distance_km * resolver.factor(c.id, a.date) * factor, 2)
```

- [ ] **Step 4: achievements umstellen**

In `backend/app/services/achievements.py`: `from .factors import FactorResolver` importieren.

`_gewertete_km` (Zeile 183) — Signatur ändern, alle Aufrufer reichen statt `cats` einen Resolver durch:

```python
def _gewertete_km(act: Activity, resolver: FactorResolver) -> float:
    """MM einer einzelnen Aktivität: Kategorie-Faktor (datumsabhängig), ohne
    Admin-Handicap — gleiche Rechnung wie Testphasen-Sieger/Warm-up-Vergleich."""
    return resolver.mm(act)
```

Aufrufer anpassen — in `warmup_mm` (Zeile 190) und `check_unlocks` (Zeilen 293/299/304): dort, wo bisher das `cats`-Dict für `_gewertete_km` gebaut/benutzt wird, stattdessen einmal `resolver = FactorResolver.load(session)` laden und `_gewertete_km(act, resolver)` aufrufen. (`cats` bleibt bestehen, wo es zusätzlich für `bucket_for_category` o.ä. gebraucht wird.)

In `fuehrungs_zeit` (Zeile 420), Jahresbester-Helfer (Zeile 444) und `_wochenkoenig_fenster` (Zeile 471): jeweils `resolver = FactorResolver.load(session)` am Funktionsanfang, dann

```python
        kum[a.user_id] += resolver.mm(a) * users[a.user_id].km_factor          # Z. 420
        sums[act.user_id] += resolver.mm(act)                                   # Z. 444
        tages_km[act.date][act.user_id] += resolver.mm(act) * u.km_factor       # Z. 471
```

Die umgebenden `cats`-Filter (`if cat is None: continue` etc.) bleiben unverändert.

- [ ] **Step 5: feed umstellen**

In `backend/app/services/feed.py`: `from .factors import FactorResolver` importieren.

`_activity_payload` (Zeile 49) bekommt den Resolver:

```python
def _activity_payload(act: Activity, cat: Category, resolver: FactorResolver) -> dict:
    ...
        "mm": round(resolver.mm(act), 2),
```

`activity_event` (Zeile 65): `_activity_payload(act, cat, FactorResolver.load(session))`.

Saison-Totals (Zeile 91), Recap (Zeile 210), Backfill (Zeile 355): jeweils `resolver = FactorResolver.load(session)` einmal vor der Schleife, dann

```python
        totals[a.user_id] += resolver.mm(a) * users[a.user_id].km_factor   # Z. 91
        mm[a.user_id] += resolver.mm(a) * users[a.user_id].km_factor       # Z. 210
        totals[a.user_id] += resolver.mm(a) * users[a.user_id].km_factor   # Z. 355
```

Im Backfill (Zeile 352) außerdem `_activity_payload(a, cat, resolver)`.

- [ ] **Step 6: Gesamte Backend-Suite laufen lassen**

Run: `python -m pytest -q`
Expected: alle Tests PASS. Falls ein Bestandstest bricht: prüfen, ob die Stelle versehentlich Verhalten geändert hat (ohne CategoryFactorChange-Zeilen MUSS jede Rechnung identisch sein).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/achievements.py backend/app/services/feed.py backend/app/routers/comparison.py backend/tests/test_factor_changes.py
git commit -m "feat(faktoren): Achievements, Feed und Vergleich rechnen datumsabhängig"
```

---

### Task 7: Frontend — Typen und API-Client

**Files:**
- Modify: `frontend/src/api/client.ts` (Category-Typ ~Zeile 8, api-Objekt ~Zeile 408)

- [ ] **Step 1: Typen erweitern**

```ts
export type FactorChange = { id: number; factor: number; valid_from: string }
export type Category = {
  id: number
  name: string
  factor: number // der heute gültige Faktor (Backend berechnet)
  base_factor: number
  color: string
  icon: string
  default_km: number
  is_active: boolean
  strava_sport_types: string[]
  pending_changes: FactorChange[]
  history: FactorChange[]
}
```

- [ ] **Step 2: API-Methoden ergänzen** (neben `patchCategory`)

```ts
  createFactorChange: (categoryId: number, b: { factor: number; valid_from: string }) =>
    request<FactorChange>(`/api/categories/${categoryId}/factor-changes`, post(b)),
  deleteFactorChange: (categoryId: number, changeId: number) =>
    request<void>(`/api/categories/${categoryId}/factor-changes/${changeId}`, { method: 'DELETE' }),
```

`createCategory`-Typ anpassen, weil `Omit<Category, 'id' | 'is_active'>` jetzt die neuen Pflichtfelder enthielte:

```ts
  createCategory: (b: {
    name: string; factor: number; color: string; icon: string
    default_km: number; strava_sport_types: string[]
  }) => request<Category>('/api/categories', post(b)),
```

- [ ] **Step 3: Typecheck**

Run: `npx tsc --noEmit`
Expected: Fehler nur in `Admin.test.tsx`-Mocks (fehlende neue Felder) — die fixt Task 8. Kompiliert der Rest, weiter.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(faktoren): API-Client für Faktor-Änderungen"
```

---

### Task 8: Admin-Panel — Faktor ändern statt Faktor tippen

**Files:**
- Modify: `frontend/src/pages/Admin.tsx` (`Kategorien`, Zeilen 203-316)
- Test: `frontend/src/pages/Admin.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

In `Admin.test.tsx`: Mock-Kategorien um die neuen Felder ergänzen (beide Objekte: `base_factor` = wie `factor`, `pending_changes: []`, `history: []`; Kategorie 1 zusätzlich mit einer anstehenden Änderung testbar machen):

```ts
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, base_factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'],
        pending_changes: [{ id: 7, factor: 3, valid_from: '2026-10-01' }], history: [] },
      { id: 2, name: 'Radfahren', factor: 1, base_factor: 1, color: '#00f', icon: 'rad', default_km: 20, is_active: true, strava_sport_types: [],
        pending_changes: [], history: [] },
    ]),
```

Mocks ergänzen: `createFactorChange` und `deleteFactorChange` als benannte `vi.fn()` (Muster `patchCategory`). Neue Tests:

```ts
const createFactorChange = vi.fn().mockResolvedValue({})
const deleteFactorChange = vi.fn().mockResolvedValue(undefined)
// im vi.mock-api-Objekt:
//   createFactorChange: (...a: unknown[]) => createFactorChange(...a),
//   deleteFactorChange: (...a: unknown[]) => deleteFactorChange(...a),

describe('Admin Faktor-Änderungen', () => {
  it('zeigt aktuellen Faktor und anstehende Änderung, legt neue an', async () => {
    renderAdmin()
    expect(await screen.findByText('×4')).toBeInTheDocument()
    expect(screen.getByText(/ab 01\.10\.2026.*×3/)).toBeInTheDocument()
    fireEvent.click(screen.getAllByText('Faktor ändern')[0])
    fireEvent.change(screen.getByLabelText('Neuer Faktor'), { target: { value: '3.5' } })
    fireEvent.change(screen.getByLabelText('Gültig ab'), { target: { value: '2026-11-01' } })
    fireEvent.click(screen.getByText('Änderung anlegen'))
    await waitFor(() =>
      expect(createFactorChange).toHaveBeenCalledWith(1, { factor: 3.5, valid_from: '2026-11-01' }),
    )
  })

  it('löscht eine anstehende Änderung', async () => {
    renderAdmin()
    fireEvent.click((await screen.findAllByText('Faktor ändern'))[0])
    fireEvent.click(screen.getByLabelText('Änderung ab 01.10.2026 löschen'))
    await waitFor(() => expect(deleteFactorChange).toHaveBeenCalledWith(1, 7))
  })
})
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `npx vitest run src/pages/Admin.test.tsx`
Expected: FAIL (`Faktor ändern` nicht gefunden)

- [ ] **Step 3: UI implementieren**

In `Kategorien` (Admin.tsx): Faktor-`Input` (Zeilen 245-255) ersetzen durch Anzeige + Button; Modal-State und Hilfsformat ergänzen. Ein Datum `2026-10-01` wird als `01.10.2026` angezeigt:

```tsx
const datumKurz = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}
```

Im Kategorien-Row (ersetzt das Faktor-Input):

```tsx
            <div className="flex min-w-28 flex-col">
              <span className="text-xs font-semibold text-ink-mute">Faktor</span>
              <span className="font-mono tabular-nums text-accent">
                ×{c.factor}
                {c.pending_changes.length > 0 && (
                  <span className="ml-1 text-xs text-ink-mute">
                    → ab {datumKurz(c.pending_changes[0].valid_from)} ×{c.pending_changes[0].factor}
                  </span>
                )}
              </span>
            </div>
            <Button variant="ghost" onClick={() => setFaktorKat(c)}>
              Faktor ändern
            </Button>
```

State + Mutations in `Kategorien` (Muster: bestehende Mutations dort):

```tsx
  const [faktorKat, setFaktorKat] = useState<Category | null>(null)
  const [neuFaktor, setNeuFaktor] = useState('')
  const [gueltigAb, setGueltigAb] = useState(() => new Date().toISOString().slice(0, 10))
  const createChange = useMutation({
    mutationFn: () =>
      api.createFactorChange(faktorKat!.id, {
        factor: parseFloat(neuFaktor),
        valid_from: gueltigAb,
      }),
    onSuccess: () => {
      setFaktorKat(null)
      setNeuFaktor('')
      refresh()
    },
    onError: (e) => toast(e.message),
  })
  const deleteChange = useMutation({
    mutationFn: ({ catId, changeId }: { catId: number; changeId: number }) =>
      api.deleteFactorChange(catId, changeId),
    onSuccess: () => {
      setFaktorKat(null)
      refresh()
    },
    onError: (e) => toast(e.message),
  })
```

(`Category`-Typ aus `../api/client` importieren.) Modal vor dem schließenden `</Collapsible>`:

```tsx
      <Modal
        open={faktorKat !== null}
        onClose={() => setFaktorKat(null)}
        title={`Faktor für ${faktorKat?.name ?? ''} ändern`}
      >
        <p className="mb-3 text-sm text-ink-mute">
          Gilt ab dem Stichtag für neue Aktivitäten — nie rückwirkend. Aktuell: ×
          {faktorKat?.factor}
        </p>
        <div className="flex flex-wrap gap-2">
          <Input
            label="Neuer Faktor"
            type="number"
            step="0.5"
            className="w-24"
            value={neuFaktor}
            onChange={(e) => setNeuFaktor(e.target.value)}
          />
          <Input
            label="Gültig ab"
            type="date"
            value={gueltigAb}
            onChange={(e) => setGueltigAb(e.target.value)}
          />
        </div>
        <Button
          className="mt-3"
          disabled={!(parseFloat(neuFaktor) > 0) || !gueltigAb}
          onClick={() => createChange.mutate()}
        >
          Änderung anlegen
        </Button>
        {(faktorKat?.pending_changes.length ?? 0) > 0 && (
          <div className="mt-4 space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-mute">
              Anstehend
            </p>
            {faktorKat!.pending_changes.map((p) => (
              <div key={p.id} className="flex items-center justify-between text-sm">
                <span>
                  ab {datumKurz(p.valid_from)}: ×{p.factor}
                </span>
                <Button
                  variant="ghost"
                  aria-label={`Änderung ab ${datumKurz(p.valid_from)} löschen`}
                  onClick={() => deleteChange.mutate({ catId: faktorKat!.id, changeId: p.id })}
                >
                  Löschen
                </Button>
              </div>
            ))}
          </div>
        )}
        {(faktorKat?.history.length ?? 0) > 0 && (
          <div className="mt-4 space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-mute">
              Historie
            </p>
            <p className="text-sm text-ink-mute">
              Ur-Faktor: ×{faktorKat!.base_factor}
              {faktorKat!.history.map((h) => (
                <span key={h.id}> · ab {datumKurz(h.valid_from)}: ×{h.factor}</span>
              ))}
            </p>
          </div>
        )}
      </Modal>
```

Achtung: Das Modal zeigt `faktorKat` aus dem State — nach `refresh()` ist das Objekt veraltet. Deshalb schließt `createChange.onSuccess` das Modal; `deleteChange` soll es aktualisieren: in `deleteChange.onSuccess` zusätzlich `setFaktorKat(null)` (schlicht schließen — einfachste konsistente Lösung).

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/pages/Admin.test.tsx`
Expected: PASS (auch die Bestandstests — das entfernte Faktor-Input wird von keinem Bestandstest angefasst; `patchCategory` wird weiter für Standard-km/Aktiv/Strava genutzt)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Admin.tsx frontend/src/pages/Admin.test.tsx
git commit -m "feat(faktoren): Admin-Panel legt Faktor-Änderungen mit Stichtag an"
```

---

### Task 9: Regeln-Seite — Hinweis auf anstehende Änderung

**Files:**
- Modify: `frontend/src/pages/Regeln.tsx` (Faktor-Zelle, Zeilen 65-67)
- Test: `frontend/src/pages/Regeln.test.tsx` (neu)

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/pages/Regeln.test.tsx` anlegen (Render-Muster wie `Admin.test.tsx`):

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Regeln from './Regeln'

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Schwimmen', factor: 25, base_factor: 30, color: '#0af', icon: 'schwimmen', default_km: 1, is_active: true, strava_sport_types: [],
        pending_changes: [{ id: 9, factor: 20, valid_from: '2026-10-01' }], history: [] },
      { id: 2, name: 'Laufen', factor: 4, base_factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: [],
        pending_changes: [], history: [] },
    ]),
    addons: vi.fn().mockResolvedValue([]),
  },
}))

function renderRegeln() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Regeln />
    </QueryClientProvider>,
  )
}

describe('Regeln Faktor-Tabelle', () => {
  it('zeigt den heute gültigen Faktor und kündigt Änderungen an', async () => {
    renderRegeln()
    expect(await screen.findByText('×25')).toBeInTheDocument()
    expect(screen.getByText('ab 01.10.2026: ×20')).toBeInTheDocument()
  })

  it('zeigt ohne anstehende Änderung keinen Hinweis', async () => {
    renderRegeln()
    expect(await screen.findByText('×4')).toBeInTheDocument()
    expect(screen.getAllByText(/ab \d\d\./)).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/pages/Regeln.test.tsx`
Expected: FAIL (`ab 01.10.2026: ×20` nicht gefunden)

- [ ] **Step 3: Hinweis implementieren**

In `Regeln.tsx` die Faktor-Zelle ersetzen:

```tsx
                <td className="py-1.5 text-right font-mono tabular-nums text-accent">
                  ×{c.factor}
                  {c.pending_changes.length > 0 && (
                    <div className="text-xs text-ink-mute">
                      ab {datumKurz(c.pending_changes[0].valid_from)}: ×
                      {c.pending_changes[0].factor}
                    </div>
                  )}
                </td>
```

Oben in der Datei denselben Helfer wie in Admin.tsx (bewusst dupliziert statt geteiltes Modul für 3 Zeilen — falls beim Frontend-Redesign mehr Datumsformatierung anfällt, dann extrahieren):

```tsx
const datumKurz = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/pages/Regeln.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Regeln.tsx frontend/src/pages/Regeln.test.tsx
git commit -m "feat(faktoren): Regeln-Seite kündigt anstehende Faktor-Änderungen an"
```

---

### Task 10: Gesamt-Verifikation

- [ ] **Step 1: Backend komplett**

Run (aus `backend/`): `python -m pytest -q`
Expected: alle PASS

- [ ] **Step 2: Frontend komplett**

Run (aus `frontend/`): `npx vitest run` und `npx tsc --noEmit` und `npx eslint src`
Expected: alle PASS, keine Fehler

- [ ] **Step 3: Falls etwas rot ist**: Ursache beheben (KEIN Test „angepasst", der eine echte Verhaltensänderung kaschiert), dann Steps 1-2 wiederholen.

- [ ] **Step 4: Commit (falls Fixes anfielen)**

```bash
git add -A
git commit -m "fix(faktoren): Verifikations-Fixes"
```
