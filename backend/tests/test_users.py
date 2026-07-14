from datetime import date

from sqlmodel import select

from app.models import Activity, StravaConnection, User
from tests.conftest import login, make_category, make_user


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
        json={"display_name": "Erik W.", "avatar": "🚴", "password": "neu789"},
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Erik W."
    assert r.json()["avatar"] == "🚴"
    client.post("/api/auth/logout")
    login(client, password="neu789")


def test_patch_own_username(client, session):
    make_user(session)
    login(client)
    r = client.patch("/api/users/me", json={"username": "erik2"})
    assert r.status_code == 200
    assert r.json()["username"] == "erik2"
    client.post("/api/auth/logout")
    login(client, username="erik2")


def test_patch_own_username_taken(client, session):
    make_user(session)
    make_user(session, username="lisa")
    login(client)
    assert client.patch("/api/users/me", json={"username": "lisa"}).status_code == 409
    # Der eigene (unveränderte) Name ist dagegen kein Konflikt.
    assert client.patch("/api/users/me", json={"username": "erik"}).status_code == 200


def test_list_users_admin_only(client, session):
    make_user(session)
    login(client)
    assert client.get("/api/users").status_code == 403


def test_list_users_returns_all_with_username(client, session):
    make_user(session, username="chef", is_admin=True)
    make_user(session, username="lisa")
    login(client, username="chef")
    r = client.get("/api/users")
    assert r.status_code == 200
    users = {u["username"]: u for u in r.json()}
    assert set(users) == {"chef", "lisa"}
    assert users["lisa"]["display_name"] == "Lisa"
    assert users["lisa"]["is_active"] is True
    assert users["chef"]["is_admin"] is True


def test_deactivate_user_blocks_login_and_session(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="lisa")  # Lisa hat eine aktive Session
    lisa_cookies = dict(client.cookies)
    login(client, username="chef")
    r = client.patch(f"/api/users/{lisa.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    # Login abgewiesen …
    r = client.post("/api/auth/login", json={"username": "lisa", "password": "pw123"})
    assert r.status_code == 403
    # … und die alte Session ist ebenfalls tot.
    client.cookies = lisa_cookies
    assert client.get("/api/auth/me").status_code == 401


def test_reactivate_user(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="chef")
    client.patch(f"/api/users/{lisa.id}", json={"is_active": False})
    r = client.patch(f"/api/users/{lisa.id}", json={"is_active": True})
    assert r.json()["is_active"] is True
    client.post("/api/auth/logout")
    login(client, username="lisa")


def test_cannot_deactivate_self(client, session):
    chef = make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = client.patch(f"/api/users/{chef.id}", json={"is_active": False})
    assert r.status_code == 409


def test_deactivate_requires_admin(client, session):
    make_user(session)
    lisa = make_user(session, username="lisa")
    login(client)
    assert client.patch(f"/api/users/{lisa.id}", json={"is_active": False}).status_code == 403


def test_delete_user_removes_dependent_data(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    cat = make_category(session)
    session.add(Activity(user_id=lisa.id, category_id=cat.id, date=date(2026, 3, 1), distance_km=5))
    session.add(StravaConnection(
        user_id=lisa.id, athlete_id=7, access_token="a", refresh_token="r", expires_at=1
    ))
    session.commit()
    login(client, username="chef")
    assert client.delete(f"/api/users/{lisa.id}").status_code == 204
    assert session.get(User, lisa.id) is None
    assert session.exec(select(Activity).where(Activity.user_id == lisa.id)).first() is None
    assert session.exec(
        select(StravaConnection).where(StravaConnection.user_id == lisa.id)
    ).first() is None


def test_cannot_delete_self(client, session):
    chef = make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    assert client.delete(f"/api/users/{chef.id}").status_code == 409


def test_admin_sets_km_factor(client, session):
    make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client)
    r = client.patch(f"/api/users/{lisa.id}", json={"km_factor": 3.0})
    assert r.status_code == 200
    assert r.json()["km_factor"] == 3.0


def test_km_factor_must_be_positive(client, session):
    make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client)
    assert client.patch(f"/api/users/{lisa.id}", json={"km_factor": 0}).status_code == 422


def test_user_activities_lists_members_entries(client, session):
    erik = make_user(session)  # eingeloggter Betrachter
    lisa = make_user(session, username="lisa")
    cat = make_category(session, factor=4.0)
    session.add(Activity(user_id=lisa.id, category_id=cat.id, date=date(2026, 3, 1),
                         distance_km=5.0, elevation_m=120.0, source="strava",
                         external_id="42"))
    session.add(Activity(user_id=lisa.id, category_id=cat.id, date=date(2025, 3, 1),
                         distance_km=9.0))  # anderes Jahr, darf nicht auftauchen
    session.commit()
    login(client)  # als erik
    r = client.get(f"/api/users/{lisa.id}/activities", params={"year": 2026})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    assert body[0]["distance_km"] == 5.0
    assert body[0]["scaled_km"] == 20.0
    assert body[0]["elevation_m"] == 120.0
    assert body[0]["strava_url"] == "https://www.strava.com/activities/42"


def test_user_activities_requires_login(client, session):
    lisa = make_user(session, username="lisa")
    assert client.get(f"/api/users/{lisa.id}/activities", params={"year": 2026}).status_code == 401


def test_user_activities_404_for_inactive(client, session):
    make_user(session)
    lisa = make_user(session, username="lisa")
    lisa.is_active = False
    session.add(lisa)
    session.commit()
    login(client)
    assert client.get(f"/api/users/{lisa.id}/activities", params={"year": 2026}).status_code == 404
