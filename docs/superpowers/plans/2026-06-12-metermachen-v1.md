# MeterMachen V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Self-hosted Multiuser-Webapp zum Kilometer-Tracking mit skalierten Kategorien, Jahres-Distanzvergleich (Wanderkarte, Race-Bahnen, Jahresverlauf) für einen privaten Freundeskreis.

**Architecture:** Ein Docker-Container: FastAPI serviert die API unter `/api/*` und den gebauten React-SPA-Build unter `/`. SQLite auf einem Volume. Auth über signierte HttpOnly-Session-Cookies. Skalierte km werden nie gespeichert, immer live `distance_km × factor` berechnet.

**Tech Stack:** FastAPI, SQLModel, SQLite, argon2-cffi, itsdangerous (Backend) · React 18, Vite, TypeScript, TanStack Query, React Router, Tailwind CSS 4, Recharts (Frontend) · pytest + httpx, Vitest + React Testing Library (Tests) · uv, Docker Multi-Stage.

**Spec:** `docs/superpowers/specs/2026-06-12-metermachen-design.md`

---

## Dateistruktur (Zielbild)

```
backend/
├─ pyproject.toml            # uv-Projekt, Backend-Dependencies
├─ app/
│  ├─ __init__.py
│  ├─ config.py              # Env-Variablen (SECRET_KEY, ADMIN_*, DATA_DIR)
│  ├─ db.py                  # Engine, init_db()
│  ├─ models.py              # SQLModel-Tabellen: User, Category, Activity, Season
│  ├─ schemas.py             # Pydantic Request/Response-Modelle
│  ├─ auth.py                # Passwort-Hashing, Session-Token
│  ├─ deps.py                # get_session, get_current_user, require_admin
│  ├─ seed.py                # Erststart: Admin, Default-Kategorien, Season
│  ├─ main.py                # App-Factory, Lifespan, Router, SPA-Mount
│  └─ routers/
│     ├─ __init__.py
│     ├─ auth_router.py      # login/logout/me
│     ├─ activities.py       # CRUD eigene Aktivitäten
│     ├─ categories.py       # lesen (alle) / pflegen (Admin)
│     ├─ seasons.py          # lesen (alle) / pflegen + Bild-Upload (Admin)
│     ├─ users.py            # Admin: anlegen; alle: PATCH /me
│     └─ comparison.py       # Aggregat-Endpunkt für alle 3 Ansichten
└─ tests/
   ├─ conftest.py            # In-Memory-SQLite, TestClient, Login-Helfer
   ├─ test_auth.py
   ├─ test_seed.py
   ├─ test_categories.py
   ├─ test_seasons.py
   ├─ test_users.py
   ├─ test_activities.py
   └─ test_comparison.py

frontend/
├─ package.json, vite.config.ts, tsconfig.json, index.html
└─ src/
   ├─ main.tsx               # Router, QueryClient
   ├─ api/client.ts          # typisierte Fetch-Wrapper
   ├─ pages/                 # Login, MeineAktivitaeten, Vergleich, Admin
   └─ components/
      ├─ comparison/         # WanderKarte, RaceBahnen, JahresVerlauf, pathMath.ts
      ├─ activities/         # ActivityForm, ActivityList
      └─ ui/                 # Tabs, Toast

Dockerfile                   # Stage 1: Node-Build, Stage 2: Python + uv
docker-compose.yml
```

**Reihenfolge:** Tasks 1–9 Backend (jede API testgetrieben), Tasks 10–16 Frontend, Task 17 Docker. Nach jedem Task ist der Stand lauffähig und committet.

---

### Task 1: Repo aufräumen + Backend-Gerüst

Das Repo enthält uv-init-Stubs im Root (`main.py`, `pyproject.toml`, `uv.lock`, `.python-version`). Backend und Frontend bekommen eigene Unterprojekte — die Stubs fliegen raus.

**Files:**
- Delete: `main.py`, `pyproject.toml`, `uv.lock`, `.python-version` (Root)
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`
- Test: `backend/tests/test_health.py`, `backend/tests/__init__.py` (leer)

- [ ] **Step 1: Root-Stubs entfernen und committen**

```bash
git rm main.py pyproject.toml uv.lock .python-version
git commit -m "chore: remove uv-init stubs, backend/frontend get own projects"
```

- [ ] **Step 2: Backend-Projekt anlegen**

`backend/pyproject.toml`:

```toml
[project]
name = "metermachen-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlmodel>=0.0.22",
    "argon2-cffi>=23.1",
    "itsdangerous>=2.2",
    "python-multipart>=0.0.20",
]

[dependency-groups]
dev = ["pytest>=8", "httpx>=0.28"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`backend/app/__init__.py` und `backend/tests/__init__.py`: leer anlegen.

Run: `cd backend; uv sync`
Expected: venv wird erstellt, alle Pakete installiert.

- [ ] **Step 3: Failing Test — Health-Endpunkt**

`backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

Run: `cd backend; uv run pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 4: Minimale App**

`backend/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="MeterMachen")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Test grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 1 passed

```bash
git add backend/
git commit -m "feat: backend scaffold with health endpoint"
```

---

### Task 2: Konfiguration, Datenbank, Modelle

**Files:**
- Create: `backend/app/config.py`, `backend/app/db.py`, `backend/app/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Failing Test — Tabellen + Roundtrip**

`backend/tests/test_models.py`:

```python
from datetime import date

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Activity, Category, Season, User


def make_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_roundtrip_all_tables():
    with make_session() as s:
        user = User(username="erik", password_hash="x", display_name="Erik")
        cat = Category(name="Joggen", factor=4.0, color="#e74c3c", icon_emoji="🏃")
        s.add(user)
        s.add(cat)
        s.commit()
        s.add(
            Activity(
                user_id=user.id,
                category_id=cat.id,
                date=date(2026, 3, 1),
                distance_km=5.0,
            )
        )
        s.add(Season(year=2026, goal_km=1000.0))
        s.commit()

        act = s.exec(select(Activity)).one()
        assert act.distance_km == 5.0
        assert act.source == "manual"
        assert act.updated_at is None
        season = s.exec(select(Season)).one()
        assert season.milestones_json == "[]"
        assert user.avatar_emoji == "🏃"
        assert user.is_admin is False
        assert cat.is_active is True
```

Run: `cd backend; uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 2: Config, DB, Modelle implementieren**

`backend/app/config.py`:

```python
import os
from pathlib import Path

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")  # leer → DATA_DIR/meter.db
SKIP_SEED = os.environ.get("METER_SKIP_SEED") == "1"


def database_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATA_DIR / 'meter.db'}"
```

`backend/app/models.py`:

```python
from datetime import date as date_type
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    display_name: str
    avatar_emoji: str = "🏃"
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    factor: float
    color: str
    icon_emoji: str
    is_active: bool = True


class Activity(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    category_id: int = Field(foreign_key="category.id")
    date: date_type = Field(index=True)
    distance_km: float
    duration_min: int | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None
    source: str = "manual"
    external_id: str | None = None


class Season(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    year: int = Field(unique=True)
    goal_km: float
    milestones_json: str = "[]"  # JSON-Liste [{"km":..,"label":..,"emoji":..}]
    map_image: str | None = None
```

`backend/app/db.py`:

```python
from sqlmodel import SQLModel, create_engine

from . import config
from . import models  # noqa: F401  — Tabellen registrieren

engine = create_engine(config.database_url(), connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
```

- [ ] **Step 3: Test grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 2 passed

```bash
git add backend/app backend/tests
git commit -m "feat: data model (User, Category, Activity, Season) + db setup"
```

---

### Task 3: Auth — Hashing, Session-Token, Login/Logout/Me

**Files:**
- Create: `backend/app/auth.py`, `backend/app/deps.py`, `backend/app/routers/__init__.py`, `backend/app/routers/auth_router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/conftest.py`, `backend/tests/test_auth.py`

- [ ] **Step 1: Test-Infrastruktur (conftest)**

`backend/tests/conftest.py`:

```python
import os

os.environ["METER_SKIP_SEED"] = "1"  # Lifespan-Seeding in Tests aus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import auth
from app.deps import get_session
from app.main import app
from app.models import Category, User


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_user(session, username="erik", password="pw123", is_admin=False) -> User:
    user = User(
        username=username,
        password_hash=auth.hash_password(password),
        display_name=username.capitalize(),
        is_admin=is_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(client, username="erik", password="pw123"):
    r = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert r.status_code == 200, r.text
    return r


def make_category(session, name="Joggen", factor=4.0, **kw) -> Category:
    cat = Category(
        name=name, factor=factor, color="#e74c3c", icon_emoji="🏃", **kw
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
```

- [ ] **Step 2: Failing Tests — Login-Flows**

`backend/tests/test_auth.py`:

```python
from tests.conftest import login, make_user


def test_login_ok_sets_cookie_and_me_works(client, session):
    make_user(session)
    r = login(client)
    assert "session" in r.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "erik"
    assert me.json()["is_admin"] is False


def test_login_wrong_password(client, session):
    make_user(session)
    r = client.post("/api/auth/login", json={"username": "erik", "password": "falsch"})
    assert r.status_code == 401


def test_login_unknown_user(client, session):
    r = client.post("/api/auth/login", json={"username": "nope", "password": "x"})
    assert r.status_code == 401


def test_me_requires_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_session(client, session):
    make_user(session)
    login(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
```

Run: `cd backend; uv run pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.deps'`

- [ ] **Step 3: Auth implementieren**

`backend/app/auth.py`:

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 Tage

_ph = PasswordHasher()
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="session")


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_session_token(user_id: int) -> str:
    return _serializer.dumps(user_id)


def read_session_token(token: str) -> int | None:
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
```

`backend/app/deps.py`:

```python
from fastapi import Cookie, Depends, HTTPException
from sqlmodel import Session

from . import auth
from .db import engine
from .models import User


def get_session():
    with Session(engine) as session:
        yield session


def get_current_user(
    session: Session = Depends(get_session),
    session_cookie: str | None = Cookie(default=None, alias=auth.SESSION_COOKIE),
) -> User:
    if not session_cookie:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    user_id = auth.read_session_token(session_cookie)
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Nicht eingeloggt")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Nur für Admins")
    return user
```

`backend/app/routers/__init__.py`: leer anlegen.

`backend/app/routers/auth_router.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import auth
from ..deps import get_current_user, get_session
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class MeOut(BaseModel):
    id: int
    username: str
    display_name: str
    avatar_emoji: str
    is_admin: bool


@router.post("/login", response_model=MeOut)
def login(data: LoginIn, response: Response, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == data.username)).first()
    if user is None or not auth.verify_password(user.password_hash, data.password):
        raise HTTPException(status_code=401, detail="Benutzername oder Passwort falsch")
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user.id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return user
```

`backend/app/main.py` (komplett ersetzen):

```python
from fastapi import FastAPI

from .routers import auth_router

app = FastAPI(title="MeterMachen")
app.include_router(auth_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 7 passed

```bash
git add backend/
git commit -m "feat: session-cookie auth with login/logout/me"
```

---

### Task 4: Erststart-Seeding (Admin, Default-Kategorien, Season)

**Files:**
- Create: `backend/app/seed.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_seed.py`

- [ ] **Step 1: Failing Tests**

`backend/tests/test_seed.py`:

```python
from sqlmodel import select

from app.models import Category, Season, User
from app.seed import seed_all


def test_seed_creates_admin_categories_season(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    admin = session.exec(select(User)).one()
    assert admin.username == "chef"
    assert admin.is_admin is True
    cats = session.exec(select(Category)).all()
    assert {c.name for c in cats} == {
        "Joggen", "Laufen", "Spazieren", "Wandern", "Schwimmen", "Radfahren", "Tanzen"
    }
    assert {c.name: c.factor for c in cats}["Joggen"] == 4.0
    assert {c.name: c.factor for c in cats}["Radfahren"] == 1.0
    season = session.exec(select(Season)).one()
    assert season.year == 2026
    assert season.goal_km == 1000.0


def test_seed_is_idempotent(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    assert len(session.exec(select(User)).all()) == 1
    assert len(session.exec(select(Category)).all()) == 7
    assert len(session.exec(select(Season)).all()) == 1
```

Run: `cd backend; uv run pytest tests/test_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.seed'`

- [ ] **Step 2: Seeding implementieren**

`backend/app/seed.py`:

```python
from sqlmodel import Session, select

from . import auth
from .models import Category, Season, User

DEFAULT_CATEGORIES = [
    ("Joggen", 4.0, "#e74c3c", "🏃"),
    ("Laufen", 4.0, "#c0392b", "👟"),
    ("Spazieren", 3.0, "#f1c40f", "🚶"),
    ("Wandern", 3.0, "#27ae60", "🥾"),
    ("Schwimmen", 10.0, "#9b59b6", "🏊"),
    ("Radfahren", 1.0, "#3498db", "🚴"),
    ("Tanzen", 3.0, "#e67e22", "💃"),
]


def seed_all(session: Session, admin_user: str, admin_password: str, year: int) -> None:
    if session.exec(select(User)).first() is None:
        session.add(
            User(
                username=admin_user,
                password_hash=auth.hash_password(admin_password),
                display_name=admin_user.capitalize(),
                is_admin=True,
            )
        )
    if session.exec(select(Category)).first() is None:
        for name, factor, color, emoji in DEFAULT_CATEGORIES:
            session.add(Category(name=name, factor=factor, color=color, icon_emoji=emoji))
    if session.exec(select(Season).where(Season.year == year)).first() is None:
        session.add(Season(year=year, goal_km=1000.0))
    session.commit()
```

`backend/app/main.py` (komplett ersetzen — Lifespan kommt dazu):

```python
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI
from sqlmodel import Session

from . import config
from .db import engine, init_db
from .routers import auth_router
from .seed import seed_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not config.SKIP_SEED:
        init_db()
        with Session(engine) as session:
            seed_all(
                session,
                admin_user=config.ADMIN_USER,
                admin_password=config.ADMIN_PASSWORD,
                year=date.today().year,
            )
    yield


app = FastAPI(title="MeterMachen", lifespan=lifespan)
app.include_router(auth_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 9 passed

```bash
git add backend/
git commit -m "feat: first-start seeding (admin, default categories, season)"
```

---

### Task 5: Schemas + Stammdaten-Router (Categories, Seasons)

**Files:**
- Create: `backend/app/schemas.py`, `backend/app/routers/categories.py`, `backend/app/routers/seasons.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_categories.py`, `backend/tests/test_seasons.py`

- [ ] **Step 1: Failing Tests — Categories**

`backend/tests/test_categories.py`:

```python
from tests.conftest import login, make_category, make_user


def test_list_categories_requires_login(client, session):
    make_category(session)
    assert client.get("/api/categories").status_code == 401


def test_list_categories(client, session):
    make_user(session)
    make_category(session)
    make_category(session, name="Radfahren", factor=1.0, is_active=False)
    login(client)
    r = client.get("/api/categories")
    assert r.status_code == 200
    assert [c["name"] for c in r.json()] == ["Joggen", "Radfahren"]
    assert r.json()[1]["is_active"] is False


def test_create_category_admin_only(client, session):
    make_user(session)
    login(client)
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon_emoji": "🚣"},
    )
    assert r.status_code == 403


def test_create_and_patch_category_as_admin(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon_emoji": "🚣"},
    )
    assert r.status_code == 201
    cat_id = r.json()["id"]
    r = client.patch(f"/api/categories/{cat_id}", json={"factor": 3.0, "is_active": False})
    assert r.status_code == 200
    assert r.json()["factor"] == 3.0
    assert r.json()["is_active"] is False
```

- [ ] **Step 2: Failing Tests — Seasons**

`backend/tests/test_seasons.py`:

```python
from app.models import Season
from tests.conftest import login, make_user


def make_season(session, year=2026, goal_km=1000.0):
    season = Season(year=year, goal_km=goal_km)
    session.add(season)
    session.commit()
    session.refresh(season)
    return season


def test_list_seasons(client, session):
    make_user(session)
    make_season(session)
    login(client)
    r = client.get("/api/seasons")
    assert r.status_code == 200
    assert r.json()[0]["year"] == 2026
    assert r.json()[0]["milestones"] == []


def test_patch_season_admin_only(client, session):
    make_user(session)
    season = make_season(session)
    login(client)
    assert client.patch(f"/api/seasons/{season.id}", json={"goal_km": 2000}).status_code == 403


def test_patch_season_goal_and_milestones(client, session):
    make_user(session, username="chef", is_admin=True)
    season = make_season(session)
    login(client, username="chef")
    r = client.patch(
        f"/api/seasons/{season.id}",
        json={
            "goal_km": 1500,
            "milestones": [{"km": 500, "label": "Brücke", "emoji": "🌉"}],
        },
    )
    assert r.status_code == 200
    assert r.json()["goal_km"] == 1500
    assert r.json()["milestones"] == [{"km": 500, "label": "Brücke", "emoji": "🌉"}]


def test_create_season_as_admin(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = client.post("/api/seasons", json={"year": 2027, "goal_km": 1200})
    assert r.status_code == 201
    assert r.json()["year"] == 2027
```

Run: `cd backend; uv run pytest tests/test_categories.py tests/test_seasons.py -v`
Expected: FAIL — 404-Fehler (Routen existieren nicht)

- [ ] **Step 3: Schemas implementieren**

`backend/app/schemas.py`:

```python
import json
from datetime import date as date_type

from pydantic import BaseModel, Field, field_validator

from .models import Season


class Milestone(BaseModel):
    km: float
    label: str
    emoji: str = "🚩"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    factor: float = Field(gt=0)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    icon_emoji: str = "🏅"


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    factor: float | None = Field(default=None, gt=0)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon_emoji: str | None = None
    is_active: bool | None = None


class SeasonCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    goal_km: float = Field(gt=0)
    milestones: list[Milestone] = []


class SeasonPatch(BaseModel):
    goal_km: float | None = Field(default=None, gt=0)
    milestones: list[Milestone] | None = None


class SeasonOut(BaseModel):
    id: int
    year: int
    goal_km: float
    milestones: list[Milestone]
    map_image: str | None

    @classmethod
    def from_season(cls, season: Season) -> "SeasonOut":
        return cls(
            id=season.id,
            year=season.year,
            goal_km=season.goal_km,
            milestones=json.loads(season.milestones_json),
            map_image=season.map_image,
        )


class ActivityCreate(BaseModel):
    category_id: int
    date: date_type
    distance_km: float = Field(gt=0)
    duration_min: int | None = Field(default=None, gt=0)
    note: str | None = None

    @field_validator("date")
    @classmethod
    def not_in_future(cls, v: date_type) -> date_type:
        if v > date_type.today():
            raise ValueError("Datum darf nicht in der Zukunft liegen")
        return v


class ActivityPatch(BaseModel):
    category_id: int | None = None
    date: date_type | None = None
    distance_km: float | None = Field(default=None, gt=0)
    duration_min: int | None = Field(default=None, gt=0)
    note: str | None = None

    @field_validator("date")
    @classmethod
    def not_in_future(cls, v: date_type | None) -> date_type | None:
        if v is not None and v > date_type.today():
            raise ValueError("Datum darf nicht in der Zukunft liegen")
        return v


class ActivityOut(BaseModel):
    id: int
    category_id: int
    date: date_type
    distance_km: float
    duration_min: int | None
    note: str | None
    scaled_km: float
    edited: bool
```

- [ ] **Step 4: Router implementieren**

`backend/app/routers/categories.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import Category
from ..schemas import CategoryCreate, CategoryPatch

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[Category], dependencies=[Depends(get_current_user)])
def list_categories(session: Session = Depends(get_session)):
    return session.exec(select(Category).order_by(Category.id)).all()


@router.post("", response_model=Category, status_code=201, dependencies=[Depends(require_admin)])
def create_category(data: CategoryCreate, session: Session = Depends(get_session)):
    cat = Category(**data.model_dump())
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


@router.patch("/{category_id}", response_model=Category, dependencies=[Depends(require_admin)])
def patch_category(
    category_id: int, data: CategoryPatch, session: Session = Depends(get_session)
):
    cat = session.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(cat, key, value)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
```

`backend/app/routers/seasons.py`:

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_admin
from ..models import Season
from ..schemas import SeasonCreate, SeasonOut, SeasonPatch

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


@router.get("", response_model=list[SeasonOut], dependencies=[Depends(get_current_user)])
def list_seasons(session: Session = Depends(get_session)):
    seasons = session.exec(select(Season).order_by(Season.year)).all()
    return [SeasonOut.from_season(s) for s in seasons]


@router.post("", response_model=SeasonOut, status_code=201, dependencies=[Depends(require_admin)])
def create_season(data: SeasonCreate, session: Session = Depends(get_session)):
    if session.exec(select(Season).where(Season.year == data.year)).first():
        raise HTTPException(status_code=409, detail="Jahr existiert bereits")
    season = Season(
        year=data.year,
        goal_km=data.goal_km,
        milestones_json=json.dumps([m.model_dump() for m in data.milestones]),
    )
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)


@router.patch("/{season_id}", response_model=SeasonOut, dependencies=[Depends(require_admin)])
def patch_season(season_id: int, data: SeasonPatch, session: Session = Depends(get_session)):
    season = session.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404)
    if data.goal_km is not None:
        season.goal_km = data.goal_km
    if data.milestones is not None:
        season.milestones_json = json.dumps([m.model_dump() for m in data.milestones])
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)
```

In `backend/app/main.py` die Router registrieren — Import-Zeile und `include_router`-Aufrufe ergänzen:

```python
from .routers import auth_router, categories, seasons
# ...nach app = FastAPI(...):
app.include_router(auth_router.router)
app.include_router(categories.router)
app.include_router(seasons.router)
```

- [ ] **Step 5: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 17 passed

```bash
git add backend/
git commit -m "feat: categories + seasons CRUD (admin-managed)"
```

---

### Task 6: Users-Router (Admin legt an, jeder pflegt sein Profil)

**Files:**
- Create: `backend/app/routers/users.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: Failing Tests**

`backend/tests/test_users.py`:

```python
from tests.conftest import login, make_user


def test_create_user_admin_only(client, session):
    make_user(session)
    login(client)
    r = client.post(
        "/api/users",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa"},
    )
    assert r.status_code == 403


def test_admin_creates_user_who_can_login(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = client.post(
        "/api/users",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa"},
    )
    assert r.status_code == 201
    assert r.json()["is_admin"] is False
    client.post("/api/auth/logout")
    login(client, username="lisa", password="pw456")


def test_duplicate_username_rejected(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    body = {"username": "lisa", "password": "pw456", "display_name": "Lisa"}
    assert client.post("/api/users", json=body).status_code == 201
    assert client.post("/api/users", json=body).status_code == 409


def test_patch_own_profile(client, session):
    make_user(session)
    login(client)
    r = client.patch(
        "/api/users/me",
        json={"display_name": "Erik W.", "avatar_emoji": "🚴", "password": "neu789"},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Erik W."
    assert r.json()["avatar_emoji"] == "🚴"
    client.post("/api/auth/logout")
    login(client, password="neu789")
```

Run: `cd backend; uv run pytest tests/test_users.py -v`
Expected: FAIL — 404 (Routen existieren nicht)

- [ ] **Step 2: Router implementieren**

`backend/app/routers/users.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import auth
from ..deps import get_current_user, get_session, require_admin
from ..models import User
from .auth_router import MeOut

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=4)
    display_name: str = Field(min_length=1)
    avatar_emoji: str = "🏃"
    is_admin: bool = False


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1)
    avatar_emoji: str | None = None
    password: str | None = Field(default=None, min_length=4)


@router.post("", response_model=MeOut, status_code=201, dependencies=[Depends(require_admin)])
def create_user(data: UserCreate, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(status_code=409, detail="Benutzername vergeben")
    user = User(
        username=data.username,
        password_hash=auth.hash_password(data.password),
        display_name=data.display_name,
        avatar_emoji=data.avatar_emoji,
        is_admin=data.is_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/me", response_model=MeOut)
def patch_me(
    data: ProfilePatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.avatar_emoji is not None:
        user.avatar_emoji = data.avatar_emoji
    if data.password is not None:
        user.password_hash = auth.hash_password(data.password)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
```

In `backend/app/main.py` registrieren (`from .routers import ... users` + `app.include_router(users.router)`).

- [ ] **Step 3: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 21 passed

```bash
git add backend/
git commit -m "feat: user management (admin create, self-service profile)"
```

---

### Task 7: Activities — CRUD mit Validierung und Besitz-Schutz

**Files:**
- Create: `backend/app/routers/activities.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_activities.py`

- [ ] **Step 1: Failing Tests**

`backend/tests/test_activities.py`:

```python
from datetime import date, timedelta

from tests.conftest import login, make_category, make_user


def create_activity(client, cat_id, **overrides):
    body = {"category_id": cat_id, "date": "2026-03-01", "distance_km": 5.0}
    body.update(overrides)
    return client.post("/api/activities", json=body)


def test_create_and_list_with_scaled_km(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    r = create_activity(client, cat.id, note="Feierabendrunde")
    assert r.status_code == 201
    assert r.json()["scaled_km"] == 20.0
    assert r.json()["edited"] is False
    r = client.get("/api/activities", params={"year": 2026})
    assert len(r.json()) == 1
    assert client.get("/api/activities", params={"year": 2025}).json() == []


def test_validation_rules(client, session):
    make_user(session)
    cat = make_category(session)
    inactive = make_category(session, name="Alt", factor=2.0, is_active=False)
    login(client)
    assert create_activity(client, cat.id, distance_km=-1).status_code == 422
    future = (date.today() + timedelta(days=1)).isoformat()
    assert create_activity(client, cat.id, date=future).status_code == 422
    assert create_activity(client, inactive.id).status_code == 422
    assert create_activity(client, 999).status_code == 422


def test_patch_sets_edited_flag_and_rescales(client, session):
    make_user(session)
    cat = make_category(session, factor=4.0)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    r = client.patch(f"/api/activities/{act_id}", json={"distance_km": 10.0})
    assert r.status_code == 200
    assert r.json()["scaled_km"] == 40.0
    assert r.json()["edited"] is True


def test_cannot_touch_foreign_activities(client, session):
    make_user(session)
    other = make_user(session, username="lisa")
    cat = make_category(session)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    client.post("/api/auth/logout")
    login(client, username="lisa")
    assert client.patch(f"/api/activities/{act_id}", json={"distance_km": 1}).status_code == 404
    assert client.delete(f"/api/activities/{act_id}").status_code == 404
    assert client.get("/api/activities", params={"year": 2026}).json() == []


def test_delete_own_activity(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    act_id = create_activity(client, cat.id).json()["id"]
    assert client.delete(f"/api/activities/{act_id}").status_code == 204
    assert client.get("/api/activities", params={"year": 2026}).json() == []
```

Run: `cd backend; uv run pytest tests/test_activities.py -v`
Expected: FAIL — 404 (Routen existieren nicht)

- [ ] **Step 2: Router implementieren**

Die Erstellung läuft durch `_validate_category` + `_to_out` — dieselben Funktionen nutzt später der Strava-Importer (Spec §9).

`backend/app/routers/activities.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, User
from ..schemas import ActivityCreate, ActivityOut, ActivityPatch
from ..models import utcnow

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _validate_category(session: Session, category_id: int) -> Category:
    cat = session.get(Category, category_id)
    if cat is None or not cat.is_active:
        raise HTTPException(status_code=422, detail="Kategorie unbekannt oder inaktiv")
    return cat


def _to_out(activity: Activity, factor: float) -> ActivityOut:
    return ActivityOut(
        id=activity.id,
        category_id=activity.category_id,
        date=activity.date,
        distance_km=activity.distance_km,
        duration_min=activity.duration_min,
        note=activity.note,
        scaled_km=round(activity.distance_km * factor, 2),
        edited=activity.updated_at is not None,
    )


def _own_activity(session: Session, user: User, activity_id: int) -> Activity:
    act = session.get(Activity, activity_id)
    if act is None or act.user_id != user.id:
        raise HTTPException(status_code=404)
    return act


@router.get("", response_model=list[ActivityOut])
def list_my_activities(
    year: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    acts = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .where(Activity.user_id == user.id)
        .order_by(Activity.date.desc(), Activity.id.desc())
    ).all()
    return [_to_out(a, c.factor) for a, c in acts if a.date.year == year]


@router.post("", response_model=ActivityOut, status_code=201)
def create_activity(
    data: ActivityCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    cat = _validate_category(session, data.category_id)
    act = Activity(user_id=user.id, **data.model_dump())
    session.add(act)
    session.commit()
    session.refresh(act)
    return _to_out(act, cat.factor)


@router.patch("/{activity_id}", response_model=ActivityOut)
def patch_activity(
    activity_id: int,
    data: ActivityPatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    act = _own_activity(session, user, activity_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _validate_category(session, changes["category_id"])
    for key, value in changes.items():
        setattr(act, key, value)
    act.updated_at = utcnow()
    session.add(act)
    session.commit()
    session.refresh(act)
    cat = session.get(Category, act.category_id)
    return _to_out(act, cat.factor)


@router.delete("/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    act = _own_activity(session, user, activity_id)
    session.delete(act)
    session.commit()
```

In `backend/app/main.py` registrieren (`activities` importieren + `app.include_router(activities.router)`).

- [ ] **Step 3: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 26 passed

```bash
git add backend/
git commit -m "feat: activity CRUD with validation, ownership, edited flag"
```

---

### Task 8: Comparison-Endpunkt (Aggregat für alle drei Ansichten)

**Files:**
- Create: `backend/app/routers/comparison.py`
- Modify: `backend/app/main.py`, `backend/app/schemas.py`
- Test: `backend/tests/test_comparison.py`

- [ ] **Step 1: Failing Tests**

`backend/tests/test_comparison.py`:

```python
from datetime import date

from app.models import Activity, Season
from tests.conftest import login, make_category, make_user


def add_activity(session, user, cat, d, km):
    session.add(Activity(user_id=user.id, category_id=cat.id, date=d, distance_km=km))
    session.commit()


def setup_data(session):
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    jog = make_category(session, factor=4.0)
    rad = make_category(session, name="Radfahren", factor=1.0)
    session.add(Season(year=2026, goal_km=1000.0))
    session.commit()
    add_activity(session, erik, jog, date(2026, 1, 10), 5)    # 20 skaliert
    add_activity(session, erik, rad, date(2026, 2, 1), 30)    # 30 skaliert
    add_activity(session, lisa, jog, date(2026, 1, 15), 10)   # 40 skaliert
    add_activity(session, erik, jog, date(2025, 12, 31), 99)  # falsches Jahr
    return erik, lisa


def test_ranking_and_totals(client, session):
    setup_data(session)
    login(client)
    r = client.get("/api/comparison/2026")
    assert r.status_code == 200
    body = r.json()
    assert body["goal_km"] == 1000.0
    users = body["users"]
    assert [u["display_name"] for u in users] == ["Erik", "Lisa"]
    assert users[0]["total_scaled_km"] == 50.0
    assert users[0]["rank"] == 1
    assert users[1]["total_scaled_km"] == 40.0


def test_category_breakdown_and_segments(client, session):
    setup_data(session)
    login(client)
    erik = client.get("/api/comparison/2026").json()["users"][0]
    breakdown = {b["name"]: b["scaled_km"] for b in erik["by_category"]}
    assert breakdown == {"Joggen": 20.0, "Radfahren": 30.0}
    assert [s["scaled_km"] for s in erik["segments"]] == [20.0, 30.0]  # chronologisch
    assert erik["segments"][0]["date"] == "2026-01-10"
    assert erik["segments"][0]["color"] == "#e74c3c"


def test_cumulative_series(client, session):
    setup_data(session)
    login(client)
    erik = client.get("/api/comparison/2026").json()["users"][0]
    assert erik["cumulative"] == [
        {"date": "2026-01-10", "scaled_km": 20.0},
        {"date": "2026-02-01", "scaled_km": 50.0},
    ]


def test_empty_year_and_users_without_activities(client, session):
    setup_data(session)
    login(client)
    r = client.get("/api/comparison/2024")
    assert r.status_code == 404  # keine Season für 2024


def test_user_without_activities_is_listed(client, session):
    setup_data(session)
    make_user(session, username="tom")
    login(client)
    users = client.get("/api/comparison/2026").json()["users"]
    assert users[2]["display_name"] == "Tom"
    assert users[2]["total_scaled_km"] == 0
    assert users[2]["cumulative"] == []
```

Run: `cd backend; uv run pytest tests/test_comparison.py -v`
Expected: FAIL — 404 (Route existiert nicht)

- [ ] **Step 2: Schemas ergänzen**

Ans Ende von `backend/app/schemas.py` anhängen:

```python
class CategoryShare(BaseModel):
    category_id: int
    name: str
    color: str
    icon_emoji: str
    scaled_km: float


class Segment(BaseModel):
    date: date_type
    category_id: int
    color: str
    scaled_km: float


class CumulativePoint(BaseModel):
    date: date_type
    scaled_km: float


class ComparisonUser(BaseModel):
    user_id: int
    display_name: str
    avatar_emoji: str
    rank: int
    total_scaled_km: float
    by_category: list[CategoryShare]
    segments: list[Segment]
    cumulative: list[CumulativePoint]


class ComparisonOut(BaseModel):
    year: int
    goal_km: float
    milestones: list[Milestone]
    map_image: str | None
    users: list[ComparisonUser]
```

- [ ] **Step 3: Router implementieren**

`backend/app/routers/comparison.py`:

```python
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import Activity, Category, Season, User
from ..schemas import (
    CategoryShare,
    ComparisonOut,
    ComparisonUser,
    CumulativePoint,
    Segment,
)

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.get("/{year}", response_model=ComparisonOut, dependencies=[Depends(get_current_user)])
def comparison(year: int, session: Session = Depends(get_session)):
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Kein Jahr konfiguriert")

    users = session.exec(select(User).order_by(User.id)).all()
    rows = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .order_by(Activity.date, Activity.id)
    ).all()
    rows = [(a, c) for a, c in rows if a.date.year == year]

    by_user: dict[int, list[tuple[Activity, Category]]] = defaultdict(list)
    for a, c in rows:
        by_user[a.user_id].append((a, c))

    result_users = []
    for user in users:
        acts = by_user.get(user.id, [])
        segments, cumulative, shares = [], [], defaultdict(float)
        running = 0.0
        for a, c in acts:
            scaled = round(a.distance_km * c.factor, 2)
            running = round(running + scaled, 2)
            segments.append(
                Segment(date=a.date, category_id=c.id, color=c.color, scaled_km=scaled)
            )
            cumulative.append(CumulativePoint(date=a.date, scaled_km=running))
            shares[c.id] += scaled
        by_category = [
            CategoryShare(
                category_id=c.id,
                name=c.name,
                color=c.color,
                icon_emoji=c.icon_emoji,
                scaled_km=round(km, 2),
            )
            for c, km in (
                (session.get(Category, cid), km) for cid, km in shares.items()
            )
        ]
        result_users.append(
            ComparisonUser(
                user_id=user.id,
                display_name=user.display_name,
                avatar_emoji=user.avatar_emoji,
                rank=0,
                total_scaled_km=running,
                by_category=by_category,
                segments=segments,
                cumulative=cumulative,
            )
        )

    result_users.sort(key=lambda u: -u.total_scaled_km)
    for i, u in enumerate(result_users):
        u.rank = i + 1

    return ComparisonOut(
        year=year,
        goal_km=season.goal_km,
        milestones=json.loads(season.milestones_json),
        map_image=season.map_image,
        users=result_users,
    )
```

In `backend/app/main.py` registrieren (`comparison` importieren + `app.include_router(comparison.router)`).

- [ ] **Step 4: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 31 passed

```bash
git add backend/
git commit -m "feat: comparison endpoint with ranking, segments, cumulative series"
```

---

### Task 9: Kartenbild-Upload + SPA-Serving

**Files:**
- Modify: `backend/app/routers/seasons.py`, `backend/app/main.py`
- Test: `backend/tests/test_seasons.py` (erweitern)

- [ ] **Step 1: Failing Test — Bild-Upload**

An `backend/tests/test_seasons.py` anhängen:

```python
def test_upload_map_image(client, session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    make_user(session, username="chef", is_admin=True)
    season = make_season(session)
    login(client, username="chef")
    r = client.post(
        f"/api/seasons/{season.id}/map-image",
        files={"file": ("karte.png", b"\x89PNG fake", "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["map_image"] == "/media/maps/2026.png"
    assert (tmp_path / "maps" / "2026.png").read_bytes() == b"\x89PNG fake"


def test_upload_rejects_non_image(client, session, tmp_path, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    make_user(session, username="chef", is_admin=True)
    season = make_season(session)
    login(client, username="chef")
    r = client.post(
        f"/api/seasons/{season.id}/map-image",
        files={"file": ("doc.txt", b"hallo", "text/plain")},
    )
    assert r.status_code == 422
```

Run: `cd backend; uv run pytest tests/test_seasons.py -v`
Expected: FAIL — 404 (Route existiert nicht)

- [ ] **Step 2: Upload-Endpunkt implementieren**

An `backend/app/routers/seasons.py` anhängen (Imports oben ergänzen: `from fastapi import UploadFile`, `from .. import config`):

```python
ALLOWED_IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


@router.post("/{season_id}/map-image", response_model=SeasonOut, dependencies=[Depends(require_admin)])
def upload_map_image(
    season_id: int, file: UploadFile, session: Session = Depends(get_session)
):
    season = session.get(Season, season_id)
    if season is None:
        raise HTTPException(status_code=404)
    ext = ALLOWED_IMAGE_TYPES.get(file.content_type)
    if ext is None:
        raise HTTPException(status_code=422, detail="Nur PNG/JPEG/WebP erlaubt")
    maps_dir = config.DATA_DIR / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    target = maps_dir / f"{season.year}{ext}"
    target.write_bytes(file.file.read())
    season.map_image = f"/media/maps/{target.name}"
    session.add(season)
    session.commit()
    session.refresh(season)
    return SeasonOut.from_season(season)
```

- [ ] **Step 3: Media- und SPA-Serving in main.py**

`backend/app/main.py` — nach den `include_router`-Aufrufen anhängen:

```python
import os
from pathlib import Path

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """Liefert index.html für alle unbekannten Pfade (Client-Side-Routing)."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def mount_static(app: FastAPI) -> None:
    media_dir = config.DATA_DIR / "maps"
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media/maps", StaticFiles(directory=media_dir), name="media")
    dist = Path(os.environ.get("FRONTEND_DIST", "../frontend/dist"))
    if dist.is_dir():
        app.mount("/", SPAStaticFiles(directory=dist, html=True), name="spa")


mount_static(app)
```

- [ ] **Step 4: Tests grün, committen**

Run: `cd backend; uv run pytest -v`
Expected: 33 passed

```bash
git add backend/
git commit -m "feat: map image upload + media/SPA static serving"
```

**Backend fertig.** Manuelle Probe: `cd backend; uv run uvicorn app.main:app --reload` → `http://localhost:8000/docs` zeigt alle Endpunkte; Login mit admin/admin funktioniert.

---

### Task 10: Frontend-Gerüst (Vite, Tailwind, Router, Query, Vitest)

**Files:**
- Create: `frontend/` (Vite-Scaffold), `frontend/vite.config.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/vitest.setup.ts`

- [ ] **Step 1: Scaffold + Dependencies**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query react-router-dom recharts tailwindcss @tailwindcss/vite
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

- [ ] **Step 2: Konfiguration**

`frontend/vite.config.ts` (komplett ersetzen):

```ts
/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/media': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
  },
})
```

`frontend/vitest.setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

`frontend/src/index.css` (komplett ersetzen):

```css
@import 'tailwindcss';
```

In `frontend/package.json` unter `scripts` ergänzen: `"test": "vitest run"`.

Vite-Scaffold-Reste löschen: `frontend/src/App.css`, `frontend/src/assets/react.svg`, `frontend/public/vite.svg`.

- [ ] **Step 3: App-Einstieg mit Router und QueryClient**

`frontend/src/main.tsx` (komplett ersetzen):

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
```

`frontend/src/App.tsx` (komplett ersetzen — Platzhalter-Seiten, werden in Folge-Tasks ersetzt):

```tsx
import { Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<p className="p-8">MeterMachen 🚧</p>} />
    </Routes>
  )
}
```

- [ ] **Step 4: Smoke-Check, committen**

Run: `cd frontend; npm run build`
Expected: Build ohne Fehler, `dist/` entsteht.

```bash
git add frontend/
git commit -m "feat: frontend scaffold (vite, tailwind, router, query, vitest)"
```

---

### Task 11: API-Client, Login-Seite, Auth-Schutz, Layout

**Files:**
- Create: `frontend/src/api/client.ts`, `frontend/src/pages/Login.tsx`, `frontend/src/components/ui/Layout.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Typisierter API-Client**

`frontend/src/api/client.ts`:

```ts
export type Me = {
  id: number
  username: string
  display_name: string
  avatar_emoji: string
  is_admin: boolean
}
export type Category = {
  id: number
  name: string
  factor: number
  color: string
  icon_emoji: string
  is_active: boolean
}
export type Milestone = { km: number; label: string; emoji: string }
export type Season = {
  id: number
  year: number
  goal_km: number
  milestones: Milestone[]
  map_image: string | null
}
export type Activity = {
  id: number
  category_id: number
  date: string
  distance_km: number
  duration_min: number | null
  note: string | null
  scaled_km: number
  edited: boolean
}
export type ActivityInput = {
  category_id: number
  date: string
  distance_km: number
  duration_min?: number | null
  note?: string | null
}
export type CategoryShare = {
  category_id: number
  name: string
  color: string
  icon_emoji: string
  scaled_km: number
}
export type Segment = { date: string; category_id: number; color: string; scaled_km: number }
export type ComparisonUser = {
  user_id: number
  display_name: string
  avatar_emoji: string
  rank: number
  total_scaled_km: number
  by_category: CategoryShare[]
  segments: Segment[]
  cumulative: { date: string; scaled_km: number }[]
}
export type Comparison = {
  year: number
  goal_km: number
  milestones: Milestone[]
  map_image: string | null
  users: ComparisonUser[]
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!r.ok) {
    const detail = (await r.json().catch(() => null))?.detail
    throw new Error(typeof detail === 'string' ? detail : `Fehler ${r.status}`)
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

const post = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) })
const patch = (body: unknown) => ({ method: 'PATCH', body: JSON.stringify(body) })

export const api = {
  login: (username: string, password: string) =>
    request<Me>('/api/auth/login', post({ username, password })),
  logout: () => request<unknown>('/api/auth/logout', { method: 'POST' }),
  me: () => request<Me>('/api/auth/me'),
  categories: () => request<Category[]>('/api/categories'),
  createCategory: (b: Omit<Category, 'id' | 'is_active'>) =>
    request<Category>('/api/categories', post(b)),
  patchCategory: (id: number, b: Partial<Omit<Category, 'id'>>) =>
    request<Category>(`/api/categories/${id}`, patch(b)),
  seasons: () => request<Season[]>('/api/seasons'),
  createSeason: (b: { year: number; goal_km: number; milestones?: Milestone[] }) =>
    request<Season>('/api/seasons', post(b)),
  patchSeason: (id: number, b: { goal_km?: number; milestones?: Milestone[] }) =>
    request<Season>(`/api/seasons/${id}`, patch(b)),
  uploadMapImage: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Season>(`/api/seasons/${id}/map-image`, { method: 'POST', body: form })
  },
  activities: (year: number) => request<Activity[]>(`/api/activities?year=${year}`),
  createActivity: (b: ActivityInput) => request<Activity>('/api/activities', post(b)),
  patchActivity: (id: number, b: Partial<ActivityInput>) =>
    request<Activity>(`/api/activities/${id}`, patch(b)),
  deleteActivity: (id: number) => request<void>(`/api/activities/${id}`, { method: 'DELETE' }),
  createUser: (b: { username: string; password: string; display_name: string; avatar_emoji?: string }) =>
    request<Me>('/api/users', post(b)),
  patchMe: (b: { display_name?: string; avatar_emoji?: string; password?: string }) =>
    request<Me>('/api/users/me', patch(b)),
  comparison: (year: number) => request<Comparison>(`/api/comparison/${year}`),
}
```

- [ ] **Step 2: Login-Seite und Layout**

`frontend/src/pages/Login.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'

export default function Login() {
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const me = await api.login(username, password)
      queryClient.setQueryData(['me'], me)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login fehlgeschlagen')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-emerald-50">
      <form onSubmit={submit} className="w-80 space-y-4 rounded-2xl bg-white p-8 shadow">
        <h1 className="text-center text-2xl font-bold">MeterMachen 🏃</h1>
        <input
          className="w-full rounded border p-2"
          placeholder="Benutzername"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="w-full rounded border p-2"
          type="password"
          placeholder="Passwort"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-emerald-600 p-2 font-semibold text-white">
          Einloggen
        </button>
      </form>
    </div>
  )
}
```

`frontend/src/components/ui/Layout.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'
import { api, type Me } from '../../api/client'

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-1 ${isActive ? 'bg-emerald-600 text-white' : 'hover:bg-emerald-100'}`

export default function Layout({ me }: { me: Me }) {
  const queryClient = useQueryClient()
  async function logout() {
    await api.logout()
    queryClient.setQueryData(['me'], null)
  }
  return (
    <div className="min-h-screen bg-emerald-50">
      <nav className="flex items-center gap-2 bg-white px-4 py-2 shadow">
        <span className="mr-2 font-bold">MeterMachen</span>
        <NavLink to="/" end className={link}>Vergleich</NavLink>
        <NavLink to="/aktivitaeten" className={link}>Meine Aktivitäten</NavLink>
        {me.is_admin && <NavLink to="/admin" className={link}>Admin</NavLink>}
        <span className="ml-auto text-sm">{me.avatar_emoji} {me.display_name}</span>
        <button onClick={logout} className="text-sm text-gray-500 hover:underline">
          Logout
        </button>
      </nav>
      <main className="mx-auto max-w-5xl p-4">
        <Outlet />
      </main>
    </div>
  )
}
```

- [ ] **Step 3: App mit Auth-Weiche**

`frontend/src/App.tsx` (komplett ersetzen — die Seiten `Vergleich`, `MeineAktivitaeten`, `Admin` entstehen in Tasks 12–16; bis dahin Platzhalter-Komponenten unten in derselben Datei):

```tsx
import { useQuery } from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import Layout from './components/ui/Layout'
import Login from './pages/Login'

const Vergleich = () => <p>Vergleich 🚧</p>
const MeineAktivitaeten = () => <p>Aktivitäten 🚧</p>
const Admin = () => <p>Admin 🚧</p>

export default function App() {
  const { data: me, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.me().catch(() => null),
  })
  if (isLoading) return <p className="p-8">Lade…</p>
  if (!me) return <Login />
  return (
    <Routes>
      <Route element={<Layout me={me} />}>
        <Route path="/" element={<Vergleich />} />
        <Route path="/aktivitaeten" element={<MeineAktivitaeten />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  )
}
```

- [ ] **Step 4: Manuell prüfen, committen**

Run: Backend starten (`cd backend; uv run uvicorn app.main:app`), Frontend-Dev (`cd frontend; npm run dev`), `http://localhost:5173` öffnen.
Expected: Login-Maske; mit admin/admin einloggen → Navigation mit drei Platzhalter-Seiten, Logout funktioniert.

```bash
git add frontend/
git commit -m "feat: api client, login flow, authenticated layout"
```

---

### Task 12: Meine Aktivitäten — Formular + Liste

**Files:**
- Create: `frontend/src/components/activities/ActivityForm.tsx`, `frontend/src/components/activities/ActivityForm.test.tsx`, `frontend/src/pages/MeineAktivitaeten.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Failing Test — Formular**

`frontend/src/components/activities/ActivityForm.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Category } from '../../api/client'
import ActivityForm from './ActivityForm'

const categories: Category[] = [
  { id: 1, name: 'Joggen', factor: 4, color: '#e74c3c', icon_emoji: '🏃', is_active: true },
  { id: 2, name: 'Alt', factor: 2, color: '#000000', icon_emoji: '🦖', is_active: false },
]

describe('ActivityForm', () => {
  it('zeigt nur aktive Kategorien an', () => {
    render(<ActivityForm categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByRole('option', { name: /Joggen/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Alt/ })).not.toBeInTheDocument()
  })

  it('liefert die Eingaben beim Absenden', async () => {
    const onSubmit = vi.fn()
    render(<ActivityForm categories={categories} onSubmit={onSubmit} />)
    await userEvent.type(screen.getByLabelText('Datum'), '2026-03-01')
    await userEvent.type(screen.getByLabelText('Distanz (km)'), '5.5')
    await userEvent.type(screen.getByLabelText('Notiz'), 'Runde am Fluss')
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: '2026-03-01',
      distance_km: 5.5,
      duration_min: null,
      note: 'Runde am Fluss',
    })
  })

  it('blockiert Absenden ohne Distanz', async () => {
    const onSubmit = vi.fn()
    render(<ActivityForm categories={categories} onSubmit={onSubmit} />)
    await userEvent.type(screen.getByLabelText('Datum'), '2026-03-01')
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
```

Run: `cd frontend; npm test`
Expected: FAIL — `Cannot find module './ActivityForm'`

- [ ] **Step 2: Formular implementieren**

`frontend/src/components/activities/ActivityForm.tsx`:

```tsx
import { useState } from 'react'
import type { Activity, ActivityInput, Category } from '../../api/client'

type Props = {
  categories: Category[]
  onSubmit: (input: ActivityInput) => void
  initial?: Activity
}

export default function ActivityForm({ categories, onSubmit, initial }: Props) {
  const active = categories.filter((c) => c.is_active || c.id === initial?.category_id)
  const [categoryId, setCategoryId] = useState(initial?.category_id ?? active[0]?.id ?? 0)
  const [date, setDate] = useState(initial?.date ?? '')
  const [distance, setDistance] = useState(initial ? String(initial.distance_km) : '')
  const [duration, setDuration] = useState(initial?.duration_min ? String(initial.duration_min) : '')
  const [note, setNote] = useState(initial?.note ?? '')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const distance_km = parseFloat(distance)
    if (!date || !categoryId || !Number.isFinite(distance_km) || distance_km <= 0) return
    onSubmit({
      category_id: categoryId,
      date,
      distance_km,
      duration_min: duration ? parseInt(duration, 10) : null,
      note: note || null,
    })
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl bg-white p-4 shadow sm:grid-cols-2">
      <label className="flex flex-col text-sm">
        Kategorie
        <select
          className="rounded border p-2"
          value={categoryId}
          onChange={(e) => setCategoryId(Number(e.target.value))}
        >
          {active.map((c) => (
            <option key={c.id} value={c.id}>
              {c.icon_emoji} {c.name} ({c.factor}x)
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-sm">
        Datum
        <input
          type="date"
          className="rounded border p-2"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </label>
      <label className="flex flex-col text-sm">
        Distanz (km)
        <input
          type="number"
          step="0.01"
          min="0.01"
          className="rounded border p-2"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
        />
      </label>
      <label className="flex flex-col text-sm">
        Dauer (min, optional)
        <input
          type="number"
          min="1"
          className="rounded border p-2"
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
        />
      </label>
      <label className="flex flex-col text-sm sm:col-span-2">
        Notiz
        <input
          className="rounded border p-2"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <button className="rounded bg-emerald-600 p-2 font-semibold text-white sm:col-span-2">
        Speichern
      </button>
    </form>
  )
}
```

- [ ] **Step 3: Tests grün**

Run: `cd frontend; npm test`
Expected: 3 passed

- [ ] **Step 4: Seite mit Liste und Mutationen**

`frontend/src/pages/MeineAktivitaeten.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Activity, type ActivityInput } from '../api/client'
import ActivityForm from '../components/activities/ActivityForm'

export default function MeineAktivitaeten() {
  const year = new Date().getFullYear()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Activity | null>(null)
  const [error, setError] = useState('')

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities = [] } = useQuery({
    queryKey: ['activities', year],
    queryFn: () => api.activities(year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['activities'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const save = useMutation({
    mutationFn: (input: ActivityInput) =>
      editing ? api.patchActivity(editing.id, input) : api.createActivity(input),
    onSuccess: () => {
      setEditing(null)
      setError('')
      invalidate()
    },
    onError: (e) => setError(e.message),
  })
  const remove = useMutation({ mutationFn: api.deleteActivity, onSuccess: invalidate })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{editing ? 'Eintrag bearbeiten' : 'Neue Aktivität'}</h1>
      <ActivityForm
        key={editing?.id ?? 'new'}
        categories={categories}
        initial={editing ?? undefined}
        onSubmit={save.mutate}
      />
      {editing && (
        <button className="text-sm text-gray-500 underline" onClick={() => setEditing(null)}>
          Bearbeiten abbrechen
        </button>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <h2 className="text-lg font-semibold">Meine Einträge {year}</h2>
      <ul className="space-y-2">
        {activities.map((a) => {
          const cat = catById.get(a.category_id)
          return (
            <li key={a.id} className="flex items-center gap-3 rounded-xl bg-white p-3 shadow">
              <span className="text-xl">{cat?.icon_emoji}</span>
              <div className="flex-1">
                <p className="font-medium">
                  {a.date} · {a.distance_km} km {cat?.name} → <b>{a.scaled_km} km</b>
                  {a.edited && <span className="ml-2 text-xs text-gray-400">(bearbeitet)</span>}
                </p>
                {(a.note || a.duration_min) && (
                  <p className="text-sm text-gray-500">
                    {a.duration_min ? `${a.duration_min} min` : ''}
                    {a.duration_min && a.note ? ' · ' : ''}
                    {a.note}
                  </p>
                )}
              </div>
              <button className="text-sm underline" onClick={() => setEditing(a)}>
                Bearbeiten
              </button>
              <button
                className="text-sm text-red-600 underline"
                onClick={() => confirm('Eintrag löschen?') && remove.mutate(a.id)}
              >
                Löschen
              </button>
            </li>
          )
        })}
        {activities.length === 0 && <p className="text-gray-500">Noch keine Einträge.</p>}
      </ul>
    </div>
  )
}
```

In `frontend/src/App.tsx`: Platzhalter-Zeile `const MeineAktivitaeten = () => …` löschen und importieren: `import MeineAktivitaeten from './pages/MeineAktivitaeten'`.

- [ ] **Step 5: Manuell prüfen, committen**

Run: Backend + `npm run dev`; Aktivität anlegen, bearbeiten (→ „(bearbeitet)" erscheint), löschen.

```bash
git add frontend/
git commit -m "feat: activities page with form, list, edit/delete"
```

---

### Task 13: pathMath — Positionslogik für die Wanderkarte

**Files:**
- Create: `frontend/src/components/comparison/pathMath.ts`, `frontend/src/components/comparison/pathMath.test.ts`

- [ ] **Step 1: Failing Tests**

`frontend/src/components/comparison/pathMath.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { progressFraction, spreadBadges } from './pathMath'

describe('progressFraction', () => {
  it('berechnet den Anteil zum Ziel', () => {
    expect(progressFraction(250, 1000)).toBe(0.25)
  })
  it('kappt bei 1 wenn das Ziel überschritten ist', () => {
    expect(progressFraction(1500, 1000)).toBe(1)
  })
  it('ist 0 bei Ziel 0 oder negativer Distanz', () => {
    expect(progressFraction(100, 0)).toBe(0)
    expect(progressFraction(-5, 1000)).toBe(0)
  })
})

describe('spreadBadges', () => {
  it('lässt entfernte Punkte auf Ebene 0', () => {
    const lanes = spreadBadges([
      { id: 1, x: 0 },
      { id: 2, x: 500 },
    ], 60)
    expect(lanes.get(1)).toBe(0)
    expect(lanes.get(2)).toBe(0)
  })
  it('stapelt nahe Punkte auf verschiedene Ebenen', () => {
    const lanes = spreadBadges([
      { id: 1, x: 100 },
      { id: 2, x: 110 },
      { id: 3, x: 130 },
    ], 60)
    expect(new Set([lanes.get(1), lanes.get(2), lanes.get(3)]).size).toBe(3)
  })
})
```

Run: `cd frontend; npm test`
Expected: FAIL — `Cannot find module './pathMath'`

- [ ] **Step 2: Implementieren**

`frontend/src/components/comparison/pathMath.ts`:

```ts
/** Anteil [0..1] der Strecke zum Jahresziel; >Ziel sitzt am Ende (🏁). */
export function progressFraction(scaledKm: number, goalKm: number): number {
  if (goalKm <= 0 || scaledKm <= 0) return 0
  return Math.min(scaledKm / goalKm, 1)
}

/**
 * Verteilt Namens-Badges auf vertikale Ebenen (0,1,2,…), damit nahe
 * Avatare sich nicht überdecken. Punkte näher als minDist (in
 * SVG-Einheiten) bekommen unterschiedliche Ebenen.
 */
export function spreadBadges(
  points: { id: number; x: number }[],
  minDist: number,
): Map<number, number> {
  const sorted = [...points].sort((a, b) => a.x - b.x)
  const lanes = new Map<number, number>()
  const lastXPerLane: number[] = []
  for (const p of sorted) {
    let lane = 0
    while (lane < lastXPerLane.length && p.x - lastXPerLane[lane] < minDist) lane++
    lastXPerLane[lane] = p.x
    lanes.set(p.id, lane)
  }
  return lanes
}
```

- [ ] **Step 3: Tests grün, committen**

Run: `cd frontend; npm test`
Expected: 8 passed (3 Form + 5 pathMath)

```bash
git add frontend/src/components/comparison/
git commit -m "feat: pathMath with progress fraction and badge spreading"
```

---

### Task 14: WanderKarte (SVG-Karte mit Avataren)

**Files:**
- Create: `frontend/src/components/comparison/WanderKarte.tsx`

- [ ] **Step 1: Komponente implementieren**

Visuell geprüft, keine Pixel-Tests (Spec §7). Die Logik steckt in `pathMath.ts` (Task 13).

`frontend/src/components/comparison/WanderKarte.tsx`:

```tsx
import { useLayoutEffect, useRef, useState } from 'react'
import type { Comparison } from '../../api/client'
import { progressFraction, spreadBadges } from './pathMath'

const TRAIL = 'M 40,460 C 120,330 220,300 320,320 S 520,400 640,360 S 820,180 920,150'

type Point = { x: number; y: number }

export default function WanderKarte({ data }: { data: Comparison }) {
  const pathRef = useRef<SVGPathElement>(null)
  const [points, setPoints] = useState<Map<number, Point>>(new Map())
  const [milestonePoints, setMilestonePoints] = useState<Point[]>([])
  const [selected, setSelected] = useState<number | null>(null)

  useLayoutEffect(() => {
    const path = pathRef.current
    if (!path) return
    const len = path.getTotalLength()
    const at = (fraction: number) => {
      const p = path.getPointAtLength(fraction * len)
      return { x: p.x, y: p.y }
    }
    setPoints(
      new Map(
        data.users.map((u) => [
          u.user_id,
          at(progressFraction(u.total_scaled_km, data.goal_km)),
        ]),
      ),
    )
    setMilestonePoints(data.milestones.map((m) => at(progressFraction(m.km, data.goal_km))))
  }, [data])

  const badgeLanes = spreadBadges(
    data.users.map((u) => ({ id: u.user_id, x: points.get(u.user_id)?.x ?? 0 })),
    120,
  )

  const selectedUser = data.users.find((u) => u.user_id === selected)

  return (
    <div className="space-y-3">
    <svg viewBox="0 0 960 520" className="w-full rounded-2xl shadow">
      {data.map_image ? (
        <image href={data.map_image} width="960" height="520" preserveAspectRatio="xMidYMid slice" />
      ) : (
        <Landschaft />
      )}
      <path d={TRAIL} fill="none" stroke="#f7ecd4" strokeWidth="16" strokeLinecap="round" />
      <path
        ref={pathRef}
        d={TRAIL}
        fill="none"
        stroke="#cdab72"
        strokeWidth="3"
        strokeDasharray="10,9"
        strokeLinecap="round"
      />
      {data.milestones.map((m, i) => {
        const p = milestonePoints[i]
        if (!p) return null
        return (
          <g key={m.km}>
            <circle cx={p.x} cy={p.y} r="14" fill="#fff" stroke="#cdab72" strokeWidth="3" />
            <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="14">{m.emoji}</text>
            <text x={p.x} y={p.y + 32} textAnchor="middle" fontSize="11" fill="#666">
              {m.label} · {m.km} km
            </text>
          </g>
        )
      })}
      <g>
        <circle cx="920" cy="150" r="16" fill="#ffe9a8" stroke="#e0b84e" strokeWidth="3" />
        <text x="920" y="156" textAnchor="middle" fontSize="15">🏁</text>
        <text x="920" y="124" textAnchor="middle" fontSize="11" fill="#666">{data.goal_km} km</text>
      </g>
      {[...data.users].reverse().map((u) => {
        const p = points.get(u.user_id)
        if (!p) return null
        const lane = badgeLanes.get(u.user_id) ?? 0
        const badgeY = p.y - 28 - lane * 24
        return (
          <g
            key={u.user_id}
            className="cursor-pointer"
            onClick={() => setSelected(u.user_id === selected ? null : u.user_id)}
          >
            <circle cx={p.x} cy={p.y} r="15" fill="#fff" stroke="#888" strokeWidth="2" />
            <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="15">{u.avatar_emoji}</text>
            <rect x={p.x - 52} y={badgeY - 13} width="104" height="18" rx="9" fill="#ffffffdd" />
            <text x={p.x} y={badgeY} textAnchor="middle" fontSize="11" fontWeight="600">
              {u.rank === 1 ? '👑 ' : ''}{u.display_name} · {Math.round(u.total_scaled_km)}
            </text>
          </g>
        )
      })}
    </svg>
      {selectedUser && (
        <div className="rounded-xl bg-white p-3 shadow">
          <p className="font-semibold">
            {selectedUser.avatar_emoji} {selectedUser.display_name} —{' '}
            {Math.round(selectedUser.total_scaled_km)} von {data.goal_km} km
          </p>
          <ul className="mt-1 flex flex-wrap gap-3 text-sm">
            {selectedUser.by_category.map((b) => (
              <li key={b.category_id} className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded-full" style={{ background: b.color }} />
                {b.icon_emoji} {b.name}: {Math.round(b.scaled_km)} km
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function Landschaft() {
  return (
    <g>
      <rect width="960" height="520" fill="#e7f0d8" />
      <ellipse cx="220" cy="120" rx="190" ry="80" fill="#7db86a" />
      <circle cx="160" cy="100" r="22" fill="#4e8c3f" />
      <circle cx="220" cy="125" r="26" fill="#5da04c" />
      <circle cx="280" cy="95" r="20" fill="#4e8c3f" />
      <polygon points="680,170 770,40 860,170" fill="#a8a29a" />
      <polygon points="745,75 770,40 795,75 770,88" fill="#f4f4f2" />
      <polygon points="770,170 840,80 910,170" fill="#bdb8b0" />
      <path d="M 0,400 Q 240,360 480,410 T 960,390 L 960,520 L 0,520 Z" fill="#79b9dd" />
      <path
        d="M 90,440 q 20,-9 40,0 M 300,465 q 20,-9 40,0 M 540,445 q 20,-9 40,0"
        stroke="#fff" strokeWidth="3" fill="none" opacity="0.7" strokeLinecap="round"
      />
    </g>
  )
}
```

- [ ] **Step 2: Build prüfen, committen**

Run: `cd frontend; npm run build`
Expected: kein TypeScript-Fehler.

```bash
git add frontend/src/components/comparison/WanderKarte.tsx
git commit -m "feat: WanderKarte svg map with avatars, milestones, image layer"
```

---

### Task 15: RaceBahnen + JahresVerlauf

**Files:**
- Create: `frontend/src/components/comparison/RaceBahnen.tsx`, `frontend/src/components/comparison/JahresVerlauf.tsx`

- [ ] **Step 1: RaceBahnen implementieren**

`frontend/src/components/comparison/RaceBahnen.tsx`:

```tsx
import type { Comparison } from '../../api/client'

export default function RaceBahnen({ data }: { data: Comparison }) {
  const maxKm = Math.max(data.goal_km, ...data.users.map((u) => u.total_scaled_km))
  const pct = (km: number) => `${(km / maxKm) * 100}%`

  return (
    <div className="overflow-x-auto rounded-2xl bg-white p-4 shadow">
      <div className="relative min-w-[700px] space-y-5 pt-6 pb-2">
        {data.milestones.map((m) => (
          <div
            key={m.km}
            className="absolute top-0 bottom-0 border-l-2 border-dashed border-gray-300"
            style={{ left: pct(m.km) }}
          >
            <span className="absolute -top-1 -translate-x-1/2 text-xs whitespace-nowrap text-gray-500">
              {m.emoji} {m.km}
            </span>
          </div>
        ))}
        <div
          className="absolute top-0 bottom-0 border-l-2 border-amber-400"
          style={{ left: pct(data.goal_km) }}
        >
          <span className="absolute -top-1 -translate-x-1/2 text-xs text-amber-600">
            🏁 {data.goal_km}
          </span>
        </div>
        {data.users.map((u) => (
          <div key={u.user_id}>
            <p className="mb-1 text-sm font-semibold">
              {u.rank === 1 ? '👑 ' : ''}{u.avatar_emoji} {u.display_name} ·{' '}
              {Math.round(u.total_scaled_km)} km
            </p>
            <div className="flex h-5 overflow-hidden rounded-full bg-gray-100">
              {u.segments.map((s, i) => (
                <div
                  key={i}
                  style={{ width: pct(s.scaled_km), background: s.color }}
                  title={`${s.date}: ${s.scaled_km} km`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: JahresVerlauf implementieren**

`frontend/src/components/comparison/JahresVerlauf.tsx`:

```tsx
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Comparison } from '../../api/client'

const COLORS = ['#e74c3c', '#3498db', '#27ae60', '#9b59b6', '#e67e22', '#16a085', '#d35400']

export default function JahresVerlauf({ data }: { data: Comparison }) {
  // Kurven zu einem gemeinsamen Datensatz mergen: eine Zeile pro Datum.
  const byDate = new Map<string, Record<string, number | string>>()
  for (const u of data.users) {
    for (const p of u.cumulative) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[u.display_name] = p.scaled_km
      byDate.set(p.date, row)
    }
  }
  const rows = [...byDate.values()].sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )

  return (
    <div className="rounded-2xl bg-white p-4 shadow">
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" fontSize={11} />
          <YAxis fontSize={11} unit=" km" />
          <Tooltip />
          <Legend />
          {data.milestones.map((m) => (
            <ReferenceLine
              key={m.km}
              y={m.km}
              stroke="#999"
              strokeDasharray="5 4"
              label={{ value: `${m.emoji} ${m.label}`, fontSize: 11, position: 'right' }}
            />
          ))}
          <ReferenceLine y={data.goal_km} stroke="#e0b84e" label={{ value: '🏁 Ziel', fontSize: 11 }} />
          {data.users.map((u, i) => (
            <Line
              key={u.user_id}
              dataKey={u.display_name}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2.5}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
```

- [ ] **Step 3: Build prüfen, committen**

Run: `cd frontend; npm run build`
Expected: kein TypeScript-Fehler.

```bash
git add frontend/src/components/comparison/
git commit -m "feat: race lanes and cumulative year chart"
```

---

### Task 16: Vergleichs-Seite (Tabs + Jahreswahl) und Admin-Seite

**Files:**
- Create: `frontend/src/pages/Vergleich.tsx`, `frontend/src/pages/Admin.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Vergleichs-Seite**

`frontend/src/pages/Vergleich.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import JahresVerlauf from '../components/comparison/JahresVerlauf'
import RaceBahnen from '../components/comparison/RaceBahnen'
import WanderKarte from '../components/comparison/WanderKarte'

const TABS = ['Wanderkarte', 'Race-Bahnen', 'Jahresverlauf'] as const

export default function Vergleich() {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Wanderkarte')
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [year, setYear] = useState(new Date().getFullYear())
  const { data, error } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1 text-sm ${
              tab === t ? 'bg-emerald-600 text-white' : 'bg-white shadow'
            }`}
          >
            {t}
          </button>
        ))}
        <select
          className="ml-auto rounded border bg-white p-1 text-sm"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.year}>{s.year}</option>
          ))}
        </select>
      </div>
      {error && <p className="text-red-600">{error.message}</p>}
      {data && tab === 'Wanderkarte' && <WanderKarte data={data} />}
      {data && tab === 'Race-Bahnen' && <RaceBahnen data={data} />}
      {data && tab === 'Jahresverlauf' && <JahresVerlauf data={data} />}
    </div>
  )
}
```

- [ ] **Step 2: Admin-Seite**

`frontend/src/pages/Admin.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Milestone, type Season } from '../api/client'

export default function Admin() {
  return (
    <div className="space-y-8">
      <Kategorien />
      <Jahr />
      <NeuerUser />
    </div>
  )
}

function Kategorien() {
  const queryClient = useQueryClient()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['categories'] })
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: number; factor?: number; is_active?: boolean }) =>
      api.patchCategory(id, b),
    onSuccess: refresh,
  })
  const [neu, setNeu] = useState({ name: '', factor: '1', color: '#888888', icon_emoji: '🏅' })
  const create = useMutation({
    mutationFn: () =>
      api.createCategory({ ...neu, factor: parseFloat(neu.factor) }),
    onSuccess: () => {
      setNeu({ name: '', factor: '1', color: '#888888', icon_emoji: '🏅' })
      refresh()
    },
  })

  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-bold">Kategorien & Faktoren</h2>
      <table className="w-full text-sm">
        <tbody>
          {categories.map((c) => (
            <tr key={c.id} className={`border-b ${c.is_active ? '' : 'opacity-40'}`}>
              <td className="py-1">{c.icon_emoji} {c.name}</td>
              <td>
                <input
                  type="number"
                  step="0.5"
                  defaultValue={c.factor}
                  className="w-20 rounded border p-1"
                  onBlur={(e) => {
                    const factor = parseFloat(e.target.value)
                    if (factor > 0 && factor !== c.factor) patch.mutate({ id: c.id, factor })
                  }}
                />{' '}x
              </td>
              <td className="text-right">
                <button
                  className="underline"
                  onClick={() => patch.mutate({ id: c.id, is_active: !c.is_active })}
                >
                  {c.is_active ? 'Deaktivieren' : 'Aktivieren'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex flex-wrap gap-2">
        <input className="rounded border p-1 text-sm" placeholder="Name" value={neu.name}
          onChange={(e) => setNeu({ ...neu, name: e.target.value })} />
        <input className="w-16 rounded border p-1 text-sm" placeholder="Faktor" value={neu.factor}
          onChange={(e) => setNeu({ ...neu, factor: e.target.value })} />
        <input className="w-14 rounded border p-1 text-sm" value={neu.icon_emoji}
          onChange={(e) => setNeu({ ...neu, icon_emoji: e.target.value })} />
        <input type="color" className="h-8 w-10" value={neu.color}
          onChange={(e) => setNeu({ ...neu, color: e.target.value })} />
        <button
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
          disabled={!neu.name || !(parseFloat(neu.factor) > 0)}
          onClick={() => create.mutate()}
        >
          Kategorie anlegen
        </button>
      </div>
    </section>
  )
}

function Jahr() {
  const queryClient = useQueryClient()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season: Season | undefined = seasons.find((s) => s.year === new Date().getFullYear())
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['seasons'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const [goal, setGoal] = useState('')
  const [milestones, setMilestones] = useState<Milestone[] | null>(null)
  if (!season) return null
  const ms = milestones ?? season.milestones

  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-bold">Jahr {season.year}</h2>
      <label className="text-sm">
        Ziel (skalierte km):{' '}
        <input
          type="number"
          className="w-28 rounded border p-1"
          defaultValue={season.goal_km}
          onChange={(e) => setGoal(e.target.value)}
        />
      </label>
      <h3 className="mt-3 text-sm font-semibold">Meilensteine</h3>
      {ms.map((m, i) => (
        <div key={i} className="mt-1 flex gap-2 text-sm">
          <input type="number" className="w-24 rounded border p-1" value={m.km}
            onChange={(e) => setMilestones(ms.map((x, j) => j === i ? { ...x, km: Number(e.target.value) } : x))} />
          <input className="flex-1 rounded border p-1" value={m.label}
            onChange={(e) => setMilestones(ms.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} />
          <input className="w-14 rounded border p-1" value={m.emoji}
            onChange={(e) => setMilestones(ms.map((x, j) => j === i ? { ...x, emoji: e.target.value } : x))} />
          <button className="text-red-600" onClick={() => setMilestones(ms.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <div className="mt-2 flex gap-2">
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() => setMilestones([...ms, { km: 0, label: '', emoji: '🚩' }])}
        >
          + Meilenstein
        </button>
        <button
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
          onClick={() =>
            api
              .patchSeason(season.id, {
                goal_km: goal ? parseFloat(goal) : undefined,
                milestones: ms,
              })
              .then(refresh)
          }
        >
          Speichern
        </button>
      </div>
      <h3 className="mt-4 text-sm font-semibold">Kartenbild (Aquarell)</h3>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="mt-1 text-sm"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) api.uploadMapImage(season.id, file).then(refresh)
        }}
      />
      {season.map_image && <p className="text-xs text-gray-500">Aktuell: {season.map_image}</p>}
    </section>
  )
}

function NeuerUser() {
  const [form, setForm] = useState({ username: '', password: '', display_name: '', avatar_emoji: '🏃' })
  const [message, setMessage] = useState('')
  const create = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: (u) => {
      setMessage(`✓ ${u.display_name} angelegt`)
      setForm({ username: '', password: '', display_name: '', avatar_emoji: '🏃' })
    },
    onError: (e) => setMessage(e.message),
  })
  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-bold">Neuen User anlegen</h2>
      <div className="flex flex-wrap gap-2">
        <input className="rounded border p-1 text-sm" placeholder="Benutzername" value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <input className="rounded border p-1 text-sm" placeholder="Anzeigename" value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        <input className="rounded border p-1 text-sm" placeholder="Passwort" value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <input className="w-14 rounded border p-1 text-sm" value={form.avatar_emoji}
          onChange={(e) => setForm({ ...form, avatar_emoji: e.target.value })} />
        <button
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
          disabled={!form.username || form.password.length < 4 || !form.display_name}
          onClick={() => create.mutate()}
        >
          Anlegen
        </button>
      </div>
      {message && <p className="mt-2 text-sm">{message}</p>}
    </section>
  )
}
```

- [ ] **Step 3: Routen verdrahten**

In `frontend/src/App.tsx` die übrigen Platzhalter-Zeilen (`const Vergleich = …`, `const Admin = …`) löschen und importieren:

```tsx
import Admin from './pages/Admin'
import Vergleich from './pages/Vergleich'
```

- [ ] **Step 4: Alles prüfen, committen**

Run: `cd frontend; npm test; npm run build`
Expected: 8 Tests passed, Build ok.

Manuell: Backend + Dev-Server starten; als admin Kategorien/Ziel/Meilensteine pflegen, zweiten User anlegen, mit beiden Usern Aktivitäten eintragen, alle drei Vergleichs-Tabs prüfen (Krone beim Führenden, Meilensteine sichtbar, Kurven plausibel).

```bash
git add frontend/
git commit -m "feat: comparison page with three views + admin page"
```

---

### Task 17: Docker, Compose, README

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`
- Modify: `README.md`

- [ ] **Step 1: Dockerfile (Multi-Stage)**

`Dockerfile`:

```dockerfile
# Stage 1: Frontend bauen
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + statisches Frontend
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --no-dev --frozen 2>/dev/null || uv sync --no-dev
COPY backend/app ./app
COPY --from=frontend /build/dist /srv/frontend/dist

ENV DATA_DIR=/data \
    FRONTEND_DIST=/srv/frontend/dist
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore`:

```
**/node_modules
**/dist
**/.venv
**/__pycache__
data/
.superpowers/
docs/
```

- [ ] **Step 2: docker-compose.yml**

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      SECRET_KEY: ${SECRET_KEY:?SECRET_KEY setzen}
      ADMIN_USER: ${ADMIN_USER:-admin}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?ADMIN_PASSWORD setzen}
    restart: unless-stopped
```

- [ ] **Step 3: README**

`README.md` (komplett ersetzen):

```markdown
# MeterMachen 🏃🚴🥾

Kilometer-Tracking mit skalierten Kategorien und Jahres-Distanzvergleich
für den Freundeskreis. FastAPI + React, SQLite, ein Container.

## Betrieb

    SECRET_KEY=<zufälliger-string> ADMIN_PASSWORD=<passwort> docker compose up -d --build

App: http://localhost:8000 — Login mit `admin` / `<passwort>`.
Backup: den Ordner `./data` kopieren (SQLite-DB + Kartenbilder).

## Entwicklung

    cd backend && uv sync && uv run uvicorn app.main:app --reload   # API :8000
    cd frontend && npm install && npm run dev                       # UI  :5173

Tests: `cd backend && uv run pytest` · `cd frontend && npm test`

## Doku

- Spec: docs/superpowers/specs/2026-06-12-metermachen-design.md
- Plan: docs/superpowers/plans/2026-06-12-metermachen-v1.md
```

- [ ] **Step 4: Bauen, Smoke-Test, committen**

Run: `SECRET_KEY=test ADMIN_PASSWORD=test docker compose up -d --build` (PowerShell: `$env:SECRET_KEY='test'; $env:ADMIN_PASSWORD='test'; docker compose up -d --build`)
Expected: `http://localhost:8000` zeigt die Login-Maske; Login mit admin/test; Aktivität anlegen; Wanderkarte rendert. Danach `docker compose down`.

```bash
git add Dockerfile docker-compose.yml .dockerignore README.md
git commit -m "feat: docker deployment (single container, sqlite volume)"
```

---

## Nicht in V1 (bewusst)

- Strava/Sportuhr-Import — Datenmodell ist vorbereitet (`source`, `external_id`), kommt als eigenes Spec/Plan-Paket
- E2E-Tests (Playwright)
- Mini-Games / Sonderfelder auf der Karte
- HTTPS (macht der Reverse-Proxy des Servers)






