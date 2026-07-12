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


def test_inactive_user_hidden_from_comparison(client, session):
    erik, lisa = setup_data(session)
    lisa.is_active = False
    session.add(lisa)
    session.commit()
    login(client)
    users = client.get("/api/comparison/2026").json()["users"]
    assert [u["display_name"] for u in users] == ["Erik"]


def _stichtag_setup(session, start_offset_days):
    """Season mit start_date relativ zu heute; Aktivitäten um den Stichtag."""
    from datetime import timedelta

    user = make_user(session, is_admin=True)
    cat = make_category(session, factor=1.0)
    start = date.today() + timedelta(days=start_offset_days)
    season = Season(
        year=date.today().year, goal_km=1000, start_date=start, milestones_json="[]"
    )
    session.add(season)
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=start - timedelta(days=1), distance_km=10))
    if start_offset_days <= 0:
        session.add(Activity(user_id=user.id, category_id=cat.id,
                             date=start, distance_km=7))
    session.commit()
    return user, start


def test_comparison_counts_everything_before_start(client, session):
    _stichtag_setup(session, start_offset_days=5)  # Start in Zukunft = Testphase
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    assert r.json()["users"][0]["total_scaled_km"] == 10.0
    assert r.json()["start_date"] is not None


def test_comparison_counts_only_from_start_after_start(client, session):
    _stichtag_setup(session, start_offset_days=0)  # Start heute = Challenge läuft
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    assert r.json()["users"][0]["total_scaled_km"] == 7.0


def test_comparison_warmup_phase(client, session):
    _stichtag_setup(session, start_offset_days=0)
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}?phase=warmup")
    assert r.json()["users"][0]["total_scaled_km"] == 10.0
    assert r.json()["phase"] == "warmup"


def test_comparison_warmup_404_ohne_startdatum(client, session):
    make_user(session, is_admin=True)
    session.add(Season(year=date.today().year, goal_km=1000, milestones_json="[]"))
    session.commit()
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}?phase=warmup")
    assert r.status_code == 404


def test_comparison_applies_km_factor(client, session):
    user, _ = _stichtag_setup(session, start_offset_days=0)
    user.km_factor = 3.0
    session.add(user)
    session.commit()
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    assert r.json()["users"][0]["total_scaled_km"] == 21.0
    assert r.json()["users"][0]["km_factor"] == 3.0


def test_comparison_warmup_ignores_km_factor(client, session):
    user, _ = _stichtag_setup(session, start_offset_days=0)
    user.km_factor = 3.0
    session.add(user)
    session.commit()
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}?phase=warmup")
    assert r.json()["users"][0]["total_scaled_km"] == 10.0
