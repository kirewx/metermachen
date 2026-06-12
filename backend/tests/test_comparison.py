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
    add_activity(session, erik, jog, date(2026, 1, 10), 5)  # 20 skaliert
    add_activity(session, erik, rad, date(2026, 2, 1), 30)  # 30 skaliert
    add_activity(session, lisa, jog, date(2026, 1, 15), 10)  # 40 skaliert
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
