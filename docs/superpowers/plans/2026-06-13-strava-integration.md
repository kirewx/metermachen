# Strava-Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strava-Aktivitäten automatisch per Webhook in MeterMachen importieren — Sportart wird über ein Admin-gepflegtes Mapping einer Kategorie zugeordnet, Distanz/Datum/Name werden übernommen, und importierte Einträge tragen ein dezentes „Strava"-Badge.

**Architecture:** OAuth2 pro User (`StravaConnection`-Tabelle, Token als Epoch-Int gespeichert). Ein Service-Modul kapselt OAuth, Token-Refresh, Activity-Fetch und Sportart→Kategorie-Mapping als kleine, einzeln testbare Funktionen. Ein Router stellt Connect/Callback/Status/Disconnect sowie den Webhook (GET-Validierung + POST-Event) bereit; die Event-Logik (`handle_webhook_event`) ist von der Route entkoppelt und direkt unit-testbar. Das Feature ist config-gated: ohne Strava-Env-Variablen ist es still deaktiviert. Frontend: Connect/Trennen im Profil, Sportart-Mapping im Admin, Badge in „Meine Aktivitäten".

**Tech Stack:** FastAPI + SQLModel + SQLite (kein Alembic → `migrate()` in `db.py`), `httpx` für HTTP, `itsdangerous` für signierten OAuth-`state`. Frontend React 19 + TS + react-query, Vitest. Pytest im Backend.

**Arbeitsverzeichnisse:** Backend-Kommandos aus `backend/`, Frontend-Kommandos aus `frontend/`.

---

## File Structure

**Backend (neu):**
- `backend/app/services/__init__.py` — leeres Package-Init.
- `backend/app/services/strava.py` — OAuth, Token-Refresh, Activity-Fetch, Mapping, `handle_webhook_event`.
- `backend/app/routers/strava_router.py` — Connect/Callback/Status/Disconnect + Webhook.
- `backend/tests/test_strava.py` — Tests für Service + Router.
- `backend/scripts/strava_subscribe.py` — einmaliges Setup-Skript für die Webhook-Subscription.

**Backend (geändert):**
- `backend/pyproject.toml` — `httpx` als Runtime-Dep.
- `backend/app/config.py` — Strava-Env-Variablen + `strava_enabled()`.
- `backend/app/models.py` — `StravaConnection` + `Category.strava_sport_types`.
- `backend/app/db.py` — Migration für `category.strava_sport_types`.
- `backend/app/schemas.py` — `CategoryOut`, `strava_sport_types` in Create/Patch, `source` in `ActivityOut`.
- `backend/app/routers/categories.py` — gibt `CategoryOut` zurück, schreibt JSON-Sportarten.
- `backend/app/routers/activities.py` — `_to_out` füllt `source`.
- `backend/app/main.py` — `strava_router` registrieren.

**Frontend (geändert):**
- `frontend/src/api/client.ts` — `source` an `Activity`, `strava_sport_types` an `Category`, Strava-API-Methoden, `StravaStatus`-Typ.
- `frontend/src/pages/MeineAktivitaeten.tsx` — „Strava"-Badge.
- `frontend/src/components/ui/ProfilModal.tsx` — Strava-Abschnitt.
- `frontend/src/pages/Admin.tsx` — Sportart-Mehrfachauswahl pro Kategorie.

**Frontend (neu):**
- `frontend/src/pages/MeineAktivitaeten.test.tsx` — Badge-Test.
- `frontend/src/components/ui/ProfilModal.test.tsx` — Strava-Abschnitt-Test.

---

## Task 1: Backend-Dependency + Strava-Config

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_strava.py` (neu)

- [ ] **Step 1: `httpx` als Runtime-Dependency ergänzen**

In `backend/pyproject.toml` die `dependencies`-Liste um `httpx>=0.28` erweitern (es ist bereits als Dev-Dep vorhanden — jetzt auch zur Laufzeit nötig):

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlmodel>=0.0.22",
    "argon2-cffi>=23.1",
    "itsdangerous>=2.2",
    "python-multipart>=0.0.20",
    "httpx>=0.28",
]
```

Dann Sync ausführen (aus `backend/`): `uv sync` (oder `uv pip install httpx`). Falls `uv` nicht verfügbar ist, ist `httpx` durch die Dev-Group ohnehin schon installiert — dieser Schritt stellt nur die Deklaration sicher.

- [ ] **Step 2: Failing test für `strava_enabled()` schreiben**

`backend/tests/test_strava.py` neu anlegen mit:

```python
from app import config


def test_strava_enabled_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "")
    assert config.strava_enabled() is False


def test_strava_enabled_true_when_fully_configured(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "123")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "verifytok")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://meter.example.com")
    assert config.strava_enabled() is True
```

- [ ] **Step 3: Test ausführen, Fehlschlag bestätigen**

Run (aus `backend/`): `pytest tests/test_strava.py -v`
Expected: FAIL — `AttributeError`/`STRAVA_CLIENT_ID` bzw. `strava_enabled` existiert nicht.

- [ ] **Step 4: Config implementieren**

In `backend/app/config.py` nach der Zeile `SKIP_SEED = ...` ergänzen:

```python
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
STRAVA_WEBHOOK_VERIFY_TOKEN = os.environ.get("STRAVA_WEBHOOK_VERIFY_TOKEN", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")


def strava_enabled() -> bool:
    return bool(
        STRAVA_CLIENT_ID
        and STRAVA_CLIENT_SECRET
        and STRAVA_WEBHOOK_VERIFY_TOKEN
        and PUBLIC_BASE_URL
    )
```

- [ ] **Step 5: Test ausführen, Erfolg bestätigen**

Run: `pytest tests/test_strava.py -v`
Expected: PASS (2 Tests).

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/config.py backend/tests/test_strava.py
git commit -m "feat(strava): config-flags und httpx-runtime-dependency"
```

(Falls `uv.lock` nicht verändert wurde, einfach weglassen.)

---

## Task 2: Datenmodell — StravaConnection + Category-Spalte + Migration

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_strava.py`, `backend/tests/test_migration.py`

- [ ] **Step 1: Failing tests schreiben**

In `backend/tests/test_strava.py` am Ende ergänzen:

```python
from sqlmodel import select

from app.models import Category, StravaConnection


def test_strava_connection_roundtrip(session):
    conn = StravaConnection(
        user_id=1, athlete_id=999, access_token="a", refresh_token="r", expires_at=123456
    )
    session.add(conn)
    session.commit()
    got = session.exec(select(StravaConnection).where(StravaConnection.athlete_id == 999)).first()
    assert got is not None
    assert got.expires_at == 123456


def test_category_has_strava_sport_types_default(session):
    cat = Category(name="Laufen", factor=4.0, color="#e74c3c", icon="laufen")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    assert cat.strava_sport_types == "[]"
```

In `backend/tests/test_migration.py` einen Test ergänzen, der prüft, dass `migrate()` die Spalte zu einer Alt-DB ohne `strava_sport_types` hinzufügt. Lies zuerst die vorhandene Datei, um den dortigen Stil/Imports zu übernehmen, und ergänze analog:

```python
def test_migrate_adds_strava_sport_types_column(tmp_path):
    from sqlalchemy import text
    from sqlmodel import create_engine

    from app import db

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE category (id INTEGER PRIMARY KEY, name VARCHAR, factor FLOAT, "
            "color VARCHAR, icon VARCHAR, default_km FLOAT, is_active BOOLEAN)"
        ))
        conn.execute(text("INSERT INTO category (id, name, factor, color, icon, default_km, is_active) "
                          "VALUES (1, 'Alt', 2.0, '#000000', 'medaille', 10.0, 1)"))

    db.migrate(engine)

    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("category")'))]
        assert "strava_sport_types" in cols
        val = conn.execute(text("SELECT strava_sport_types FROM category WHERE id = 1")).scalar()
        assert val == "[]"
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest tests/test_strava.py tests/test_migration.py -v`
Expected: FAIL — `StravaConnection` existiert nicht, `Category` hat kein `strava_sport_types`, Migration fügt die Spalte nicht hinzu.

- [ ] **Step 3: Modell erweitern**

In `backend/app/models.py` zur `Category`-Klasse das Feld ergänzen (nach `is_active`):

```python
    strava_sport_types: str = "[]"  # JSON-Liste gemappter Strava-Sportarten, z.B. ["Run","TrailRun"]
```

Und nach der `Category`-Klasse (vor `Season`) die neue Tabelle ergänzen:

```python
class StravaConnection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    athlete_id: int = Field(index=True)
    access_token: str
    refresh_token: str
    expires_at: int  # Unix-Epoch-Sekunden (Strava-Format), keine Zeitzonen-Fallen
    created_at: datetime = Field(default_factory=utcnow)
```

- [ ] **Step 4: Migration für die neue Spalte ergänzen**

In `backend/app/db.py` in der Funktion `migrate()` innerhalb des `with target.begin() as conn:`-Blocks (z.B. direkt nach dem `default_km`-Block) ergänzen:

```python
        if "strava_sport_types" not in _columns(conn, "category"):
            conn.execute(text(
                "ALTER TABLE category ADD COLUMN strava_sport_types TEXT NOT NULL DEFAULT '[]'"
            ))
```

(Die neue Tabelle `strava_connection` wird von `SQLModel.metadata.create_all(engine)` in `init_db()` automatisch angelegt — kein manueller Migrationsschritt nötig.)

- [ ] **Step 5: Tests ausführen, Erfolg bestätigen**

Run: `pytest tests/test_strava.py tests/test_migration.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_strava.py backend/tests/test_migration.py
git commit -m "feat(strava): stravaconnection-tabelle und category-sportart-mapping"
```

---

## Task 3: Kategorie-API exponiert Sportart-Mapping (CategoryOut)

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/categories.py`
- Test: `backend/tests/test_categories.py`

- [ ] **Step 1: Failing tests schreiben**

Lies zuerst `backend/tests/test_categories.py` für den Stil. Ergänze diese Tests (nutzen `login`, `make_user`, `make_category` aus `tests.conftest`):

```python
def test_create_category_with_strava_sport_types(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post("/api/categories", json={
        "name": "Laufen", "factor": 4.0, "color": "#e74c3c", "icon": "laufen",
        "default_km": 5.0, "strava_sport_types": ["Run", "TrailRun"],
    })
    assert r.status_code == 201, r.text
    assert r.json()["strava_sport_types"] == ["Run", "TrailRun"]


def test_list_categories_returns_sport_types_as_list(client, session):
    make_user(session, is_admin=True)
    make_category(session, name="Rad", factor=1.0, strava_sport_types='["Ride"]')
    login(client)
    r = client.get("/api/categories")
    assert r.status_code == 200
    rad = next(c for c in r.json() if c["name"] == "Rad")
    assert rad["strava_sport_types"] == ["Ride"]


def test_patch_category_updates_sport_types(client, session):
    make_user(session, is_admin=True)
    cat = make_category(session)
    login(client)
    r = client.patch(f"/api/categories/{cat.id}", json={"strava_sport_types": ["Run"]})
    assert r.status_code == 200
    assert r.json()["strava_sport_types"] == ["Run"]
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest tests/test_categories.py -v`
Expected: FAIL — Feld unbekannt / Response enthält keine `strava_sport_types`-Liste.

- [ ] **Step 3: Schemas ergänzen**

In `backend/app/schemas.py`:

(a) Import oben ergänzen (es ist bereits `from .models import Season` vorhanden — erweitern):

```python
from .models import Category, Season
```

(b) `CategoryCreate` um das Feld erweitern (nach `default_km`):

```python
    strava_sport_types: list[str] = []
```

(c) `CategoryPatch` um das Feld erweitern (nach `is_active`):

```python
    strava_sport_types: list[str] | None = None
```

(d) Eine `CategoryOut`-Klasse hinzufügen (analog zu `SeasonOut`), direkt nach `CategoryPatch`:

```python
class CategoryOut(BaseModel):
    id: int
    name: str
    factor: float
    color: str
    icon: str
    default_km: float
    is_active: bool
    strava_sport_types: list[str]

    @classmethod
    def from_category(cls, cat: Category) -> "CategoryOut":
        return cls(
            id=cat.id,
            name=cat.name,
            factor=cat.factor,
            color=cat.color,
            icon=cat.icon,
            default_km=cat.default_km,
            is_active=cat.is_active,
            strava_sport_types=json.loads(cat.strava_sport_types or "[]"),
        )
```

(`json` ist in `schemas.py` bereits importiert.)

- [ ] **Step 4: Categories-Router auf CategoryOut umstellen**

`backend/app/routers/categories.py` vollständig ersetzen durch:

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import Category
from ..schemas import CategoryCreate, CategoryOut, CategoryPatch

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get(
    "", response_model=list[CategoryOut], dependencies=[Depends(get_current_user)]
)
def list_categories(session: Session = Depends(get_session)):
    cats = session.exec(select(Category).order_by(Category.id)).all()
    return [CategoryOut.from_category(c) for c in cats]


@router.post(
    "", response_model=CategoryOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_category(data: CategoryCreate, session: Session = Depends(get_session)):
    values = data.model_dump()
    values["strava_sport_types"] = json.dumps(values.get("strava_sport_types") or [])
    cat = Category(**values)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return CategoryOut.from_category(cat)


@router.patch(
    "/{category_id}", response_model=CategoryOut, dependencies=[Depends(require_admin)]
)
def patch_category(
    category_id: int, data: CategoryPatch, session: Session = Depends(get_session)
):
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "strava_sport_types" in changes:
        changes["strava_sport_types"] = json.dumps(changes["strava_sport_types"])
    for key, value in changes.items():
        setattr(cat, key, value)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return CategoryOut.from_category(cat)
```

- [ ] **Step 5: Tests ausführen, Erfolg bestätigen**

Run: `pytest tests/test_categories.py -v`
Expected: PASS (inkl. der bestehenden Kategorie-Tests — diese dürfen NICHT verändert werden; die Response-Felder bleiben kompatibel, nur `strava_sport_types` kommt hinzu).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/categories.py backend/tests/test_categories.py
git commit -m "feat(strava): kategorie-api exponiert sportart-mapping als liste"
```

---

## Task 4: ActivityOut exponiert `source`

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routers/activities.py`
- Test: `backend/tests/test_activities.py`

- [ ] **Step 1: Failing test schreiben**

In `backend/tests/test_activities.py` ergänzen:

```python
def test_manual_activity_has_source_manual(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    r = create_activity(client, cat.id)
    assert r.status_code == 201
    assert r.json()["source"] == "manual"
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `pytest tests/test_activities.py::test_manual_activity_has_source_manual -v`
Expected: FAIL — Response hat kein Feld `source`.

- [ ] **Step 3: Schema + Mapper ergänzen**

In `backend/app/schemas.py` zur Klasse `ActivityOut` das Feld ergänzen (nach `edited`):

```python
    source: str
```

In `backend/app/routers/activities.py` in `_to_out` das Feld füllen (im `ActivityOut(...)`-Aufruf, nach `edited=...`):

```python
        source=activity.source,
```

- [ ] **Step 4: Test ausführen, Erfolg bestätigen**

Run: `pytest tests/test_activities.py -v`
Expected: PASS (alle Aktivitäten-Tests, inkl. neuem).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/activities.py backend/tests/test_activities.py
git commit -m "feat(strava): activityout exponiert source-feld"
```

---

## Task 5: Strava-Service-Modul

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/strava.py`
- Test: `backend/tests/test_strava.py`

- [ ] **Step 1: Failing tests für die Service-Logik schreiben**

In `backend/tests/test_strava.py` ergänzen (Imports oben in der Datei bei Bedarf ergänzen):

```python
from app.models import Activity
from app.services import strava


def _setup_conn(session, athlete_id=999, expires_at=9999999999):
    user = make_user(session)
    conn = StravaConnection(
        user_id=user.id, athlete_id=athlete_id,
        access_token="tok", refresh_token="ref", expires_at=expires_at,
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return user, conn


def _payload(athlete_id=999, object_id=555, aspect="create"):
    return {"object_type": "activity", "aspect_type": aspect,
            "owner_id": athlete_id, "object_id": object_id}


def test_category_for_sport_matches_active_only(session):
    make_category(session, name="Laufen", strava_sport_types='["Run","TrailRun"]')
    make_category(session, name="Inaktiv", strava_sport_types='["Ride"]', is_active=False)
    assert strava.category_for_sport(session, "Run").name == "Laufen"
    assert strava.category_for_sport(session, "TrailRun").name == "Laufen"
    assert strava.category_for_sport(session, "Ride") is None  # nur inaktiv gemappt
    assert strava.category_for_sport(session, "Swim") is None


def test_valid_access_token_refreshes_when_expired(session, monkeypatch):
    _user, conn = _setup_conn(session, expires_at=0)
    monkeypatch.setattr(strava, "refresh_tokens", lambda rt: {
        "access_token": "neu", "refresh_token": "neu-ref", "expires_at": 8888888888,
    })
    token = strava.valid_access_token(session, conn)
    assert token == "neu"
    assert conn.refresh_token == "neu-ref"
    assert conn.expires_at == 8888888888


def test_valid_access_token_keeps_valid_token(session, monkeypatch):
    _user, conn = _setup_conn(session, expires_at=9999999999)
    monkeypatch.setattr(strava, "refresh_tokens", lambda rt: (_ for _ in ()).throw(AssertionError("darf nicht refreshen")))
    assert strava.valid_access_token(session, conn) == "tok"


def test_handle_webhook_event_imports_activity(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Morgenlauf",
    })
    strava.handle_webhook_event(session, _payload())
    acts = session.exec(select(Activity)).all()
    assert len(acts) == 1
    assert acts[0].source == "strava"
    assert acts[0].external_id == "555"
    assert acts[0].distance_km == 5.0
    assert acts[0].duration_min == 30
    assert acts[0].note == "Morgenlauf"
    assert acts[0].date.isoformat() == "2026-03-01"


def test_handle_webhook_event_dedup(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Morgenlauf",
    })
    strava.handle_webhook_event(session, _payload())
    strava.handle_webhook_event(session, _payload())
    assert len(session.exec(select(Activity)).all()) == 1


def test_handle_webhook_event_skips_unmapped_sport(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Swim", "distance": 2000.0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Schwimmen",
    })
    strava.handle_webhook_event(session, _payload())
    assert session.exec(select(Activity)).all() == []


def test_handle_webhook_event_skips_zero_distance(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Kraft", strava_sport_types='["WeightTraining"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "WeightTraining", "distance": 0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Gym",
    })
    strava.handle_webhook_event(session, _payload())
    assert session.exec(select(Activity)).all() == []


def test_handle_webhook_event_unknown_owner(session, monkeypatch):
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    called = {"fetch": False}
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: called.__setitem__("fetch", True))
    strava.handle_webhook_event(session, _payload(athlete_id=12345))
    assert called["fetch"] is False
    assert session.exec(select(Activity)).all() == []


def test_handle_webhook_event_ignores_non_create(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {"sport_type": "Run"})
    strava.handle_webhook_event(session, _payload(aspect="update"))
    assert session.exec(select(Activity)).all() == []
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest tests/test_strava.py -v`
Expected: FAIL — `app.services.strava` existiert nicht.

- [ ] **Step 3: Service-Modul implementieren**

`backend/app/services/__init__.py` neu anlegen (leer):

```python
```

`backend/app/services/strava.py` neu anlegen mit:

```python
import json
import time
from datetime import date as date_type
from datetime import datetime
from urllib.parse import urlencode

import httpx
from sqlmodel import Session, select

from .. import config
from ..models import Activity, Category, StravaConnection

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"
SCOPE = "activity:read_all"
_TIMEOUT = 10


def authorize_url(state: str) -> str:
    params = {
        "client_id": config.STRAVA_CLIENT_ID,
        "redirect_uri": f"{config.PUBLIC_BASE_URL}/api/strava/callback",
        "response_type": "code",
        "scope": SCOPE,
        "approval_prompt": "auto",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    r = httpx.post(TOKEN_URL, data={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def refresh_tokens(refresh_token: str) -> dict:
    r = httpx.post(TOKEN_URL, data={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_activity(access_token: str, activity_id: int) -> dict:
    r = httpx.get(
        f"{API_BASE}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def apply_tokens(conn: StravaConnection, data: dict) -> None:
    conn.access_token = data["access_token"]
    conn.refresh_token = data["refresh_token"]
    conn.expires_at = int(data["expires_at"])


def valid_access_token(session: Session, conn: StravaConnection) -> str:
    if conn.expires_at > int(time.time()) + 60:
        return conn.access_token
    data = refresh_tokens(conn.refresh_token)
    apply_tokens(conn, data)
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn.access_token


def category_for_sport(session: Session, sport_type: str | None) -> Category | None:
    if not sport_type:
        return None
    cats = session.exec(select(Category).where(Category.is_active)).all()
    for cat in cats:
        if sport_type in json.loads(cat.strava_sport_types or "[]"):
            return cat
    return None


def _parse_date(value: str | None) -> date_type:
    if not value:
        return date_type.today()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


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
    existing = session.exec(
        select(Activity).where(
            Activity.user_id == conn.user_id,
            Activity.external_id == str(activity_id),
            Activity.source == "strava",
        )
    ).first()
    if existing is not None:
        return
    token = valid_access_token(session, conn)
    data = fetch_activity(token, activity_id)
    cat = category_for_sport(session, data.get("sport_type") or data.get("type"))
    if cat is None:
        return
    distance_km = round((data.get("distance") or 0) / 1000, 2)
    if distance_km <= 0:
        return
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
```

- [ ] **Step 4: Tests ausführen, Erfolg bestätigen**

Run: `pytest tests/test_strava.py -v`
Expected: PASS (alle Service-Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/strava.py backend/tests/test_strava.py
git commit -m "feat(strava): service-modul fuer oauth, token-refresh und webhook-import"
```

---

## Task 6: Strava-Router + Registrierung

**Files:**
- Create: `backend/app/routers/strava_router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_strava.py`

- [ ] **Step 1: Failing tests für den Router schreiben**

In `backend/tests/test_strava.py` ergänzen:

```python
def _enable_strava(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "sec")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "verifytok")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://meter.example.com")


def test_status_disabled_when_unconfigured(client, session, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "")
    make_user(session)
    login(client)
    r = client.get("/api/strava/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "connected": False}


def test_status_connected(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=42,
                                 access_token="a", refresh_token="r", expires_at=999))
    session.commit()
    login(client)
    r = client.get("/api/strava/status")
    assert r.json() == {"enabled": True, "connected": True, "athlete_id": 42}


def test_webhook_verify_echoes_challenge(client, monkeypatch):
    _enable_strava(monkeypatch)
    r = client.get("/api/strava/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "verifytok", "hub.challenge": "abc123",
    })
    assert r.status_code == 200
    assert r.json() == {"hub.challenge": "abc123"}


def test_webhook_verify_rejects_wrong_token(client, monkeypatch):
    _enable_strava(monkeypatch)
    r = client.get("/api/strava/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "falsch", "hub.challenge": "abc123",
    })
    assert r.status_code == 403


def test_webhook_post_schedules_processing(client, monkeypatch):
    from app.routers import strava_router
    seen = {}
    monkeypatch.setattr(strava_router, "process_event", lambda payload: seen.update(payload))
    r = client.post("/api/strava/webhook", json={"object_type": "activity", "aspect_type": "create"})
    assert r.status_code == 200
    assert seen.get("object_type") == "activity"


def test_connect_redirects_to_strava(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    make_user(session)
    login(client)
    r = client.get("/api/strava/connect", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("https://www.strava.com/oauth/authorize")


def test_callback_stores_connection(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    from app.routers import strava_router
    user = make_user(session)
    login(client)
    state = strava_router._state_serializer.dumps(user.id)
    monkeypatch.setattr(strava_router.strava, "exchange_code", lambda code: {
        "access_token": "AT", "refresh_token": "RT", "expires_at": 8888888888,
        "athlete": {"id": 77},
    })
    r = client.get("/api/strava/callback", params={"code": "xyz", "state": state},
                   follow_redirects=False)
    assert r.status_code in (302, 307)
    conn = session.exec(select(StravaConnection).where(StravaConnection.user_id == user.id)).first()
    assert conn is not None
    assert conn.athlete_id == 77
    assert conn.access_token == "AT"


def test_disconnect_removes_connection(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=42,
                                 access_token="a", refresh_token="r", expires_at=999))
    session.commit()
    login(client)
    assert client.delete("/api/strava/disconnect").status_code == 204
    assert session.exec(select(StravaConnection)).all() == []
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `pytest tests/test_strava.py -v`
Expected: FAIL — Endpunkte/`strava_router` existieren nicht (404).

- [ ] **Step 3: Router implementieren**

`backend/app/routers/strava_router.py` neu anlegen mit:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlmodel import Session, select

from .. import config
from ..db import engine
from ..deps import get_current_user, get_session
from ..models import StravaConnection, User
from ..services import strava

router = APIRouter(prefix="/api/strava", tags=["strava"])
_state_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="strava-oauth")


def _require_enabled() -> None:
    if not config.strava_enabled():
        raise HTTPException(status_code=404, detail="Strava ist nicht konfiguriert")


@router.get("/status")
def status(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if not config.strava_enabled():
        return {"enabled": False, "connected": False}
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    return {
        "enabled": True,
        "connected": conn is not None,
        "athlete_id": conn.athlete_id if conn else None,
    }


@router.get("/connect")
def connect(user: User = Depends(get_current_user)):
    _require_enabled()
    state = _state_serializer.dumps(user.id)
    return RedirectResponse(strava.authorize_url(state))


@router.get("/callback")
def callback(
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
    if conn is None:
        conn = StravaConnection(
            user_id=user.id, athlete_id=0, access_token="", refresh_token="", expires_at=0
        )
    conn.athlete_id = data["athlete"]["id"]
    strava.apply_tokens(conn, data)
    session.add(conn)
    session.commit()
    return RedirectResponse("/?strava=connected")


@router.delete("/disconnect", status_code=204)
def disconnect(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.user_id == user.id)
    ).first()
    if conn is not None:
        session.delete(conn)
        session.commit()


@router.get("/webhook")
def webhook_verify(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == config.STRAVA_WEBHOOK_VERIFY_TOKEN
    ):
        return JSONResponse({"hub.challenge": params.get("hub.challenge")})
    raise HTTPException(status_code=403, detail="Verify-Token falsch")


def process_event(payload: dict) -> None:
    with Session(engine) as session:
        strava.handle_webhook_event(session, payload)


@router.post("/webhook")
async def webhook_event(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    background_tasks.add_task(process_event, payload)
    return {"ok": True}
```

- [ ] **Step 4: Router in `main.py` registrieren**

In `backend/app/main.py`:

(a) Import-Zeile erweitern:

```python
from .routers import activities, auth_router, categories, comparison, seasons, strava_router, users
```

(b) Nach `app.include_router(seasons.router)` ergänzen:

```python
app.include_router(strava_router.router)
```

- [ ] **Step 5: Tests ausführen, Erfolg bestätigen**

Run: `pytest tests/test_strava.py -v`
Expected: PASS (alle Router-Tests).

- [ ] **Step 6: Gesamte Backend-Suite laufen lassen**

Run: `pytest -q`
Expected: PASS — keine Regression.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/strava_router.py backend/app/main.py backend/tests/test_strava.py
git commit -m "feat(strava): router fuer connect/callback/status/disconnect und webhook"
```

---

## Task 7: Frontend-API-Client erweitern

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Typen + Endpunkte ergänzen**

In `frontend/src/api/client.ts`:

(a) Im `Category`-Typ ein Feld ergänzen (nach `is_active: boolean`):

```ts
  strava_sport_types: string[]
```

(b) Im `Activity`-Typ ein Feld ergänzen (nach `edited: boolean`):

```ts
  source: string
```

(c) Nach dem `Comparison`-Typ einen neuen Typ ergänzen:

```ts
export type StravaStatus = {
  enabled: boolean
  connected: boolean
  athlete_id?: number | null
}
```

(d) In `createCategory` den Body-Typ erweitern, damit `strava_sport_types` mitgesendet werden darf. Aktuelle Zeile:

```ts
  createCategory: (b: Omit<Category, 'id' | 'is_active'>) =>
    request<Category>('/api/categories', post(b)),
```

bleibt typkompatibel, da `Omit<Category, 'id' | 'is_active'>` das neue Pflichtfeld `strava_sport_types` enthält. Der Aufrufer in `Admin.tsx` (Task 10) liefert es mit.

(e) Im `api`-Objekt nach `comparison: ...` ergänzen:

```ts
  stravaStatus: () => request<StravaStatus>('/api/strava/status'),
  disconnectStrava: () => request<void>('/api/strava/disconnect', { method: 'DELETE' }),
```

(Der „Connect"-Schritt ist eine Vollseiten-Navigation, kein fetch — das wird in Task 9 per `window.location.href = '/api/strava/connect'` gelöst, damit der Session-Cookie mitgeht und der Server zu Strava weiterleitet.)

- [ ] **Step 2: Typecheck**

Run (aus `frontend/`): `npx tsc -b --noEmit`
Expected: Es kann Fehler in `Admin.tsx` geben, weil `createCategory` jetzt `strava_sport_types` erwartet — das wird in Task 10 behoben. Wenn nur dieser Fehler auftritt, ist Schritt korrekt; sonst Fehler beheben. (Hinweis: Dieser Task wird zusammen mit Task 10 grün; falls die Reihenfolge stört, Task 7 + 10 in einem Commit zusammenfassen.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(strava): api-client um source, sportart-mapping und strava-status erweitert"
```

---

## Task 8: „Strava"-Badge in „Meine Aktivitäten"

**Files:**
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx`
- Test: `frontend/src/pages/MeineAktivitaeten.test.tsx` (neu)

- [ ] **Step 1: Failing test schreiben**

`frontend/src/pages/MeineAktivitaeten.test.tsx` neu anlegen:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MeineAktivitaeten from './MeineAktivitaeten'

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#fff', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
    ]),
    activities: vi.fn().mockResolvedValue([
      { id: 1, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, note: null, scaled_km: 20, edited: false, source: 'strava' },
      { id: 2, category_id: 1, date: '2026-03-02', distance_km: 3, duration_min: null, note: null, scaled_km: 12, edited: false, source: 'manual' },
    ]),
  },
}))

vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MeineAktivitaeten />
    </QueryClientProvider>,
  )
}

describe('MeineAktivitaeten', () => {
  it('zeigt genau ein Strava-Badge (nur für die Strava-Aktivität)', async () => {
    renderPage()
    await screen.findByText(/Laufen/)
    const badges = screen.getAllByText('Strava')
    expect(badges).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run (aus `frontend/`): `npm test -- src/pages/MeineAktivitaeten.test.tsx`
Expected: FAIL — kein „Strava"-Text vorhanden.

- [ ] **Step 3: Badge ergänzen**

In `frontend/src/pages/MeineAktivitaeten.tsx` im `<p>` mit dem Titel (das ist die Zeile mit `{a.distance_km} km {cat?.name}`), nach dem `{a.edited && ...}`-Ausdruck, ergänzen:

```tsx
                  {a.source === 'strava' && (
                    <span className="ml-2 rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
                      Strava
                    </span>
                  )}
```

- [ ] **Step 4: Test ausführen, Erfolg bestätigen**

Run: `npm test -- src/pages/MeineAktivitaeten.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/MeineAktivitaeten.tsx frontend/src/pages/MeineAktivitaeten.test.tsx
git commit -m "feat(strava): dezentes strava-badge in meine-aktivitaeten"
```

---

## Task 9: Strava-Abschnitt im ProfilModal

**Files:**
- Modify: `frontend/src/components/ui/ProfilModal.tsx`
- Test: `frontend/src/components/ui/ProfilModal.test.tsx` (neu)

- [ ] **Step 1: Failing tests schreiben**

`frontend/src/components/ui/ProfilModal.test.tsx` neu anlegen:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import ProfilModal from './ProfilModal'

const me: Me = { id: 1, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

const stravaStatus = vi.fn()
vi.mock('../../api/client', () => ({
  api: { patchMe: vi.fn(), stravaStatus: () => stravaStatus(), disconnectStrava: vi.fn() },
}))
vi.mock('./Toast', () => ({ useToast: () => vi.fn() }))

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ProfilModal me={me} open onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('ProfilModal Strava-Abschnitt', () => {
  it('zeigt Verbinden-Button, wenn nicht verbunden', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: false })
    renderModal()
    expect(await screen.findByRole('button', { name: /Mit Strava verbinden/ })).toBeInTheDocument()
  })

  it('zeigt Trennen-Button, wenn verbunden', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: true, athlete_id: 42 })
    renderModal()
    expect(await screen.findByRole('button', { name: /Strava trennen/ })).toBeInTheDocument()
  })

  it('zeigt nichts, wenn Feature deaktiviert', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    renderModal()
    await screen.findByLabelText('Anzeigename')
    expect(screen.queryByRole('button', { name: /Strava/ })).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `npm test -- src/components/ui/ProfilModal.test.tsx`
Expected: FAIL — kein Strava-Button.

- [ ] **Step 3: Strava-Abschnitt implementieren**

In `frontend/src/components/ui/ProfilModal.tsx`:

(a) Imports oben anpassen — `useQuery` ergänzen und `api` bleibt:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
```

(b) Innerhalb der Komponente nach der `save`-Mutation ergänzen:

```tsx
  const { data: strava } = useQuery({ queryKey: ['strava-status'], queryFn: api.stravaStatus })
  const trennen = useMutation({
    mutationFn: api.disconnectStrava,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strava-status'] })
      toast('Strava getrennt', 'ok')
    },
    onError: (e) => toast(e.message),
  })
```

(c) Im JSX innerhalb des `<div className="space-y-4">`, direkt vor dem Speichern-`<Button>`, einen Abschnitt ergänzen:

```tsx
        {strava?.enabled && (
          <div className="rounded-xl border border-line p-3">
            <div className="mb-2 text-xs font-semibold text-ink-mute">Strava</div>
            {strava.connected ? (
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => trennen.mutate()}
                disabled={trennen.isPending}
              >
                Strava trennen
              </Button>
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
          </div>
        )}
```

- [ ] **Step 4: Tests ausführen, Erfolg bestätigen**

Run: `npm test -- src/components/ui/ProfilModal.test.tsx`
Expected: PASS (3 Tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/ProfilModal.tsx frontend/src/components/ui/ProfilModal.test.tsx
git commit -m "feat(strava): verbinden/trennen im profil-modal"
```

---

## Task 10: Sportart-Mapping im Admin

**Files:**
- Modify: `frontend/src/pages/Admin.tsx`

- [ ] **Step 1: Sportart-Konstante + Multiselect-Steuerung ergänzen**

In `frontend/src/pages/Admin.tsx`:

(a) Oberhalb der `Kategorien`-Funktion (z.B. nach der `H`-Definition) eine kuratierte Sportart-Liste ergänzen:

```tsx
const STRAVA_SPORT_TYPES = [
  'Run', 'TrailRun', 'Walk', 'Hike', 'Ride', 'MountainBikeRide', 'GravelRide',
  'EBikeRide', 'VirtualRide', 'VirtualRun', 'Swim', 'Rowing', 'Kayaking',
  'NordicSki', 'AlpineSki', 'BackcountrySki', 'Snowboard', 'IceSkate',
  'InlineSkate', 'Elliptical', 'StairStepper', 'Workout', 'WeightTraining',
]
```

(b) In der `Kategorien`-Komponente die `patch`-Mutation um `strava_sport_types` erweitern (Signatur):

```tsx
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: number; factor?: number; default_km?: number; is_active?: boolean; strava_sport_types?: string[] }) =>
      api.patchCategory(id, b),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
```

(c) Den `create`-Aufruf um das Pflichtfeld ergänzen (im `api.createCategory({...})`-Objekt nach `default_km: parseFloat(neu.default_km)`):

```tsx
        strava_sport_types: [],
```

(d) In der Kategorie-Zeile (innerhalb der `categories.map((c) => ...)`-Schleife, im äußeren `<div key={c.id}>`, nach dem „Aktivieren/Deaktivieren"-`<Button>`) eine Sportart-Auswahl ergänzen. Da die Zeile mit `flex-wrap` umbricht, kommt die Auswahl als eigener, voll breiter Block:

```tsx
            <div className="w-full">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-mute">
                Strava-Sportarten
              </div>
              <div className="flex flex-wrap gap-1">
                {STRAVA_SPORT_TYPES.map((sport) => {
                  const aktiv = c.strava_sport_types.includes(sport)
                  return (
                    <button
                      key={sport}
                      type="button"
                      onClick={() => {
                        const next = aktiv
                          ? c.strava_sport_types.filter((s) => s !== sport)
                          : [...c.strava_sport_types, sport]
                        patch.mutate({ id: c.id, strava_sport_types: next })
                      }}
                      className={`rounded-full border px-2 py-0.5 text-[11px] transition ${
                        aktiv
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-line text-ink-mute hover:border-accent'
                      }`}
                    >
                      {sport}
                    </button>
                  )
                })}
              </div>
            </div>
```

- [ ] **Step 2: Typecheck + Lint + Tests**

Run (aus `frontend/`):
- `npx tsc -b --noEmit` — Expected: keine Fehler (das `createCategory`-Problem aus Task 7 ist jetzt behoben).
- `npm run lint` — Expected: sauber.
- `npm test` — Expected: alle Tests grün.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Admin.tsx
git commit -m "feat(strava): admin-mapping der strava-sportarten pro kategorie"
```

---

## Task 11: Webhook-Subscription-Skript + Doku

**Files:**
- Create: `backend/scripts/strava_subscribe.py`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Subscription-Skript anlegen**

`backend/scripts/strava_subscribe.py` neu anlegen:

```python
"""Einmaliges Setup/Verwalten der Strava-Webhook-Subscription.

Aufruf (aus backend/, mit gesetzten Strava-Env-Variablen):
    python -m scripts.strava_subscribe create
    python -m scripts.strava_subscribe view
    python -m scripts.strava_subscribe delete <subscription_id>

Voraussetzung: Der Callback (PUBLIC_BASE_URL + /api/strava/webhook) muss
oeffentlich per HTTPS erreichbar sein, BEVOR 'create' aufgerufen wird —
Strava validiert ihn sofort per GET.
"""
import sys

import httpx

from app import config

PUSH_URL = "https://www.strava.com/api/v3/push_subscriptions"


def create() -> None:
    callback = f"{config.PUBLIC_BASE_URL}/api/strava/webhook"
    r = httpx.post(PUSH_URL, data={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "callback_url": callback,
        "verify_token": config.STRAVA_WEBHOOK_VERIFY_TOKEN,
    }, timeout=20)
    print(r.status_code, r.text)


def view() -> None:
    r = httpx.get(PUSH_URL, params={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
    }, timeout=20)
    print(r.status_code, r.text)


def delete(subscription_id: str) -> None:
    r = httpx.delete(f"{PUSH_URL}/{subscription_id}", params={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
    }, timeout=20)
    print(r.status_code, r.text)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "view"
    if cmd == "create":
        create()
    elif cmd == "view":
        view()
    elif cmd == "delete" and len(sys.argv) > 2:
        delete(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
```

- [ ] **Step 2: `.env.example` ergänzen**

Am Ende von `.env.example` ergänzen:

```
# Optional: Strava-Integration. Alle vier Werte setzen, um sie zu aktivieren.
# API-App anlegen unter https://www.strava.com/settings/api
#STRAVA_CLIENT_ID=
#STRAVA_CLIENT_SECRET=
# Frei wählbarer String, der die Webhook-Validierung absichert:
#STRAVA_WEBHOOK_VERIFY_TOKEN=
# Öffentlich per HTTPS erreichbare Basis-URL der App (für OAuth-Redirect + Webhook):
#PUBLIC_BASE_URL=https://meter.example.com
```

- [ ] **Step 3: README ergänzen**

In `README.md` einen kurzen Abschnitt „Strava-Integration (optional)" ergänzen. Lies zuerst die README, um Ton/Struktur zu treffen, und beschreibe:
- vier Env-Variablen setzen (Verweis auf `.env.example`),
- der Endpoint `POST /api/strava/webhook` muss öffentlich per HTTPS erreichbar sein (lokal via Tunnel wie ngrok),
- einmalig `python -m scripts.strava_subscribe create` aus `backend/` ausführen,
- funktioniert mit kostenlosen Strava-Accounts; Scope `activity:read_all` importiert auch private Aktivitäten,
- nur Neuanlagen werden importiert; lokale Änderungen in MeterMachen bleiben erhalten.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/strava_subscribe.py .env.example README.md
git commit -m "docs(strava): subscription-skript und setup-dokumentation"
```

---

## Task 12: Gesamtverifikation

**Files:** keine — nur Verifikation.

- [ ] **Step 1: Backend-Tests**

Run (aus `backend/`): `pytest -q`
Expected: PASS — alle Tests grün, keine Regression.

- [ ] **Step 2: Frontend-Tests, Lint, Build**

Run (aus `frontend/`):
- `npm test` — Expected: alle grün.
- `npm run lint` — Expected: sauber.
- `npm run build` — Expected: erfolgreich.

- [ ] **Step 3: Abschluss-Commit (nur falls kleine Korrekturen nötig waren)**

```bash
git add -A
git commit -m "chore(strava): lint/typecheck-fixes"
```

---

## Self-Review-Notiz (Plan vs. Spec)

- **Webhook Auto-Sync:** `POST /api/strava/webhook` + `handle_webhook_event`, nur `create` (Task 5, 6) ✓
- **Admin-Mapping pro Kategorie:** `Category.strava_sport_types` + CategoryOut + Admin-UI (Task 2, 3, 10) ✓
- **Nur Neuanlage, lokale Änderungen gewinnen:** kein Update/Delete-Handling; Dedup über `external_id` (Task 5) ✓
- **Strava-Badge, manuelle ohne Badge:** `source` in ActivityOut/Client + Badge nur bei `source==='strava'` (Task 4, 7, 8) ✓
- **Kostenlose Accounts / `activity:read_all`:** Scope-Konstante im Service + README (Task 5, 11) ✓
- **Config-gated:** `strava_enabled()`; Status liefert `enabled:false`, UI blendet aus (Task 1, 6, 9) ✓
- **OAuth pro User + Token-Refresh:** `StravaConnection` + `valid_access_token` + signierter `state` (Task 2, 5, 6) ✓
- **Deployment-Voraussetzung + Subscription:** Skript + Doku (Task 11) ✓
- **Typkonsistenz:** Service-Funktionsnamen (`category_for_sport`, `valid_access_token`, `apply_tokens`, `fetch_activity`, `refresh_tokens`, `exchange_code`, `handle_webhook_event`, `process_event`) sind über Router und Tests hinweg identisch verwendet. `strava_sport_types` ist überall `list[str]` an der API-Grenze und JSON-`str` in der DB.
- **Reihenfolge-Hinweis:** Task 7 (Client-Typen) macht `createCategory` strikter; der dadurch entstehende TS-Fehler wird in Task 10 behoben. Bei Inline-Ausführung ist die Reihenfolge 7→10 unkritisch; der finale Build (Task 12) ist die maßgebliche Grüne.
