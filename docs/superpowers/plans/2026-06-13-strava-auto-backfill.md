# Strava Auto-Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beim erstmaligen Strava-Connect automatisch alle Aktivitäten des laufenden Kalenderjahres importieren, im Hintergrund, mit Fortschrittsanzeige und Abschluss-Toast im UI.

**Architecture:** FastAPI-`BackgroundTask` beim OAuth-Callback startet `backfill_current_year`, das die Strava-Summary-Liste (`/athlete/activities?after=...`) holt und jede Aktivität über einen gemeinsamen `import_activity`-Helper idempotent importiert. Fortschritt (`backfill_state/total/done`) liegt auf der `StravaConnection`. Das Frontend pollt `/api/strava/status` solange `state==running` und zeigt „Importiere… X von Y" + Abschluss-Toast.

**Tech Stack:** Python/FastAPI/SQLModel/httpx (Backend), pytest; React 19/TanStack Query v5/Vitest (Frontend).

**Spec:** `docs/superpowers/specs/2026-06-13-strava-auto-backfill-design.md`

**Branch:** `feature/strava-auto-backfill` (bereits angelegt, Spec committet)

**Konventionen aus dem Repo (wichtig):**
- Backend-Tests laufen aus `backend/`: `uv run pytest`. httpx wird in Tests **nicht** echt aufgerufen, sondern Funktionen wie `strava.fetch_activity` / `strava.valid_access_token` per `monkeypatch` ersetzt.
- SQLModel-Tabellenname der Verbindung = `stravaconnection` (Klassenname lowercase).
- Frontend-Tests aus `frontend/`: `npm test`. `api`-Client und `./Toast` werden per `vi.mock` ersetzt.
- Commits klein und häufig; Stil wie im Repo (`feat(strava): …`, `test(strava): …`, deutsch, klein).

---

## Task 1: `StravaConnection`-Felder + Migration

**Files:**
- Modify: `backend/app/models.py` (Klasse `StravaConnection`)
- Modify: `backend/app/db.py` (`migrate`)
- Test: `backend/tests/test_migration.py`

- [ ] **Step 1: Failing-Test für die Migration schreiben**

In `backend/tests/test_migration.py` ans Dateiende anhängen:

```python
def test_migrate_adds_backfill_columns(tmp_path):
    from sqlalchemy import text
    from sqlmodel import create_engine

    from app import db

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE stravaconnection (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "athlete_id INTEGER, access_token VARCHAR, refresh_token VARCHAR, "
            "expires_at INTEGER, created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO stravaconnection (id, user_id, athlete_id, access_token, "
            "refresh_token, expires_at) VALUES (1, 1, 99, 'a', 'r', 123)"
        ))

    db.migrate(engine)

    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("stravaconnection")'))]
        assert "backfill_state" in cols
        assert "backfill_total" in cols
        assert "backfill_done" in cols
        row = conn.execute(text(
            "SELECT backfill_state, backfill_total, backfill_done FROM stravaconnection WHERE id = 1"
        )).first()
        assert row == ("idle", 0, 0)
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && uv run pytest tests/test_migration.py::test_migrate_adds_backfill_columns -v`
Expected: FAIL (Spalten existieren nicht).

- [ ] **Step 3: Migration implementieren**

In `backend/app/db.py`, innerhalb von `migrate()`, am Ende des `with target.begin() as conn:`-Blocks (nach dem `season`-Block) ergänzen:

```python
        if _table_exists(conn, "stravaconnection"):
            sc_cols = _columns(conn, "stravaconnection")
            if "backfill_state" not in sc_cols:
                conn.execute(text(
                    "ALTER TABLE stravaconnection ADD COLUMN backfill_state TEXT NOT NULL DEFAULT 'idle'"
                ))
            if "backfill_total" not in sc_cols:
                conn.execute(text(
                    "ALTER TABLE stravaconnection ADD COLUMN backfill_total INTEGER NOT NULL DEFAULT 0"
                ))
            if "backfill_done" not in sc_cols:
                conn.execute(text(
                    "ALTER TABLE stravaconnection ADD COLUMN backfill_done INTEGER NOT NULL DEFAULT 0"
                ))
```

- [ ] **Step 4: Felder am Modell ergänzen**

In `backend/app/models.py`, Klasse `StravaConnection`, nach `created_at`:

```python
    backfill_state: str = "idle"  # "idle" | "running" | "done" | "error"
    backfill_total: int = 0
    backfill_done: int = 0
```

- [ ] **Step 5: Tests laufen lassen, grün bestätigen**

Run: `cd backend && uv run pytest tests/test_migration.py -v`
Expected: PASS (alle Migrations-Tests, inkl. neuem).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_migration.py
git commit -m "feat(strava): backfill-status-felder auf stravaconnection + migration"
```

---

## Task 2: Gemeinsamen `import_activity`-Helper extrahieren (Refactor)

Ziel: Die Insert-Logik aus `handle_webhook_event` in `import_activity(session, conn, data) -> bool` herauslösen. Verhalten bleibt identisch; bestehende Webhook-Tests bleiben grün.

**Files:**
- Modify: `backend/app/services/strava.py`
- Test: `backend/tests/test_strava.py`

- [ ] **Step 1: Failing-Test für den neuen Helper schreiben**

In `backend/tests/test_strava.py` ergänzen (nach den bestehenden `handle_webhook_event`-Tests):

```python
def test_import_activity_inserts_and_is_idempotent(session):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    data = {"id": 999, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
            "start_date_local": "2026-03-01T07:00:00Z", "name": "Lauf"}
    assert strava.import_activity(session, conn, data) is True
    assert strava.import_activity(session, conn, data) is False  # Dublette
    acts = session.exec(select(Activity)).all()
    assert len(acts) == 1
    assert acts[0].external_id == "999"
    assert acts[0].distance_km == 5.0
    assert acts[0].duration_min == 30
    assert acts[0].source == "strava"


def test_import_activity_skips_unmapped_and_zero(session):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    assert strava.import_activity(session, conn,
        {"id": 1, "sport_type": "Swim", "distance": 2000.0}) is False  # ungemappt
    assert strava.import_activity(session, conn,
        {"id": 2, "sport_type": "Run", "distance": 0}) is False  # distanz 0
    assert session.exec(select(Activity)).all() == []
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py::test_import_activity_inserts_and_is_idempotent tests/test_strava.py::test_import_activity_skips_unmapped_and_zero -v`
Expected: FAIL (`module 'app.services.strava' has no attribute 'import_activity'`).

- [ ] **Step 3: Helper implementieren + `handle_webhook_event` darauf umstellen**

In `backend/app/services/strava.py` `handle_webhook_event` durch folgende zwei Funktionen ersetzen (das `object_id`-Feld nutzt `data["id"]`):

```python
def import_activity(session: Session, conn: StravaConnection, data: dict) -> bool:
    """Importiert eine Strava-Aktivität (Summary oder Detail) idempotent.
    Gibt True zurück, wenn neu angelegt; False bei Skip/Dublette."""
    activity_id = data.get("id")
    existing = session.exec(
        select(Activity).where(
            Activity.user_id == conn.user_id,
            Activity.external_id == str(activity_id),
            Activity.source == "strava",
        )
    ).first()
    if existing is not None:
        return False
    cat = category_for_sport(session, data.get("sport_type") or data.get("type"))
    if cat is None:
        return False
    distance_km = round((data.get("distance") or 0) / 1000, 2)
    if distance_km <= 0:
        return False
    duration_min = round((data.get("moving_time") or 0) / 60) or None
    act = Activity(
        user_id=conn.user_id,
        category_id=cat.id,
        date=_parse_date(data.get("start_date_local") or data.get("start_date")),
        distance_km=distance_km,
        duration_min=duration_min,
        note=data.get("name"),
        source="strava",
        external_id=str(activity_id),
    )
    session.add(act)
    session.commit()
    return True


def handle_webhook_event(session: Session, payload: dict) -> None:
    """Importiert genau neue Strava-Aktivitäten (aspect 'create'). Idempotent über external_id."""
    if payload.get("object_type") != "activity" or payload.get("aspect_type") != "create":
        return
    owner_id = payload.get("owner_id")
    activity_id = payload.get("object_id")
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.athlete_id == owner_id)
    ).first()
    if conn is None:
        return
    token = valid_access_token(session, conn)
    data = fetch_activity(token, activity_id)
    data.setdefault("id", activity_id)
    import_activity(session, conn, data)
```

- [ ] **Step 4: Gesamte Strava-Testdatei laufen lassen, grün bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py -v`
Expected: PASS (neue Helper-Tests **und** alle bestehenden `handle_webhook_event`-Tests — Verhalten unverändert).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strava.py backend/tests/test_strava.py
git commit -m "refactor(strava): import-kernlogik in import_activity-helper auslagern"
```

---

## Task 3: `backfill_current_year` implementieren

**Files:**
- Modify: `backend/app/services/strava.py`
- Test: `backend/tests/test_strava.py`

- [ ] **Step 1: Failing-Tests schreiben**

In `backend/tests/test_strava.py` ergänzen. Diese Tests mocken die HTTP-Liste über `monkeypatch` auf eine Hilfsfunktion `fetch_athlete_activities` (in Step 3 angelegt) und ersetzen `valid_access_token`:

```python
def test_backfill_imports_mapped_activities_and_tracks_progress(session, monkeypatch):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    make_category(session, name="Radfahren", strava_sport_types='["Ride"]')
    activities = [
        {"id": 1, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
         "start_date_local": "2026-02-01T07:00:00Z", "name": "Lauf"},
        {"id": 2, "sport_type": "Ride", "distance": 20000.0, "moving_time": 3600,
         "start_date_local": "2026-02-02T07:00:00Z", "name": "Tour"},
        {"id": 3, "sport_type": "Swim", "distance": 1000.0, "moving_time": 1800,
         "start_date_local": "2026-02-03T07:00:00Z", "name": "Bad"},  # ungemappt
    ]
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_athlete_activities", lambda tok, after: activities)

    strava.backfill_current_year(user.id)

    fresh = session.get(StravaConnection, conn.id)
    session.refresh(fresh)
    assert fresh.backfill_state == "done"
    assert fresh.backfill_total == 2   # nur Run + Ride sind importierbar
    assert fresh.backfill_done == 2
    acts = session.exec(select(Activity).where(Activity.source == "strava")).all()
    assert {a.external_id for a in acts} == {"1", "2"}


def test_backfill_is_idempotent(session, monkeypatch):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    activities = [{"id": 1, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
                   "start_date_local": "2026-02-01T07:00:00Z", "name": "Lauf"}]
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_athlete_activities", lambda tok, after: activities)

    strava.backfill_current_year(user.id)
    strava.backfill_current_year(user.id)

    assert len(session.exec(select(Activity).where(Activity.source == "strava")).all()) == 1


def test_backfill_sets_error_on_http_failure(session, monkeypatch):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    def boom(tok, after):
        raise RuntimeError("strava down")
    monkeypatch.setattr(strava, "fetch_athlete_activities", boom)

    strava.backfill_current_year(user.id)

    fresh = session.get(StravaConnection, conn.id)
    session.refresh(fresh)
    assert fresh.backfill_state == "error"


def test_backfill_noop_without_connection(session, monkeypatch):
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    called = {"list": False}
    monkeypatch.setattr(strava, "fetch_athlete_activities",
                        lambda tok, after: called.__setitem__("list", True) or [])
    strava.backfill_current_year(user_id=4242)  # kein User/keine Connection
    assert called["list"] is False
```

> Hinweis: Die Tests rufen `backfill_current_year` mit der test-eigenen In-Memory-DB auf. Damit die Funktion dieselbe Engine wie der `session`-Fixture benutzt, öffnet sie ihre Session über `app.db.engine`. Im Test wird `engine` deshalb auf die Fixture-Engine gepatcht — siehe Step 2.

- [ ] **Step 2: Test-Fixture für die Engine-Bindung ergänzen**

Damit `backfill_current_year` (das eine eigene Session via `db.engine` öffnet) im Test die Fixture-Tabellen sieht, in `backend/tests/test_strava.py` oben eine Hilfsfixture ergänzen und in den drei Backfill-Tests verwenden, die eine Connection brauchen. Konkret: die Backfill-Tests bekommen zusätzlich das Argument `bind_engine` und der Fixture-Body patcht `app.db.engine` sowie `app.services.strava.engine` auf die Engine der Session:

```python
@pytest.fixture
def bind_engine(session, monkeypatch):
    bind = session.get_bind()
    from app import db
    from app.services import strava as strava_svc
    monkeypatch.setattr(db, "engine", bind)
    monkeypatch.setattr(strava_svc, "engine", bind)
    return bind
```

Die vier Backfill-Tests aus Step 1 erhalten `bind_engine` als zusätzlichen Parameter, z. B.:
`def test_backfill_imports_mapped_activities_and_tracks_progress(session, monkeypatch, bind_engine):`

(`strava.py` importiert `engine` aus `..db` — Patchen von `strava_svc.engine` trifft den dort gebundenen Namen.)

- [ ] **Step 3: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py -k backfill -v`
Expected: FAIL (`fetch_athlete_activities` / `backfill_current_year` existieren nicht).

- [ ] **Step 4: Implementieren**

In `backend/app/services/strava.py` die Imports oben ergänzen (Datei beginnt bereits mit `from datetime import date as date_type` und importiert `time`):

```python
from datetime import datetime as _dt
```

Dann am Dateiende ergänzen:

```python
def fetch_athlete_activities(access_token: str, after: int) -> list[dict]:
    """Holt Summary-Aktivitäten ab Epoch `after`, paginiert (100/Seite)."""
    out: list[dict] = []
    page = 1
    while True:
        r = httpx.get(
            f"{API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after, "per_page": 100, "page": page},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def _is_importable(session: Session, data: dict) -> bool:
    if category_for_sport(session, data.get("sport_type") or data.get("type")) is None:
        return False
    return (data.get("distance") or 0) > 0


def backfill_current_year(user_id: int) -> None:
    """Importiert alle Aktivitäten des laufenden Kalenderjahres beim ersten Connect.
    Läuft als BackgroundTask, eigene DB-Session, idempotent, best-effort."""
    year_start = int(_dt(date_type.today().year, 1, 1).timestamp())
    with Session(engine) as session:
        conn = session.exec(
            select(StravaConnection).where(StravaConnection.user_id == user_id)
        ).first()
        if conn is None:
            return
        conn.backfill_state = "running"
        conn.backfill_done = 0
        conn.backfill_total = 0
        session.add(conn)
        session.commit()
        try:
            token = valid_access_token(session, conn)
            activities = fetch_athlete_activities(token, year_start)
            importable = [a for a in activities if _is_importable(session, a)]
            conn.backfill_total = len(importable)
            session.add(conn)
            session.commit()
            for data in importable:
                # Connection könnte zwischenzeitlich getrennt worden sein
                if session.get(StravaConnection, conn.id) is None:
                    return
                if import_activity(session, conn, data):
                    conn.backfill_done += 1
                    session.add(conn)
                    session.commit()
            conn.backfill_state = "done"
            session.add(conn)
            session.commit()
        except Exception:
            conn.backfill_state = "error"
            session.add(conn)
            session.commit()
```

- [ ] **Step 5: Tests laufen lassen, grün bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py -k backfill -v`
Expected: PASS (alle vier Backfill-Tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/strava.py backend/tests/test_strava.py
git commit -m "feat(strava): backfill_current_year fuer import des laufenden jahres"
```

---

## Task 4: Backfill im Callback auslösen

**Files:**
- Modify: `backend/app/routers/strava_router.py` (`callback`)
- Test: `backend/tests/test_strava.py`

- [ ] **Step 1: Failing-Test schreiben**

In `backend/tests/test_strava.py` ergänzen:

```python
def test_callback_triggers_backfill_on_fresh_connect(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    from app.routers import strava_router
    user = make_user(session)
    login(client)
    state = strava_router._state_serializer.dumps(user.id)
    monkeypatch.setattr(strava_router.strava, "exchange_code", lambda code: {
        "access_token": "AT", "refresh_token": "RT", "expires_at": 8888888888,
        "athlete": {"id": 77},
    })
    triggered = {"user_id": None}
    monkeypatch.setattr(strava_router.strava, "backfill_current_year",
                        lambda uid: triggered.__setitem__("user_id", uid))
    r = client.get("/api/strava/callback", params={"code": "xyz", "state": state},
                   follow_redirects=False)
    assert r.status_code in (302, 307)
    assert triggered["user_id"] == user.id


def test_callback_no_backfill_on_existing_connection(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    from app.routers import strava_router
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=77,
                                 access_token="old", refresh_token="old", expires_at=1))
    session.commit()
    login(client)
    state = strava_router._state_serializer.dumps(user.id)
    monkeypatch.setattr(strava_router.strava, "exchange_code", lambda code: {
        "access_token": "AT", "refresh_token": "RT", "expires_at": 8888888888,
        "athlete": {"id": 77},
    })
    triggered = {"called": False}
    monkeypatch.setattr(strava_router.strava, "backfill_current_year",
                        lambda uid: triggered.__setitem__("called", True))
    client.get("/api/strava/callback", params={"code": "xyz", "state": state},
               follow_redirects=False)
    assert triggered["called"] is False
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py -k "callback_triggers_backfill or callback_no_backfill" -v`
Expected: FAIL (Backfill wird nicht ausgelöst).

- [ ] **Step 3: Callback anpassen**

In `backend/app/routers/strava_router.py`:

Import-Zeile (oben) um `BackgroundTasks` ergänzen — `from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request` ist bereits vorhanden, also nichts zu tun.

`callback`-Signatur und -Body so ändern, dass bei neuer Verbindung der Backfill angehängt wird:

```python
@router.get("/callback")
def callback(
    background_tasks: BackgroundTasks,
    code: str | None = None,
    state: str | None = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_enabled()
    if not code or not state:
        raise HTTPException(status_code=400, detail="Fehlende OAuth-Parameter")
    try:
        state_user_id = _state_serializer.loads(state, max_age=600)
    except BadSignature:
        raise HTTPException(status_code=400, detail="Ungültiger State")
    if state_user_id != user.id:
        raise HTTPException(status_code=400, detail="State passt nicht zum angemeldeten User")
    data = strava.exchange_code(code)
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    is_new = conn is None
    if conn is None:
        conn = StravaConnection(
            user_id=user.id, athlete_id=0, access_token="", refresh_token="", expires_at=0
        )
    conn.athlete_id = data["athlete"]["id"]
    strava.apply_tokens(conn, data)
    session.add(conn)
    session.commit()
    if is_new:
        background_tasks.add_task(strava.backfill_current_year, user.id)
    return RedirectResponse("/?strava=connected")
```

> Hinweis: In FastAPI muss der `BackgroundTasks`-Parameter ohne Default zuerst stehen — daher die geänderte Reihenfolge der Argumente.

- [ ] **Step 4: Tests laufen lassen, grün bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py -v`
Expected: PASS (neue Callback-Tests + bestehender `test_callback_stores_connection`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/strava_router.py backend/tests/test_strava.py
git commit -m "feat(strava): backfill als background-task beim ersten connect ausloesen"
```

---

## Task 5: `/status` um `backfill`-Block erweitern

**Files:**
- Modify: `backend/app/routers/strava_router.py` (`status`)
- Test: `backend/tests/test_strava.py` (bestehenden Test anpassen + neuen)

- [ ] **Step 1: Bestehenden Test anpassen + neuen Test schreiben**

In `backend/tests/test_strava.py` den bestehenden `test_status_connected` so ersetzen, dass er den `backfill`-Block erwartet, und einen neuen Test für den laufenden Import ergänzen:

```python
def test_status_connected(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=42,
                                 access_token="a", refresh_token="r", expires_at=999))
    session.commit()
    login(client)
    r = client.get("/api/strava/status")
    assert r.json() == {
        "enabled": True, "connected": True, "athlete_id": 42,
        "backfill": {"state": "idle", "total": 0, "done": 0},
    }


def test_status_reports_running_backfill(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(
        user_id=user.id, athlete_id=42, access_token="a", refresh_token="r",
        expires_at=999, backfill_state="running", backfill_total=52, backfill_done=10))
    session.commit()
    login(client)
    r = client.get("/api/strava/status")
    assert r.json()["backfill"] == {"state": "running", "total": 52, "done": 10}
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd backend && uv run pytest tests/test_strava.py -k status -v`
Expected: FAIL (`test_status_connected` und `test_status_reports_running_backfill` — kein `backfill`-Key).

- [ ] **Step 3: `status` erweitern**

In `backend/app/routers/strava_router.py` die `status`-Funktion ersetzen:

```python
@router.get("/status")
def status(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if not config.strava_enabled():
        return {"enabled": False, "connected": False}
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    result = {
        "enabled": True,
        "connected": conn is not None,
        "athlete_id": conn.athlete_id if conn else None,
    }
    if conn is not None:
        result["backfill"] = {
            "state": conn.backfill_state,
            "total": conn.backfill_total,
            "done": conn.backfill_done,
        }
    return result
```

- [ ] **Step 4: Gesamte Backend-Suite laufen lassen, grün bestätigen**

Run: `cd backend && uv run pytest -v`
Expected: PASS (alle Tests inkl. `test_status_disabled_when_unconfigured`, das weiterhin `{"enabled": False, "connected": False}` erwartet).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/strava_router.py backend/tests/test_strava.py
git commit -m "feat(strava): backfill-status im /status-endpoint ausgeben"
```

---

## Task 6: Frontend-Typ `StravaStatus` erweitern

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Typ erweitern**

In `frontend/src/api/client.ts` den `StravaStatus`-Typ ersetzen:

```typescript
export type StravaBackfill = {
  state: 'idle' | 'running' | 'done' | 'error'
  total: number
  done: number
}
export type StravaStatus = {
  enabled: boolean
  connected: boolean
  athlete_id?: number | null
  backfill?: StravaBackfill
}
```

- [ ] **Step 2: Typecheck/Build laufen lassen**

Run: `cd frontend && npx tsc --noEmit`
Expected: PASS (keine Typfehler).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(strava): StravaStatus-typ um backfill-block erweitern"
```

---

## Task 7: `ProfilModal` — Polling, Fortschritt, Toast

**Files:**
- Modify: `frontend/src/components/ui/ProfilModal.tsx`
- Test: `frontend/src/components/ui/ProfilModal.test.tsx`

- [ ] **Step 1: Failing-Tests schreiben**

In `frontend/src/components/ui/ProfilModal.test.tsx` den Toast-Mock so ändern, dass ein steuerbarer Spy entsteht, und Tests ergänzen. Die Datei-Oberseite anpassen:

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import ProfilModal from './ProfilModal'

const me: Me = { id: 1, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

const stravaStatus = vi.fn()
const toastSpy = vi.fn()
vi.mock('../../api/client', () => ({
  api: { patchMe: vi.fn(), stravaStatus: () => stravaStatus(), disconnectStrava: vi.fn() },
}))
vi.mock('./Toast', () => ({ useToast: () => toastSpy }))

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={qc}>
      <ProfilModal me={me} open onClose={vi.fn()} />
    </QueryClientProvider>,
  )
  return { qc, ...utils }
}
```

Die bestehenden drei Tests bleiben unverändert. Danach ergänzen:

```typescript
describe('ProfilModal Strava-Backfill', () => {
  it('zeigt Importfortschritt bei state running', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'running', total: 52, done: 23 },
    })
    renderModal()
    expect(await screen.findByText(/Importiere… 23 von 52/)).toBeInTheDocument()
  })

  it('feuert Toast beim Übergang running → done', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'running', total: 52, done: 50 },
    })
    const { qc } = renderModal()
    await screen.findByText(/Importiere…/)
    toastSpy.mockClear()
    act(() => {
      qc.setQueryData(['strava-status'], {
        enabled: true, connected: true, athlete_id: 42,
        backfill: { state: 'done', total: 52, done: 52 },
      })
    })
    expect(toastSpy).toHaveBeenCalledWith('52 Aktivitäten importiert', 'ok')
  })

  it('kein Toast, wenn Modal erst im done-Zustand öffnet', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'done', total: 52, done: 52 },
    })
    renderModal()
    await screen.findByRole('button', { name: /Strava trennen/ })
    expect(toastSpy).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag bestätigen**

Run: `cd frontend && npm test -- ProfilModal`
Expected: FAIL (kein Fortschrittstext, kein Toast).

- [ ] **Step 3: `ProfilModal.tsx` implementieren**

In `frontend/src/components/ui/ProfilModal.tsx`:

Imports oben ergänzen (`useEffect`, `useRef`):

```typescript
import { useEffect, useRef, useState } from 'react'
```

Die `strava-status`-Query mit Polling und einen Effekt für Toast/Invalidierung ergänzen. Den `useQuery`-Aufruf ersetzen:

```typescript
  const { data: strava } = useQuery({
    queryKey: ['strava-status'],
    queryFn: api.stravaStatus,
    refetchInterval: (query) =>
      query.state.data?.backfill?.state === 'running' ? 1500 : false,
  })

  const prevBackfill = useRef<string | undefined>(undefined)
  useEffect(() => {
    const state = strava?.backfill?.state
    if (prevBackfill.current === 'running' && state === 'done') {
      const total = strava?.backfill?.total ?? 0
      if (total > 0) toast(`${total} Aktivitäten importiert`, 'ok')
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
      queryClient.invalidateQueries({ queryKey: ['activities'] })
    }
    prevBackfill.current = state
  }, [strava?.backfill?.state, strava?.backfill?.total, queryClient, toast])
```

In der Strava-Box (`{strava?.enabled && (...)}`) den `connected`-Zweig so anpassen, dass bei laufendem Import der Fortschritt statt des Trennen-Buttons erscheint:

```tsx
            {strava.connected ? (
              strava.backfill?.state === 'running' ? (
                <div className="flex items-center gap-2 text-sm text-ink-mute">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Importiere… {strava.backfill.done} von {strava.backfill.total}
                </div>
              ) : (
                <Button
                  variant="ghost"
                  className="w-full"
                  onClick={() => trennen.mutate()}
                  disabled={trennen.isPending}
                >
                  Strava trennen
                </Button>
              )
            ) : (
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => {
                  window.location.href = '/api/strava/connect'
                }}
              >
                Mit Strava verbinden
              </Button>
            )}
```

- [ ] **Step 4: Tests laufen lassen, grün bestätigen**

Run: `cd frontend && npm test -- ProfilModal`
Expected: PASS (alle alten + neuen Tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/ProfilModal.tsx frontend/src/components/ui/ProfilModal.test.tsx
git commit -m "feat(strava): import-fortschritt + abschluss-toast im profil-modal"
```

---

## Task 8: README-Hinweis + Gesamt-Verifikation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README ergänzen**

In `README.md` im Abschnitt „Strava-Integration (optional)", nach dem Absatz über die Webhook-Subscription, ergänzen:

```markdown
Beim **erstmaligen Verbinden** eines Strava-Accounts werden automatisch alle
Aktivitäten des laufenden Kalenderjahres im Hintergrund importiert (nur gemappte
Sport-Typen, idempotent). Der Fortschritt wird im Profil-Modal angezeigt.
```

- [ ] **Step 2: Gesamte Backend-Suite**

Run: `cd backend && uv run pytest -v`
Expected: PASS (alle Tests).

- [ ] **Step 3: Gesamte Frontend-Suite + Typecheck**

Run: `cd frontend && npm test -- --run && npx tsc --noEmit`
Expected: PASS (alle Tests, keine Typfehler).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(strava): auto-backfill beim ersten connect dokumentieren"
```

---

## Self-Review-Ergebnis (vom Autor)

- **Spec-Abdeckung:** Datenmodell+Migration (T1), gemeinsamer Helper (T2), `backfill_current_year` mit Summary-Liste/Jahr/Idempotenz/Progress/Error (T3), Callback-Trigger nur bei frischem Connect (T4), `/status`-Block (T5), Frontend-Typ (T6), Polling+Fortschritt+Toast+Invalidierung (T7), README + Verifikation (T8). Alle Spec-Abschnitte abgedeckt.
- **Edge-Cases:** Disconnect-während-Import (Existenz-Check in T3-Loop), `total=0`→`done` (kein Toast, da T7 `total>0` prüft), Token-Refresh (`valid_access_token` in T3), Error-Pfad (T3-Test). Server-Neustart bewusst ohne Recovery (Spec-Nicht-Ziel).
- **Typkonsistenz:** `import_activity(session, conn, data)->bool`, `fetch_athlete_activities(token, after)->list`, `backfill_current_year(user_id)`, Status-`backfill`-Keys `{state,total,done}` durchgängig in Backend, Tests und Frontend-Typ identisch.
- **Bekannte Test-Abhängigkeit:** `backfill_current_year` öffnet eine eigene Session über `db.engine`; in Tests via `bind_engine`-Fixture auf die Fixture-Engine gepatcht (T3 Step 2).
