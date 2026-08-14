from app import auth
from tests.conftest import login, make_user


def _create_link(client, user_id):
    return client.post(f"/api/users/{user_id}/reset-link")


def _reset(client, token, password="neu1234"):
    return client.post(
        "/api/auth/reset-password", json={"token": token, "password": password}
    )


def test_create_link_admin_only(client, session):
    user = make_user(session)  # kein Admin
    login(client)
    assert _create_link(client, user.id).status_code == 403


def test_admin_creates_link_with_url_and_expiry(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="chef")
    r = _create_link(client, lisa.id)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"]
    assert body["url"].endswith("/passwort-reset/" + body["token"])
    assert body["expires_at"]


def test_create_link_unknown_user_404(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    assert _create_link(client, 999).status_code == 404


def test_reset_sets_password_and_logs_in(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa", password="alt1234")
    login(client, username="chef")
    token = _create_link(client, lisa.id).json()["token"]
    client.post("/api/auth/logout")

    r = _reset(client, token, "neu1234")
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "lisa"
    # Cookie gesetzt -> /me funktioniert ohne erneuten Login
    assert client.get("/api/auth/me").json()["username"] == "lisa"

    client.post("/api/auth/logout")
    assert (
        client.post(
            "/api/auth/login", json={"username": "lisa", "password": "alt1234"}
        ).status_code
        == 401
    )
    login(client, username="lisa", password="neu1234")


def test_reset_token_is_single_use(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="chef")
    token = _create_link(client, lisa.id).json()["token"]
    client.post("/api/auth/logout")
    assert _reset(client, token, "neu1234").status_code == 200
    assert _reset(client, token, "nochmal99").status_code == 400


def test_reset_rejects_tampered_token(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="chef")
    token = _create_link(client, lisa.id).json()["token"]
    client.post("/api/auth/logout")
    assert _reset(client, token[:-2] + "xx").status_code == 400
    assert _reset(client, "kompletter-unsinn").status_code == 400


def test_reset_rejects_expired_token(client, session, monkeypatch):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="chef")
    token = _create_link(client, lisa.id).json()["token"]
    client.post("/api/auth/logout")
    monkeypatch.setattr(auth, "RESET_MAX_AGE", -1)
    assert _reset(client, token).status_code == 400


def test_reset_rejects_deactivated_account(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    lisa.is_active = False
    session.add(lisa)
    session.commit()
    login(client, username="chef")
    token = _create_link(client, lisa.id).json()["token"]
    client.post("/api/auth/logout")
    assert _reset(client, token).status_code == 403


def test_reset_rejects_short_password(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client, username="chef")
    token = _create_link(client, lisa.id).json()["token"]
    client.post("/api/auth/logout")
    assert _reset(client, token, "abc").status_code == 422
