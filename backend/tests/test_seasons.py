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


def test_create_duplicate_season_year_conflict(client, session):
    make_user(session, username="chef", is_admin=True)
    make_season(session)
    login(client, username="chef")
    r = client.post("/api/seasons", json={"year": 2026, "goal_km": 500})
    assert r.status_code == 409


def test_patch_season_empty_milestones_clears(client, session):
    make_user(session, username="chef", is_admin=True)
    season = make_season(session)
    login(client, username="chef")
    client.patch(
        f"/api/seasons/{season.id}",
        json={"milestones": [{"km": 100, "label": "x", "emoji": "🚩"}]},
    )
    r = client.patch(f"/api/seasons/{season.id}", json={"milestones": []})
    assert r.status_code == 200
    assert r.json()["milestones"] == []
