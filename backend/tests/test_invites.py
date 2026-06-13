from datetime import datetime, timedelta, timezone

from app.models import Invite
from tests.conftest import login, make_user


def _create_invite(client):
    return client.post("/api/invites", json={"display_name": "Lisa"})


def test_create_invite_admin_only(client, session):
    make_user(session)  # kein Admin
    login(client)
    assert _create_invite(client).status_code == 403


def test_admin_creates_invite_returns_token_and_url(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = _create_invite(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"]
    assert body["url"].endswith("/einladung/" + body["token"])
    assert body["used_at"] is None


def test_public_can_check_valid_token(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    client.post("/api/auth/logout")
    r = client.get(f"/api/invites/{token}")
    assert r.status_code == 200
    assert r.json() == {"valid": True, "display_name": "Lisa", "expired": False, "used": False}


def test_unknown_token_is_invalid(client):
    r = client.get("/api/invites/does-not-exist")
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_accept_creates_user_and_logs_in(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    client.post("/api/auth/logout")
    r = client.post(
        f"/api/invites/{token}/accept",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "lisa"
    assert r.json()["is_admin"] is False
    # Cookie gesetzt -> /me funktioniert ohne erneuten Login
    assert client.get("/api/auth/me").json()["username"] == "lisa"


def test_accept_is_single_use(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    body = {"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"}
    assert client.post(f"/api/invites/{token}/accept", json=body).status_code == 200
    body2 = {**body, "username": "tom"}
    assert client.post(f"/api/invites/{token}/accept", json=body2).status_code == 409


def test_accept_rejects_expired(client, session):
    admin = make_user(session, username="chef", is_admin=True)
    invite = Invite(
        token="abgelaufen",
        created_by=admin.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(invite)
    session.commit()
    r = client.post(
        "/api/invites/abgelaufen/accept",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"},
    )
    assert r.status_code == 410


def test_accept_rejects_duplicate_username(client, session):
    make_user(session, username="lisa")  # existiert schon
    admin = make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    client.post("/api/auth/logout")
    r = client.post(
        f"/api/invites/{token}/accept",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"},
    )
    assert r.status_code == 409


def test_admin_can_list_and_delete(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    invite_id = _create_invite(client).json()["id"]
    assert len(client.get("/api/invites").json()) == 1
    assert client.delete(f"/api/invites/{invite_id}").status_code == 204
    assert client.get("/api/invites").json() == []
