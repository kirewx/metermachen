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
