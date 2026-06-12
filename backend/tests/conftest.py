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
    cat = Category(name=name, factor=factor, color="#e74c3c", icon_emoji="🏃", **kw)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat
