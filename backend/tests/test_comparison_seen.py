from datetime import date

from sqlmodel import select

from app.models import Activity, ComparisonSeen, Season
from tests.conftest import login, make_category, make_user


def _setup(session):
    erik = make_user(session)
    cat = make_category(session, factor=2.0)  # scaled = distance * 2
    session.add(Season(year=2026, goal_km=1000.0))
    session.commit()
    session.add(Activity(user_id=erik.id, category_id=cat.id, date=date(2026, 1, 10), distance_km=10))
    session.commit()
    return erik


def test_last_seen_null_without_snapshot(client, session):
    _setup(session)
    login(client)
    r = client.get("/api/comparison/2026/last-seen")
    assert r.status_code == 200
    assert r.json() is None


def test_mark_seen_then_last_seen_returns_snapshot(client, session):
    _setup(session)
    login(client)
    r = client.post("/api/comparison/2026/seen")
    assert r.status_code == 200
    entry = r.json()["entries"][0]
    assert entry["scaled_km"] == 20.0
    assert entry["rank"] == 1
    g = client.get("/api/comparison/2026/last-seen").json()
    assert g["entries"][0]["scaled_km"] == 20.0
    assert "seen_at" in g


def test_mark_seen_is_idempotent_per_user_year(client, session):
    _setup(session)
    login(client)
    client.post("/api/comparison/2026/seen")
    client.post("/api/comparison/2026/seen")
    rows = session.exec(select(ComparisonSeen)).all()
    assert len(rows) == 1


def test_seen_requires_login(client, session):
    _setup(session)
    r = client.post("/api/comparison/2026/seen")
    assert r.status_code == 401
