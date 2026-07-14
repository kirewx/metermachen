from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.deps import addon_active, get_session, require_addon
from app.models import AddOn
from tests.conftest import login, make_user

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def _addon(**kw) -> AddOn:
    base = dict(key="demo", label="Demo", enabled=True, active_from=None, active_until=None)
    base.update(kw)
    return AddOn(**base)


# --- addon_active-Logik: Schalter = Master, Fenster plant --------------------


def test_disabled_is_never_active():
    assert addon_active(_addon(enabled=False), NOW) is False


def test_enabled_without_window_is_active():
    assert addon_active(_addon(), NOW) is True


def test_before_window_is_inactive():
    assert addon_active(_addon(active_from=NOW + timedelta(days=1)), NOW) is False


def test_during_window_is_active():
    a = _addon(active_from=NOW - timedelta(days=1), active_until=NOW + timedelta(days=1))
    assert addon_active(a, NOW) is True


def test_after_window_is_inactive():
    assert addon_active(_addon(active_until=NOW - timedelta(days=1)), NOW) is False


def test_naive_window_treated_as_utc():
    # SQLite liefert Datetimes ohne tzinfo zurück — Vergleich darf nicht crashen.
    a = _addon(
        active_from=(NOW - timedelta(days=1)).replace(tzinfo=None),
        active_until=(NOW + timedelta(days=1)).replace(tzinfo=None),
    )
    assert addon_active(a, NOW) is True


# --- require_addon-Guard (404 wenn aus) --------------------------------------


def _guarded_client(session) -> TestClient:
    app = FastAPI()

    @app.get("/guarded", dependencies=[Depends(require_addon("demo"))])
    def guarded():
        return {"ok": True}

    app.dependency_overrides[get_session] = lambda: session
    return TestClient(app)


def test_guard_404_when_addon_missing(session):
    assert _guarded_client(session).get("/guarded").status_code == 404


def test_guard_404_when_addon_disabled(session):
    session.add(AddOn(key="demo", label="Demo", enabled=False))
    session.commit()
    assert _guarded_client(session).get("/guarded").status_code == 404


def test_guard_ok_when_addon_active(session):
    session.add(AddOn(key="demo", label="Demo", enabled=True))
    session.commit()
    assert _guarded_client(session).get("/guarded").status_code == 200


# --- CRUD-API ----------------------------------------------------------------


def test_list_requires_login(client, session):
    assert client.get("/api/addons").status_code == 401


def test_create_requires_admin(client, session):
    make_user(session)
    login(client)
    r = client.post("/api/addons", json={"key": "x", "label": "X"})
    assert r.status_code == 403


def test_admin_creates_addon_default_off(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post("/api/addons", json={"key": "sommer", "label": "Sommer-Event"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["key"] == "sommer"
    assert body["enabled"] is False
    assert body["active"] is False


def test_duplicate_key_conflict(client, session):
    make_user(session, is_admin=True)
    login(client)
    client.post("/api/addons", json={"key": "s", "label": "S"})
    r = client.post("/api/addons", json={"key": "s", "label": "S2"})
    assert r.status_code == 409


def test_enable_makes_active(client, session):
    make_user(session, is_admin=True)
    login(client)
    aid = client.post("/api/addons", json={"key": "s", "label": "S"}).json()["id"]
    r = client.patch(f"/api/addons/{aid}", json={"enabled": True})
    assert r.status_code == 200, r.text
    assert r.json()["active"] is True


def test_delete_addon(client, session):
    make_user(session, is_admin=True)
    login(client)
    aid = client.post("/api/addons", json={"key": "s", "label": "S"}).json()["id"]
    assert client.delete(f"/api/addons/{aid}").status_code == 204
    assert client.get("/api/addons").json() == []
