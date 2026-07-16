# Season-Zeitrahmen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Season bekommt ein Enddatum; Ranking/Punkte/Wetten/Achievements rechnen mit dem Season-Fenster statt mit dem Kalenderjahr, damit die Challenge (20.07.2026 → Stuttgartlauf Mai 2027) über den Jahreswechsel funktioniert.

**Architecture:** Neue Spalte `Season.end_date` (nullable). Zentrale Fenster-Helper in neuem Modul `backend/app/services/season_window.py` (`season_window`, `window_bounds`, `in_window`, `current_season`) ersetzen alle `date.year == year`- und `Season.year == today.year`-Stellen. Frontend-Pendant `frontend/src/components/ui/season.ts` (`aktiveSeason`, `saisonLabel`) ersetzt alle `getFullYear()`-Stellen. Nach dem Enddatum friert die Wertung ein; Eintragen bleibt möglich.

**Tech Stack:** FastAPI + SQLModel + SQLite (pytest via `uv run`), React 19 + TanStack Query (vitest).

**Spec:** `docs/superpowers/specs/2026-07-16-season-zeitrahmen-design.md`

**Branch:** `feature/season-zeitrahmen` (existiert, Spec liegt darauf). Ein PR gegen `main`.

**Kommandos** (vom Repo-Root):
- Backend: `cd backend && uv run python -m pytest -q`
- Frontend: `cd frontend && npm run test` / `npm run lint` / `npm run build`

**Fenster-Definition (überall identisch):** Fensterstart = 1. Januar des Season-Jahres (Warm-up gehört zum Fenster; `start_date` trennt nur Warm-up/Challenge). Fensterende = `end_date`; fehlt es: Season **mit** `start_date` → offen (kein Ende), Season **ohne** `start_date` → 31.12. des Jahres (Kalenderjahr wie bisher).

---

### Task 1: Migration + Modell — `Season.end_date`

**Files:**
- Modify: `backend/app/models.py` (Season, ~Zeile 67)
- Modify: `backend/app/db.py` (migrate(), Season-Block ~Zeile 74)
- Test: `backend/tests/test_migration.py`

- [ ] **Step 1: Failing Test schreiben**

Ans Ende von `backend/tests/test_migration.py`:

```python
def test_migration_adds_season_end_date(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE season (id INTEGER PRIMARY KEY, year INTEGER, "
            "goal_km FLOAT, milestones_json TEXT, start_date DATE)"
        ))
        conn.execute(text(
            "INSERT INTO season (year, goal_km, milestones_json, start_date)"
            " VALUES (2026, 1000, '[]', '2026-07-20')"
        ))
    migrate(engine)
    migrate(engine)  # idempotent
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("season")'))]
        assert "end_date" in cols
        assert conn.execute(text("SELECT end_date FROM season")).scalar() is None
```

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_migration.py::test_migration_adds_season_end_date -q`
Expected: FAIL (`end_date` fehlt)

- [ ] **Step 3: Implementieren**

`backend/app/models.py`, in `Season` nach `start_date`:

```python
    end_date: date_type | None = None  # Challenge-Ende; None + start_date = offen
```

`backend/app/db.py`, im `if _table_exists(conn, "season"):`-Block nach dem `start_date`-Eintrag:

```python
            if "end_date" not in season_cols:
                conn.execute(text("ALTER TABLE season ADD COLUMN end_date DATE"))
```

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_migration.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_migration.py
git commit -m "feat(season): Spalte end_date (nullable) + Migration"
```

---

### Task 2: Seasons-API — `end_date` in Create/Patch/Out + Validierung

**Files:**
- Modify: `backend/app/schemas.py` (SeasonCreate ~59, SeasonPatch ~66, SeasonOut ~72)
- Modify: `backend/app/routers/seasons.py`
- Test: `backend/tests/test_seasons.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_seasons.py`:

```python
def test_season_end_date_roundtrip(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post(
        "/api/seasons",
        json={"year": 2031, "goal_km": 1000,
              "start_date": "2031-07-20", "end_date": "2032-05-15"},
    )
    assert r.status_code == 201
    assert r.json()["end_date"] == "2032-05-15"
    sid = r.json()["id"]
    # explizites null löscht das Enddatum (Fenster wieder offen)
    r = client.patch(f"/api/seasons/{sid}", json={"end_date": None})
    assert r.status_code == 200
    assert r.json()["end_date"] is None
    # setzen per Patch
    r = client.patch(f"/api/seasons/{sid}", json={"end_date": "2032-06-01"})
    assert r.status_code == 200
    assert r.json()["end_date"] == "2032-06-01"


def test_season_end_vor_start_abgelehnt(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post(
        "/api/seasons",
        json={"year": 2031, "goal_km": 1000,
              "start_date": "2031-07-20", "end_date": "2031-01-01"},
    )
    assert r.status_code == 422
    r = client.post(
        "/api/seasons", json={"year": 2031, "goal_km": 1000, "start_date": "2031-07-20"}
    )
    sid = r.json()["id"]
    r = client.patch(f"/api/seasons/{sid}", json={"end_date": "2031-01-01"})
    assert r.status_code == 422
```

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_seasons.py -q`
Expected: neue Tests FAIL (ValidationError/KeyError `end_date`)

- [ ] **Step 3: Implementieren**

`backend/app/schemas.py`:

`SeasonCreate` nach `start_date`:

```python
    end_date: date_type | None = None
```

`SeasonPatch` nach `start_date`:

```python
    end_date: date_type | None = None  # None + gesetzt = Enddatum löschen (Fenster offen)
```

`SeasonOut`: Feld `end_date: date_type | None` ergänzen und in `from_season` `end_date=season.end_date,` mitgeben.

`backend/app/routers/seasons.py`:

In `create_season` vor dem `Season(...)`-Konstruktor:

```python
    if (
        data.start_date is not None
        and data.end_date is not None
        and data.end_date < data.start_date
    ):
        raise HTTPException(status_code=422, detail="Enddatum liegt vor dem Startdatum")
```

und im Konstruktor `end_date=data.end_date,` ergänzen.

In `patch_season` vor den Zuweisungen (Validierung auf dem resultierenden Zustand, bevor etwas mutiert wird):

```python
    neu_start = (
        data.start_date if "start_date" in data.model_fields_set else season.start_date
    )
    neu_end = data.end_date if "end_date" in data.model_fields_set else season.end_date
    if neu_start is not None and neu_end is not None and neu_end < neu_start:
        raise HTTPException(status_code=422, detail="Enddatum liegt vor dem Startdatum")
```

und nach dem `start_date`-Block:

```python
    if "end_date" in data.model_fields_set:
        season.end_date = data.end_date
```

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_seasons.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/seasons.py backend/tests/test_seasons.py
git commit -m "feat(season): end_date in der Seasons-API mit Validierung"
```

---

### Task 3: Fenster-Helper `services/season_window.py`

**Files:**
- Create: `backend/app/services/season_window.py`
- Test: `backend/tests/test_season_window.py` (neu)

- [ ] **Step 1: Failing Tests schreiben**

`backend/tests/test_season_window.py` (neu):

```python
from datetime import date

from app.models import Season
from app.services.season_window import (
    current_season,
    in_window,
    season_window,
    window_bounds,
)


def test_season_window_kalenderjahr_ohne_daten():
    s = Season(year=2025, goal_km=1000)
    assert season_window(s) == (date(2025, 1, 1), date(2025, 12, 31))


def test_season_window_offen_mit_start_ohne_ende():
    s = Season(year=2026, goal_km=1000, start_date=date(2026, 7, 20))
    assert season_window(s) == (date(2026, 1, 1), None)


def test_season_window_mit_ende():
    s = Season(
        year=2026, goal_km=1000,
        start_date=date(2026, 7, 20), end_date=date(2027, 5, 16),
    )
    assert season_window(s) == (date(2026, 1, 1), date(2027, 5, 16))


def test_in_window():
    w = (date(2026, 1, 1), date(2027, 5, 16))
    assert in_window(date(2027, 1, 15), w) is True
    assert in_window(date(2027, 5, 16), w) is True  # Endtag zählt noch
    assert in_window(date(2027, 5, 17), w) is False
    assert in_window(date(2025, 12, 31), w) is False
    assert in_window(date(2027, 12, 1), (date(2026, 1, 1), None)) is True  # offen


def test_window_bounds_ohne_season_kalenderjahr(session):
    assert window_bounds(session, 2031) == (date(2031, 1, 1), date(2031, 12, 31))


def _add_season(session, **kw):
    s = Season(goal_km=1000, milestones_json="[]", **kw)
    session.add(s)
    session.commit()
    return s


def test_current_season_jahresuebergreifend(session):
    _add_season(session, year=2026,
                start_date=date(2026, 7, 20), end_date=date(2027, 5, 16))
    assert current_season(session, today=date(2027, 2, 1)).year == 2026


def test_current_season_nach_ende_zuletzt_begonnene(session):
    _add_season(session, year=2026,
                start_date=date(2026, 7, 20), end_date=date(2027, 5, 16))
    assert current_season(session, today=date(2027, 6, 1)).year == 2026


def test_current_season_countdown_naechste(session):
    _add_season(session, year=2028, start_date=date(2028, 7, 20))
    assert current_season(session, today=date(2027, 12, 1)).year == 2028


def test_current_season_bevorzugt_enthaltendes_fenster(session):
    _add_season(session, year=2025)  # Kalenderjahr 2025
    _add_season(session, year=2026, start_date=date(2026, 7, 20))
    assert current_season(session, today=date(2026, 8, 1)).year == 2026
    assert current_season(session, today=date(2025, 3, 1)).year == 2025


def test_current_season_leer(session):
    assert current_season(session) is None
```

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_season_window.py -q`
Expected: FAIL (Modul existiert nicht)

- [ ] **Step 3: Implementieren**

`backend/app/services/season_window.py` (neu, vollständig):

```python
"""Season-Fenster: Wertungszeitraum einer Season (Spec Season-Zeitrahmen).

Fensterstart ist immer der 1. Januar des Season-Jahres — Warm-up-Aktivitäten
gehören zum Fenster, start_date trennt nur Warm-up von Challenge.
Fensterende ist end_date; fehlt es, läuft eine Season MIT start_date offen
weiter (Jahreswechsel!), eine OHNE start_date endet am 31.12. (reines
Kalenderjahr-Verhalten wie vor diesem Feature).
"""

from datetime import date as date_type

from sqlmodel import Session, select

from ..models import Season

Window = tuple[date_type, date_type | None]


def season_window(season: Season) -> Window:
    from_date = date_type(season.year, 1, 1)
    if season.end_date is not None:
        return from_date, season.end_date
    if season.start_date is not None:
        return from_date, None
    return from_date, date_type(season.year, 12, 31)


def window_bounds(session: Session, year: int) -> Window:
    """Fenster zum year-Pfadparameter; ohne Season-Zeile: Kalenderjahr."""
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        return date_type(year, 1, 1), date_type(year, 12, 31)
    return season_window(season)


def in_window(d: date_type, window: Window) -> bool:
    from_date, to_date = window
    return d >= from_date and (to_date is None or d <= to_date)


def current_season(session: Session, today: date_type | None = None) -> Season | None:
    """Aktive Season: Fenster enthält heute (bei mehreren: spätester
    Fensterstart); sonst die zuletzt begonnene; sonst die als Nächstes
    beginnende (Countdown-Phase)."""
    today = today or date_type.today()
    seasons = session.exec(select(Season)).all()
    if not seasons:
        return None

    def start(s: Season) -> date_type:
        return season_window(s)[0]

    enthaltend = [s for s in seasons if in_window(today, season_window(s))]
    if enthaltend:
        return max(enthaltend, key=start)
    begonnen = [s for s in seasons if start(s) <= today]
    if begonnen:
        return max(begonnen, key=start)
    return min(seasons, key=start)
```

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_season_window.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/season_window.py backend/tests/test_season_window.py
git commit -m "feat(season): Fenster-Helper season_window/window_bounds/current_season"
```

---

### Task 4: Fensterfilter — Comparison, Aktivitäten-Liste, Personen-Detail

**Files:**
- Modify: `backend/app/routers/comparison.py` (~Zeile 37/46)
- Modify: `backend/app/routers/activities.py` (`list_my_activities`, ~Zeile 47)
- Modify: `backend/app/routers/users.py` (`user_activities`, ~Zeile 96)
- Test: `backend/tests/test_comparison.py`, `backend/tests/test_activities.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_comparison.py`:

```python
def test_comparison_fenster_ueber_jahresgrenze_mit_freeze(client, session):
    from datetime import date

    from app.models import Activity, Season

    user = make_user(session)
    cat = make_category(session, factor=1.0)
    session.add(Season(year=2026, goal_km=1000, milestones_json="[]",
                       start_date=date(2026, 7, 1), end_date=date(2027, 5, 16)))
    # zählt: Challenge-Phase, auch über die Jahresgrenze
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2027, 1, 15), distance_km=10))
    # zählt nicht: nach dem Saisonende (Freeze)
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2027, 5, 17), distance_km=99))
    session.commit()
    login(client)
    r = client.get("/api/comparison/2026")
    assert r.status_code == 200
    me = next(u for u in r.json()["users"] if u["user_id"] == user.id)
    assert me["total_scaled_km"] == 10.0
```

Ans Ende von `backend/tests/test_activities.py`:

```python
def test_liste_zeigt_saison_fenster_ueber_jahresgrenze(client, session):
    from datetime import date

    from app.models import Activity, Season

    user = make_user(session)
    cat = make_category(session)
    session.add(Season(year=2026, goal_km=1000, milestones_json="[]",
                       start_date=date(2026, 7, 1), end_date=date(2027, 5, 16)))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2027, 1, 15), distance_km=10))  # im Fenster
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2027, 6, 1), distance_km=5))  # nach dem Ende
    session.commit()
    login(client)
    r = client.get("/api/activities?year=2026")
    daten = [a["date"] for a in r.json()]
    assert "2027-01-15" in daten
    assert "2027-06-01" not in daten
```

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_comparison.py tests/test_activities.py -q`
Expected: neue Tests FAIL (Jahresfilter wirft die 2027er-Aktivität raus)

- [ ] **Step 3: Implementieren**

`backend/app/routers/comparison.py` — Import ergänzen:

```python
from ..services.season_window import in_window, season_window
```

Die Filterzeile `rows = [(a, c) for a, c in rows if a.date.year == year]` ersetzen durch:

```python
    window = season_window(season)
    rows = [(a, c) for a, c in rows if in_window(a.date, window)]
```

(Die Warm-up-/Challenge-Filter mit `start` darunter bleiben unverändert.)

`backend/app/routers/activities.py` — Import ergänzen:

```python
from ..services.season_window import in_window, window_bounds
```

In `list_my_activities` die Rückgabezeile ersetzen:

```python
    window = window_bounds(session, year)
    return [_to_out(a, c.factor) for a, c in acts if in_window(a.date, window)]
```

`backend/app/routers/users.py` — gleicher Import, in `user_activities` die Rückgabezeile ersetzen:

```python
    window = window_bounds(session, year)
    return [_to_out(a, c.factor) for a, c in rows if in_window(a.date, window)]
```

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_comparison.py tests/test_activities.py tests/test_users.py -q`
Expected: alle PASS (Bestand: Aktivitäten ohne Season-Daten verhalten sich wie Kalenderjahr)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/comparison.py backend/app/routers/activities.py backend/app/routers/users.py backend/tests/test_comparison.py backend/tests/test_activities.py
git commit -m "feat(season): Fensterfilter statt Kalenderjahr in Comparison und Listen"
```

---

### Task 5: Punkte — `current_season` + Einkommen stoppt am Saisonende

**Files:**
- Modify: `backend/app/services/points.py` (`challenge_start` ~41, `scaled_km_since_start` ~48)
- Test: `backend/tests/test_points.py`

- [ ] **Step 1: Failing Test schreiben**

Ans Ende von `backend/tests/test_points.py`:

```python
def test_income_stoppt_am_saisonende(session):
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    s = _season(session)  # Start vor 10 Tagen
    s.end_date = date.today() - timedelta(days=1)  # Saison gestern beendet
    session.add(s)
    session.commit()
    session.add(
        Activity(user_id=user.id, category_id=cat.id, date=date.today(), distance_km=50)
    )
    session.commit()
    points.ensure_income(session, user.id)
    assert points.balance(session, user.id) == 0  # km nach dem Ende zählen nicht
```

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_points.py -q`
Expected: neuer Test FAIL (50 km → 10 Punkte gebucht)

- [ ] **Step 3: Implementieren**

`backend/app/services/points.py` — Import ergänzen:

```python
from .season_window import current_season, season_window
```

`challenge_start` ersetzen:

```python
def challenge_start(session: Session) -> date_type | None:
    season = current_season(session)
    return season.start_date if season else None
```

`scaled_km_since_start` ersetzen:

```python
def scaled_km_since_start(session: Session, user_id: int) -> float:
    season = current_season(session)
    start = season.start_date if season else None
    if start is None or date_type.today() < start:
        return 0.0
    _, end = season_window(season)
    user = session.get(User, user_id)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    stmt = select(Activity).where(Activity.user_id == user_id, Activity.date >= start)
    if end is not None:
        stmt = stmt.where(Activity.date <= end)
    acts = session.exec(stmt).all()
    return sum(
        a.distance_km * cats[a.category_id].factor * user.km_factor
        for a in acts
        if a.category_id in cats
    )
```

Der Import `Season` in points.py wird danach ggf. ungenutzt — entfernen, falls ja.

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_points.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/points.py backend/tests/test_points.py
git commit -m "feat(season): Punkte-Einkommen nutzt aktive Season und stoppt am Ende"
```

---

### Task 6: Achievements — `current_season` + Wochenkönig-Ende

**Files:**
- Modify: `backend/app/services/achievements.py` (Saison-Block in `check_unlocks`, ~Zeile 170)
- Modify: `backend/app/routers/achievements.py` (`warmup_achievements`, ~Zeile 134)
- Test: `backend/tests/test_achievement_unlocks.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_achievement_unlocks.py`:

```python
def test_saison_checks_finden_jahresuebergreifende_season(session):
    # Season vom Vorjahr, Fenster offen (kein Ende) — enthält heute
    heute = date.today()
    start = heute - timedelta(days=200)
    session.add(Season(year=start.year, goal_km=1000, milestones_json="[]",
                       start_date=start))
    erik = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    session.commit()
    # Warm-up-Aktivität im Startjahr -> Testphasen-Sieger trotz Season.year != heute.year
    add_act(session, erik, lauf, 50.0, d=start - timedelta(days=1))
    check_unlocks(session, erik.id)
    assert "testphasen_sieger" in keys_of(session, erik)


def test_wochenkoenig_stoppt_am_saisonende(session):
    heute = date.today()
    start = heute - timedelta(days=30)
    ende = start + timedelta(days=5)  # nur 6 Challenge-Tage bis zum Ende
    session.add(Season(year=heute.year, goal_km=1000, milestones_json="[]",
                       start_date=start, end_date=ende))
    erik = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    session.commit()
    add_act(session, erik, lauf, 50.0, d=start)
    check_unlocks(session, erik.id)
    # 6 Tage alleiniger Platz 1 reichen nicht — und nach dem Ende wächst nichts mehr
    assert "wochenkoenig" not in keys_of(session, erik)
```

Hinweis: `test_saison_checks_...` setzt voraus, dass `start - timedelta(days=1)` im selben Kalenderjahr wie `start` liegt (die Warm-up-Rechnung filtert aufs Startjahr). 200 Tage zurück ist das der Fall; falls der Test an einem Datum liefe, wo nicht (Anfang Januar), wäre `start.year`-Logik betroffen — für 2026/2027 unkritisch.

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_achievement_unlocks.py -q -k "jahresuebergreifende or stoppt"`
Expected: beide FAIL — der erste, weil der `Season.year == today.year`-Lookup die Vorjahres-Season nicht findet; der zweite, weil der Streak ohne End-Kappung nach dem Saisonende weiterwächst und Wochenkönig fälschlich vergeben wird.

- [ ] **Step 3: Implementieren**

`backend/app/services/achievements.py` — Import ergänzen:

```python
from .season_window import current_season, season_window
```

Im Saison-Block von `check_unlocks` die zwei Zeilen

```python
    season = session.exec(select(Season).where(Season.year == today.year)).first()
    start = season.start_date if season else None
```

ersetzen durch:

```python
    season = current_season(session)
    start = season.start_date if season else None
```

und den `wochenkoenig`-Aufruf so ändern, dass er am Saisonende stoppt — aus

```python
        ctx = _wochenkoenig_fenster(session, user_id, start, today)
```

wird

```python
        _, saison_ende = season_window(season)
        bis = min(today, saison_ende) if saison_ende is not None else today
        ctx = _wochenkoenig_fenster(session, user_id, start, bis)
```

Der Import `Season` bleibt (wird von `_testphasen_platz1`/Modul weiter genutzt — prüfen, sonst entfernen).

`backend/app/routers/achievements.py` — Import ergänzen (`current_season` aus dem Window-Modul):

```python
from ..services.season_window import current_season
```

In `warmup_achievements` die Season-Zeile ersetzen — aus

```python
    season = session.exec(select(Season).where(Season.year == today.year)).first()
```

wird

```python
    season = current_season(session)
```

(Der `Season`-Import im Router wird dadurch ggf. ungenutzt — entfernen, falls ja.)

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_achievement_unlocks.py tests/test_achievements.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/achievements.py backend/app/routers/achievements.py backend/tests/test_achievement_unlocks.py
git commit -m "feat(season): Achievements nutzen aktive Season, Wochenkönig endet mit ihr"
```

---

### Task 7: Wetten — `current_season`, Monats-Tipp-Stopp, Wettstart-Validierung

**Files:**
- Modify: `backend/app/services/bets.py` (`_season_start` ~65, `create_bet` ~95, `ensure_monthly_tip` ~254)
- Test: `backend/tests/test_bets_lifecycle.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_bets_lifecycle.py`:

```python
def test_kein_neuer_monats_tipp_nach_saisonende(session, monkeypatch):
    monkeypatch.setattr(bets, "FIRST_TIP_MONTH", date(2020, 1, 1))
    session.add(Season(
        year=HEUTE.year, goal_km=1000, milestones_json="[]",
        start_date=HEUTE - timedelta(days=60),
        end_date=HEUTE.replace(day=1) - timedelta(days=1),  # Ende vor Monatsbeginn
    ))
    make_user(session)
    session.commit()
    bets.ensure_monthly_tip(session)
    assert session.exec(select(Bet).where(Bet.type == "monats_tipp")).all() == []


def test_create_bet_nach_saisonende_abgelehnt(session):
    session.add(Season(
        year=HEUTE.year, goal_km=1000, milestones_json="[]",
        start_date=HEUTE - timedelta(days=10),
        end_date=HEUTE + timedelta(days=3),
    ))
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    session.commit()
    points.ensure_start_credit(session, erik.id)
    with pytest.raises(ValueError, match="Saisonende"):
        bets.create_bet(
            session, erik, type="duell", title="Zu spät", stake=10,
            period_start=HEUTE + timedelta(days=5),
            period_end=HEUTE + timedelta(days=9),
            params={"opponent_id": lisa.id},
        )
```

Hinweis: Falls `HEUTE` der 1. eines Monats ist, wäre `HEUTE.replace(day=1) - timedelta(days=1)` vor dem Startdatum — für die Testläufe im Juli 2026 unkritisch; der Test prüft `month_start > end`.

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_bets_lifecycle.py -q -k "saisonende"`
Expected: beide FAIL (Tipp wird angelegt / kein ValueError)

- [ ] **Step 3: Implementieren**

`backend/app/services/bets.py` — Import ergänzen:

```python
from .season_window import current_season, season_window
```

`_season_start` ersetzen:

```python
def _season_start(session: Session) -> date_type | None:
    season = current_season(session)
    return season.start_date if season else None


def _season_end(session: Session) -> date_type | None:
    season = current_season(session)
    if season is None:
        return None
    return season_window(season)[1]
```

In `create_bet` nach dem bestehenden Challenge-Start-Check:

```python
    ende = _season_end(session)
    if ende is not None and period_start > ende:
        raise ValueError("Wetten gibt es nur bis zum Saisonende")
```

In `ensure_monthly_tip` nach der Zeile `month_start = today.replace(day=1)`:

```python
    ende = _season_end(session)
    if ende is not None and month_start > ende:
        return  # kein neuer Tipp für Monate nach dem Saisonende
```

(Der `Season`-Import in bets.py wird ggf. ungenutzt — prüfen; er wird in den Tests weiter gebraucht, im Modul nur, falls sonst nirgends referenziert.)

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_bets_lifecycle.py tests/test_bets_api.py tests/test_bets_resolution.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bets.py backend/tests/test_bets_lifecycle.py
git commit -m "feat(season): Wetten enden mit der Saison (Tipp-Stopp, Start-Validierung)"
```

---

### Task 8: Strava-Backfill ab Season-Jahr + Seed-Guard

**Files:**
- Modify: `backend/app/services/strava.py` (`backfill_current_year`, ~Zeile 172)
- Modify: `backend/app/seed.py` (Season-Guard, ~Zeile 57)
- Test: `backend/tests/test_strava.py`, `backend/tests/test_seed.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_strava.py`:

```python
def test_backfill_from_nutzt_jahr_der_aktiven_season(session):
    from datetime import date, timedelta

    from app.models import Season

    heute = date.today()
    session.add(Season(year=heute.year - 1, goal_km=1000, milestones_json="[]",
                       start_date=heute - timedelta(days=300)))
    session.commit()
    assert strava._backfill_from(session) == date(heute.year - 1, 1, 1)


def test_backfill_from_ohne_season_aktuelles_jahr(session):
    from datetime import date

    assert strava._backfill_from(session) == date(date.today().year, 1, 1)
```

Ans Ende von `backend/tests/test_seed.py`:

```python
def test_seed_legt_keine_zweite_season_an(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    # Jahreswechsel: Seed mit neuem Jahr darf KEINE Season 2027 anlegen,
    # solange die 2026er-Saison existiert (läuft bis Stuttgartlauf 2027).
    seed_all(session, admin_user="chef", admin_password="geheim", year=2027)
    seasons = session.exec(select(Season)).all()
    assert [s.year for s in seasons] == [2026]
```

- [ ] **Step 2: Rot laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_strava.py tests/test_seed.py -q -k "backfill_from or zweite_season"`
Expected: FAIL (`_backfill_from` existiert nicht; Season 2027 wird angelegt)

- [ ] **Step 3: Implementieren**

`backend/app/services/strava.py` — Import ergänzen:

```python
from .season_window import current_season
```

Neue Funktion vor `backfill_current_year`:

```python
def _backfill_from(session: Session) -> date_type:
    """Importstart: 1. Januar des Jahres der aktiven Season — ein Neu-Connect
    im Frühjahr 2027 muss die 2026er-km der laufenden Saison mitholen.
    Der STRAVA_IMPORT_SINCE-Stichtag verschiebt weiterhin nach hinten."""
    season = current_season(session)
    jahr = season.year if season is not None else date_type.today().year
    start_date = date_type(jahr, 1, 1)
    since = config.strava_import_since()
    if since is not None and since > start_date:
        start_date = since
    return start_date
```

In `backfill_current_year` die drei Zeilen vor `year_start = ...` (Berechnung von `start_date` und `since`) entfernen und die Berechnung in den Session-Block verschieben — der Anfang der Funktion wird zu:

```python
def backfill_current_year(user_id: int) -> None:
    """Importiert alle Aktivitäten der laufenden Saison beim ersten Connect.
    Läuft als BackgroundTask, eigene DB-Session, idempotent, best-effort."""
    with Session(engine) as session:
        start_date = _backfill_from(session)
        year_start = int(
            datetime(start_date.year, start_date.month, start_date.day).timestamp()
        )
        conn = session.exec(
            select(StravaConnection).where(StravaConnection.user_id == user_id)
        ).first()
```

(Rest der Funktion unverändert; auf korrekte Einrückung achten — alles ab `conn = ...` liegt bereits im `with`-Block.)

`backend/app/seed.py` — den Season-Guard ersetzen — aus

```python
    if session.exec(select(Season).where(Season.year == year)).first() is None:
        session.add(Season(year=year, goal_km=1000.0))
```

wird

```python
    # Nur wenn noch GAR KEINE Season existiert — sonst würde am 01.01. des
    # Folgejahres eine leere Season entstehen, obwohl die Challenge noch läuft.
    if session.exec(select(Season)).first() is None:
        session.add(Season(year=year, goal_km=1000.0))
```

- [ ] **Step 4: Grün laufen lassen**

Run: `cd backend && uv run python -m pytest tests/test_strava.py tests/test_seed.py -q`
Expected: alle PASS

- [ ] **Step 5: Volle Backend-Suite**

Run: `cd backend && uv run python -m pytest -q`
Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/strava.py backend/app/seed.py backend/tests/test_strava.py backend/tests/test_seed.py
git commit -m "feat(season): Backfill ab Season-Jahr, Seed legt keine Zweit-Season an"
```

---

### Task 9: Frontend — Season-Typ + Helper `season.ts`

**Files:**
- Modify: `frontend/src/api/client.ts` (Season-Typ ~19, `patchSeason` ~281)
- Create: `frontend/src/components/ui/season.ts`
- Test: `frontend/src/components/ui/season.test.ts` (neu)

- [ ] **Step 1: Types erweitern**

`client.ts` — Typ `Season` um `end_date` ergänzen:

```ts
export type Season = {
  id: number
  year: number
  goal_km: number
  milestones: Milestone[]
  start_date: string | null
  end_date: string | null
}
```

`patchSeason` erweitern:

```ts
  patchSeason: (
    id: number,
    b: {
      goal_km?: number
      milestones?: Milestone[]
      start_date?: string | null
      end_date?: string | null
    },
  ) => request<Season>(`/api/seasons/${id}`, patch(b)),
```

- [ ] **Step 2: Failing Tests schreiben**

`frontend/src/components/ui/season.test.ts` (neu):

```ts
import { describe, expect, it } from 'vitest'
import type { Season } from '../../api/client'
import { aktiveSeason, saisonLabel } from './season'

const s = (over: Partial<Season>): Season => ({
  id: 1,
  year: 2026,
  goal_km: 1000,
  milestones: [],
  start_date: null,
  end_date: null,
  ...over,
})

const ts = (iso: string) => Date.parse(`${iso}T12:00:00`)

describe('aktiveSeason', () => {
  it('findet die jahresübergreifende Season im Februar 2027', () => {
    const seasons = [s({ start_date: '2026-07-20', end_date: '2027-05-16' })]
    expect(aktiveSeason(seasons, ts('2027-02-01'))?.year).toBe(2026)
  })

  it('nach dem Ende: die zuletzt begonnene Season', () => {
    const seasons = [s({ start_date: '2026-07-20', end_date: '2027-05-16' })]
    expect(aktiveSeason(seasons, ts('2027-06-01'))?.year).toBe(2026)
  })

  it('ohne Start/Ende: Kalenderjahr-Verhalten', () => {
    const seasons = [s({ year: 2025 }), s({ id: 2, year: 2026 })]
    expect(aktiveSeason(seasons, ts('2026-03-01'))?.year).toBe(2026)
    expect(aktiveSeason(seasons, ts('2025-03-01'))?.year).toBe(2025)
  })

  it('vor allen Fenstern: die als Nächstes beginnende', () => {
    const seasons = [s({ year: 2028, start_date: '2028-07-20' })]
    expect(aktiveSeason(seasons, ts('2027-12-01'))?.year).toBe(2028)
  })

  it('leere Liste: undefined', () => {
    expect(aktiveSeason([], ts('2026-01-01'))).toBeUndefined()
  })
})

describe('saisonLabel', () => {
  it('nur Jahr, wenn das Ende nicht jahresübergreifend ist', () => {
    expect(saisonLabel(s({}))).toBe('2026')
    expect(saisonLabel(s({ end_date: '2026-12-31' }))).toBe('2026')
  })

  it('Saison 2026/27 bei Ende im Folgejahr', () => {
    expect(saisonLabel(s({ end_date: '2027-05-16' }))).toBe('Saison 2026/27')
  })

  it('undefined: aktuelles Kalenderjahr', () => {
    expect(saisonLabel(undefined)).toBe(String(new Date().getFullYear()))
  })
})
```

- [ ] **Step 3: Rot laufen lassen**

Run: `cd frontend && npm run test -- season`
Expected: FAIL (Modul existiert nicht)

- [ ] **Step 4: Implementieren**

`frontend/src/components/ui/season.ts` (neu, vollständig):

```ts
import type { Season } from '../../api/client'

// Fensterstart = 1. Januar des Season-Jahres. Ende = end_date; fehlt es:
// mit start_date offen (Jahreswechsel!), ohne start_date 31.12. (Kalenderjahr).
function fensterStart(s: Season): number {
  return Date.parse(`${s.year}-01-01T00:00:00`)
}

function fensterEnde(s: Season): number | null {
  if (s.end_date) return Date.parse(`${s.end_date}T23:59:59`)
  if (s.start_date) return null
  return Date.parse(`${s.year}-12-31T23:59:59`)
}

export function aktiveSeason(seasons: Season[], now = Date.now()): Season | undefined {
  const begonnen = seasons.filter((s) => fensterStart(s) <= now)
  const enthaltend = begonnen.filter((s) => {
    const ende = fensterEnde(s)
    return ende === null || now <= ende
  })
  const spaetesterStart = (a: Season, b: Season) => fensterStart(b) - fensterStart(a)
  if (enthaltend.length > 0) return [...enthaltend].sort(spaetesterStart)[0]
  if (begonnen.length > 0) return [...begonnen].sort(spaetesterStart)[0]
  return [...seasons].sort((a, b) => fensterStart(a) - fensterStart(b))[0]
}

export function saisonLabel(season: Season | undefined): string {
  if (!season) return String(new Date().getFullYear())
  const endJahr = season.end_date ? Number(season.end_date.slice(0, 4)) : season.year
  if (endJahr === season.year) return String(season.year)
  return `Saison ${season.year}/${String(endJahr).slice(2)}`
}
```

- [ ] **Step 5: Grün laufen lassen**

Run: `cd frontend && npm run test -- season && npm run lint`
Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/ui/season.ts frontend/src/components/ui/season.test.ts
git commit -m "feat(season): Frontend-Helper aktiveSeason/saisonLabel + end_date-Typ"
```

---

### Task 10: Frontend — alle `getFullYear()`-Stellen auf aktive Season umstellen

**Files:**
- Modify: `frontend/src/components/ui/Layout.tsx` (~Zeile 26)
- Modify: `frontend/src/components/ui/CountdownBanner.tsx` (~Zeile 13)
- Modify: `frontend/src/pages/Vergleich.tsx` (~Zeile 50–55, Select ~99)
- Modify: `frontend/src/pages/Wetten.tsx` (~Zeile 20–24)
- Modify: `frontend/src/pages/Archiv.tsx` (~Zeile 8)
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx` (~Zeile 11, Überschrift ~75)
- Test: bestehende Tests (`Wetten.test.tsx`, `MeineAktivitaeten.test.tsx` u. a. brauchen ggf. einen `seasons`-Mock)

- [ ] **Step 1: Implementieren**

`Layout.tsx` — Import + Ersetzung:

```tsx
import { aktiveSeason } from './season'
```

Aus `const season = seasons?.find((s) => s.year === new Date().getFullYear())` wird:

```tsx
  const season = aktiveSeason(seasons ?? [])
```

`CountdownBanner.tsx` — gleiches Muster:

```tsx
import { aktiveSeason } from './season'
```

```tsx
  const season = aktiveSeason(seasons ?? [])
```

`Vergleich.tsx` — Import:

```tsx
import { aktiveSeason, saisonLabel } from '../components/ui/season'
```

Aus `const [year, setYear] = useState(new Date().getFullYear())` wird (abgeleiteter Default, Nutzerwahl gewinnt):

```tsx
  const [gewaehlt, setGewaehlt] = useState<number | null>(null)
  const year = gewaehlt ?? aktiveSeason(seasons)?.year ?? new Date().getFullYear()
```

Im Jahr-`Select`: `onChange={(e) => setGewaehlt(Number(e.target.value))}` und die Option-Beschriftung `{s.year}` → `{saisonLabel(s)}` (Label „Jahr" → „Saison").

`Wetten.tsx` — Import + seasons-Query + Ersetzung:

```tsx
import { aktiveSeason } from '../components/ui/season'
```

```tsx
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const year = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
```

(ersetzt `const year = new Date().getFullYear()`.)

`Archiv.tsx` — Import + seasons-Query + Ersetzung (`useQuery` ist dort schon importiert):

```tsx
import { aktiveSeason } from '../components/ui/season'
```

```tsx
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const year = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
```

Achtung: Die `comparisonWarmup`-Query läuft dann kurz mit dem Fallback-Jahr, bis seasons geladen ist — akzeptabel (gleicher Refetch wie heute bei Cache-Invalidierung).

`MeineAktivitaeten.tsx` — Import + seasons-Query + Ersetzung + Überschrift:

```tsx
import { aktiveSeason, saisonLabel } from '../components/ui/season'
```

```tsx
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season = aktiveSeason(seasons)
  const year = season?.year ?? new Date().getFullYear()
```

Überschrift `Meine Einträge {year}` → `Meine Einträge {saisonLabel(season)}`.

- [ ] **Step 2: Tests fixen (seasons-Mock)**

`npm run test` laufen lassen. Testdateien, deren `vi.mock('../api/client', ...)` kein `seasons` hat (mindestens `Wetten.test.tsx`, `MeineAktivitaeten.test.tsx`), bekommen im api-Mock:

```tsx
    seasons: vi.fn().mockResolvedValue([]),
```

(Leere Liste = Kalenderjahr-Fallback, Bestandsverhalten der Tests bleibt.)

- [ ] **Step 3: Grün laufen lassen**

Run: `cd frontend && npm run test && npm run lint && npm run build`
Expected: alle PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Layout.tsx frontend/src/components/ui/CountdownBanner.tsx frontend/src/pages/Vergleich.tsx frontend/src/pages/Wetten.tsx frontend/src/pages/Archiv.tsx frontend/src/pages/MeineAktivitaeten.tsx frontend/src/pages/Wetten.test.tsx frontend/src/pages/MeineAktivitaeten.test.tsx
git commit -m "feat(season): Frontend nutzt aktive Season statt Kalenderjahr"
```

---

### Task 11: Admin-Panel — Start-/Enddatum-Felder in der Season-Sektion

**Files:**
- Modify: `frontend/src/pages/Admin.tsx` (Funktion `Jahr`, ~Zeile 367)
- Test: `frontend/src/pages/Admin.test.tsx` (nur falls dort die Jahr-Sektion getestet wird — prüfen; sonst manueller Check in Task 12)

Hinweis: Das Admin-Panel hatte bislang **kein** Startdatum-Feld (der Wert kam per Migration). Beide Felder kommen jetzt dazu.

- [ ] **Step 1: Implementieren**

In `Admin.tsx`, Funktion `Jahr()`:

Import oben ergänzen:

```tsx
import { aktiveSeason, saisonLabel } from '../components/ui/season'
```

Season-Auflösung ersetzen — aus

```tsx
  const season: Season | undefined = seasons.find((s) => s.year === new Date().getFullYear())
```

wird

```tsx
  const season: Season | undefined = aktiveSeason(seasons)
```

State ergänzen (bei `goal`/`milestones`; `null` = Feld nicht angefasst):

```tsx
  const [startDatum, setStartDatum] = useState<string | null>(null)
  const [endDatum, setEndDatum] = useState<string | null>(null)
```

Collapsible-Titel: `title={`Jahr ${season.year}`}` → ``title={`Saison ${saisonLabel(season)}`}``.

Nach dem Ziel-Input zwei Datumsfelder einfügen:

```tsx
      <div className="mt-3 flex flex-wrap gap-3">
        <Input
          label="Challenge-Start"
          type="date"
          className="w-40"
          defaultValue={season.start_date ?? ''}
          onChange={(e) => setStartDatum(e.target.value)}
        />
        <Input
          label="Challenge-Ende (leer = offen)"
          type="date"
          className="w-40"
          defaultValue={season.end_date ?? ''}
          onChange={(e) => setEndDatum(e.target.value)}
        />
      </div>
```

Im Speichern-Button den Patch-Payload erweitern:

```tsx
            api
              .patchSeason(season.id, {
                goal_km: goal ? parseFloat(goal) : undefined,
                milestones: ms,
                ...(startDatum !== null ? { start_date: startDatum || null } : {}),
                ...(endDatum !== null ? { end_date: endDatum || null } : {}),
              })
```

(Feld geleert = `null` = Datum löschen; nie angefasst = nicht mitschicken.)

- [ ] **Step 2: Tests prüfen/ergänzen**

`Admin.test.tsx` öffnen: falls die Jahr-Sektion dort gerendert wird und der seasons-Mock eine Season liefert, einen Test ergänzen:

```tsx
  it('zeigt Start- und Enddatum der Saison', async () => {
    renderAdmin()  // bestehende Render-Hilfsfunktion der Datei verwenden
    expect(await screen.findByLabelText('Challenge-Start')).toBeInTheDocument()
    expect(screen.getByLabelText('Challenge-Ende (leer = offen)')).toBeInTheDocument()
  })
```

Falls der seasons-Mock der Datei `end_date` nicht kennt, dort `end_date: null` ergänzen (Pflichtfeld im Season-Typ seit Task 9).

- [ ] **Step 3: Grün laufen lassen**

Run: `cd frontend && npm run test && npm run lint && npm run build`
Expected: alle PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Admin.tsx frontend/src/pages/Admin.test.tsx
git commit -m "feat(season): Start- und Enddatum im Admin-Panel"
```

---

### Task 12: Gesamtverifikation + PR

- [ ] **Step 1: Volle Suiten**

Run: `cd backend && uv run python -m pytest -q`
Expected: alle PASS

Run: `cd frontend && npm run lint && npm run test && npm run build`
Expected: alle PASS

- [ ] **Step 2: End-to-End-Check (verify-Skill nutzen)**

Backend mit frischer Temp-DB starten und per API prüfen:
1. Admin: `PATCH /api/seasons/{id}` mit `end_date` setzen → `GET /api/seasons` liefert es; `end_date` vor `start_date` → 422; `end_date: null` löscht.
2. Aktivität mit Datum nach `end_date` direkt in die DB legen (oder end_date in die Vergangenheit setzen und Aktivität heute anlegen) → `GET /api/comparison/{year}` zählt sie nicht (Freeze), `GET /api/activities?year=` zeigt sie nicht, `GET /api/points` bucht kein Einkommen dafür.
3. `end_date` wieder löschen → alles zählt wieder (Fenster offen).
4. UI-Kurzcheck über den Dev-Server: Admin-Sektion „Saison" zeigt beide Datumsfelder; Vergleich/Aktivitäten laufen unverändert.

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feature/season-zeitrahmen
gh pr create --title "Season-Zeitrahmen: Enddatum statt Kalenderjahr" --body "Implementiert docs/superpowers/specs/2026-07-16-season-zeitrahmen-design.md. Season.end_date (Admin-Panel), Fenster-Wertung über den Jahreswechsel (Challenge bis Stuttgartlauf 2027), Freeze nach Saisonende, current_season/aktiveSeason ersetzen alle Kalenderjahr-Stellen, Seed-Guard gegen Phantom-Season 2027.

Review-Fokus: Fenster-Definition (Start immer 1.1. des Season-Jahres, Ende offen bei fehlendem end_date) und Freeze-Verhalten."
```
