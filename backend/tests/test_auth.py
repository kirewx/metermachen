from app import config
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


def test_login_rejected_for_inactive_user(client, session):
    user = make_user(session)
    user.is_active = False
    session.add(user)
    session.commit()
    r = client.post("/api/auth/login", json={"username": "erik", "password": "pw123"})
    assert r.status_code == 403


def test_cookie_has_secure_flag_when_configured(client, session, monkeypatch):
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", True)
    make_user(session)
    r = client.post("/api/auth/login", json={"username": "erik", "password": "pw123"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_cookie_without_secure_flag_by_default(client, session, monkeypatch):
    monkeypatch.setattr(config, "SESSION_COOKIE_SECURE", False)
    make_user(session)
    r = client.post("/api/auth/login", json={"username": "erik", "password": "pw123"})
    assert "secure" not in r.headers["set-cookie"].lower()
