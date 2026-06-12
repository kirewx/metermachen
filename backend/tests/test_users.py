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
