import pytest
from sqlmodel import select

from app import config
from app.models import Activity, Category, StravaConnection
from app.services import strava


def test_strava_enabled_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "")
    assert config.strava_enabled() is False


def test_strava_enabled_true_when_fully_configured(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "123")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "secret")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "verifytok")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://meter.example.com")
    assert config.strava_enabled() is True


def test_strava_connection_roundtrip(session):
    conn = StravaConnection(
        user_id=1, athlete_id=999, access_token="a", refresh_token="r", expires_at=123456
    )
    session.add(conn)
    session.commit()
    got = session.exec(select(StravaConnection).where(StravaConnection.athlete_id == 999)).first()
    assert got is not None
    assert got.expires_at == 123456


def test_category_has_strava_sport_types_default(session):
    cat = Category(name="Laufen", factor=4.0, color="#e74c3c", icon="laufen")
    session.add(cat)
    session.commit()
    session.refresh(cat)
    assert cat.strava_sport_types == "[]"


from tests.conftest import login, make_category, make_user  # noqa: E402


def _setup_conn(session, athlete_id=999, expires_at=9999999999):
    user = make_user(session)
    conn = StravaConnection(
        user_id=user.id, athlete_id=athlete_id,
        access_token="tok", refresh_token="ref", expires_at=expires_at,
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return user, conn


def _payload(athlete_id=999, object_id=555, aspect="create"):
    return {"object_type": "activity", "aspect_type": aspect,
            "owner_id": athlete_id, "object_id": object_id}


def test_category_for_sport_matches_active_only(session):
    make_category(session, name="Laufen", strava_sport_types='["Run","TrailRun"]')
    make_category(session, name="Inaktiv", strava_sport_types='["Ride"]', is_active=False)
    assert strava.category_for_sport(session, "Run").name == "Laufen"
    assert strava.category_for_sport(session, "TrailRun").name == "Laufen"
    assert strava.category_for_sport(session, "Ride") is None
    assert strava.category_for_sport(session, "Swim") is None


def test_valid_access_token_refreshes_when_expired(session, monkeypatch):
    _user, conn = _setup_conn(session, expires_at=0)
    monkeypatch.setattr(strava, "refresh_tokens", lambda rt: {
        "access_token": "neu", "refresh_token": "neu-ref", "expires_at": 8888888888,
    })
    token = strava.valid_access_token(session, conn)
    assert token == "neu"
    assert conn.refresh_token == "neu-ref"
    assert conn.expires_at == 8888888888


def test_valid_access_token_keeps_valid_token(session, monkeypatch):
    _user, conn = _setup_conn(session, expires_at=9999999999)
    monkeypatch.setattr(strava, "refresh_tokens", lambda rt: (_ for _ in ()).throw(AssertionError("darf nicht refreshen")))
    assert strava.valid_access_token(session, conn) == "tok"


def test_handle_webhook_event_imports_activity(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Morgenlauf",
    })
    strava.handle_webhook_event(session, _payload())
    acts = session.exec(select(Activity)).all()
    assert len(acts) == 1
    assert acts[0].source == "strava"
    assert acts[0].external_id == "555"
    assert acts[0].distance_km == 5.0
    assert acts[0].duration_min == 30
    assert acts[0].note == "Morgenlauf"
    assert acts[0].date.isoformat() == "2026-03-01"


def test_handle_webhook_event_dedup(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Morgenlauf",
    })
    strava.handle_webhook_event(session, _payload())
    strava.handle_webhook_event(session, _payload())
    assert len(session.exec(select(Activity)).all()) == 1


def test_handle_webhook_event_skips_unmapped_sport(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Swim", "distance": 2000.0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Schwimmen",
    })
    strava.handle_webhook_event(session, _payload())
    assert session.exec(select(Activity)).all() == []


def test_handle_webhook_event_skips_zero_distance(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Kraft", strava_sport_types='["WeightTraining"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "WeightTraining", "distance": 0, "moving_time": 1800,
        "start_date_local": "2026-03-01T07:00:00Z", "name": "Gym",
    })
    strava.handle_webhook_event(session, _payload())
    assert session.exec(select(Activity)).all() == []


def test_handle_webhook_event_unknown_owner(session, monkeypatch):
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    called = {"fetch": False}
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: called.__setitem__("fetch", True))
    strava.handle_webhook_event(session, _payload(athlete_id=12345))
    assert called["fetch"] is False
    assert session.exec(select(Activity)).all() == []


def test_handle_webhook_event_ignores_non_create(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {"sport_type": "Run"})
    strava.handle_webhook_event(session, _payload(aspect="update"))
    assert session.exec(select(Activity)).all() == []


def test_import_activity_inserts_and_is_idempotent(session):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    data = {"id": 999, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
            "start_date_local": "2026-03-01T07:00:00Z", "name": "Lauf"}
    assert strava.import_activity(session, conn, data) is True
    assert strava.import_activity(session, conn, data) is False  # Dublette
    acts = session.exec(select(Activity)).all()
    assert len(acts) == 1
    assert acts[0].external_id == "999"
    assert acts[0].distance_km == 5.0
    assert acts[0].duration_min == 30
    assert acts[0].source == "strava"


def test_import_activity_skips_unmapped_and_zero(session):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    assert strava.import_activity(session, conn,
        {"id": 1, "sport_type": "Swim", "distance": 2000.0, "moving_time": 0}) is False  # ungemappt
    assert strava.import_activity(session, conn,
        {"id": 2, "sport_type": "Run", "distance": 0, "moving_time": 0}) is False  # distanz 0
    assert session.exec(select(Activity)).all() == []


def _enable_strava(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "sec")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "verifytok")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://meter.example.com")


def test_status_disabled_when_unconfigured(client, session, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "")
    make_user(session)
    login(client)
    r = client.get("/api/strava/status")
    assert r.status_code == 200
    assert r.json() == {"enabled": False, "connected": False}


def test_status_connected(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=42,
                                 access_token="a", refresh_token="r", expires_at=999))
    session.commit()
    login(client)
    r = client.get("/api/strava/status")
    assert r.json() == {
        "enabled": True, "connected": True, "athlete_id": 42,
        "backfill": {"state": "idle", "total": 0, "done": 0},
    }


def test_status_reports_running_backfill(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(
        user_id=user.id, athlete_id=42, access_token="a", refresh_token="r",
        expires_at=999, backfill_state="running", backfill_total=52, backfill_done=10))
    session.commit()
    login(client)
    r = client.get("/api/strava/status")
    assert r.json()["backfill"] == {"state": "running", "total": 52, "done": 10}


def test_webhook_verify_echoes_challenge(client, monkeypatch):
    _enable_strava(monkeypatch)
    r = client.get("/api/strava/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "verifytok", "hub.challenge": "abc123",
    })
    assert r.status_code == 200
    assert r.json() == {"hub.challenge": "abc123"}


def test_webhook_verify_rejects_wrong_token(client, monkeypatch):
    _enable_strava(monkeypatch)
    r = client.get("/api/strava/webhook", params={
        "hub.mode": "subscribe", "hub.verify_token": "falsch", "hub.challenge": "abc123",
    })
    assert r.status_code == 403


def test_webhook_post_schedules_processing(client, monkeypatch):
    from app.routers import strava_router
    seen = {}
    monkeypatch.setattr(strava_router, "process_event", lambda payload: seen.update(payload))
    r = client.post("/api/strava/webhook", json={"object_type": "activity", "aspect_type": "create"})
    assert r.status_code == 200
    assert seen.get("object_type") == "activity"


def test_connect_redirects_to_strava(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    make_user(session)
    login(client)
    r = client.get("/api/strava/connect", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].startswith("https://www.strava.com/oauth/authorize")


def test_callback_stores_connection(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    from app.routers import strava_router
    user = make_user(session)
    login(client)
    state = strava_router._state_serializer.dumps(user.id)
    monkeypatch.setattr(strava_router.strava, "exchange_code", lambda code: {
        "access_token": "AT", "refresh_token": "RT", "expires_at": 8888888888,
        "athlete": {"id": 77},
    })
    monkeypatch.setattr(strava_router.strava, "backfill_current_year", lambda uid: None)
    r = client.get("/api/strava/callback", params={"code": "xyz", "state": state},
                   follow_redirects=False)
    assert r.status_code in (302, 307)
    conn = session.exec(select(StravaConnection).where(StravaConnection.user_id == user.id)).first()
    assert conn is not None
    assert conn.athlete_id == 77
    assert conn.access_token == "AT"


def test_disconnect_removes_connection(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=42,
                                 access_token="a", refresh_token="r", expires_at=999))
    session.commit()
    login(client)
    assert client.delete("/api/strava/disconnect").status_code == 204
    assert session.exec(select(StravaConnection)).all() == []


def test_handle_webhook_event_dedup_skips_fetch(session, monkeypatch):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    # Vorab bereits importiert (gleiche external_id wie _payload default object_id=555)
    session.add(Activity(user_id=user.id, category_id=1, date=__import__("datetime").date(2026, 3, 1),
                         distance_km=5.0, source="strava", external_id="555"))
    session.commit()
    called = {"fetch": False}
    monkeypatch.setattr(strava, "fetch_activity",
                        lambda tok, aid: called.__setitem__("fetch", True) or {})
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    strava.handle_webhook_event(session, _payload())
    assert called["fetch"] is False
    assert len(session.exec(select(Activity)).all()) == 1


@pytest.fixture
def bind_engine(session, monkeypatch):
    bind = session.get_bind()
    from app import db
    from app.services import strava as strava_svc
    monkeypatch.setattr(db, "engine", bind)
    monkeypatch.setattr(strava_svc, "engine", bind)
    return bind


def test_backfill_imports_mapped_activities_and_tracks_progress(session, monkeypatch, bind_engine):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    make_category(session, name="Radfahren", strava_sport_types='["Ride"]')
    activities = [
        {"id": 1, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
         "start_date_local": "2026-02-01T07:00:00Z", "name": "Lauf"},
        {"id": 2, "sport_type": "Ride", "distance": 20000.0, "moving_time": 3600,
         "start_date_local": "2026-02-02T07:00:00Z", "name": "Tour"},
        {"id": 3, "sport_type": "Swim", "distance": 1000.0, "moving_time": 1800,
         "start_date_local": "2026-02-03T07:00:00Z", "name": "Bad"},  # ungemappt
    ]
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_athlete_activities", lambda tok, after: activities)

    strava.backfill_current_year(user.id)

    fresh = session.get(StravaConnection, conn.id)
    session.refresh(fresh)
    assert fresh.backfill_state == "done"
    assert fresh.backfill_total == 2   # nur Run + Ride sind importierbar
    assert fresh.backfill_done == 2
    acts = session.exec(select(Activity).where(Activity.source == "strava")).all()
    assert {a.external_id for a in acts} == {"1", "2"}


def test_backfill_is_idempotent(session, monkeypatch, bind_engine):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    activities = [{"id": 1, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
                   "start_date_local": "2026-02-01T07:00:00Z", "name": "Lauf"}]
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_athlete_activities", lambda tok, after: activities)

    strava.backfill_current_year(user.id)
    strava.backfill_current_year(user.id)

    assert len(session.exec(select(Activity).where(Activity.source == "strava")).all()) == 1


def test_backfill_sets_error_on_http_failure(session, monkeypatch, bind_engine):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    def boom(tok, after):
        raise RuntimeError("strava down")
    monkeypatch.setattr(strava, "fetch_athlete_activities", boom)

    strava.backfill_current_year(user.id)

    fresh = session.get(StravaConnection, conn.id)
    session.refresh(fresh)
    assert fresh.backfill_state == "error"


def test_backfill_stops_when_connection_removed_midway(session, monkeypatch, bind_engine):
    user, conn = _setup_conn(session)
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    activities = [
        {"id": 1, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
         "start_date_local": "2026-02-01T07:00:00Z", "name": "A"},
        {"id": 2, "sport_type": "Run", "distance": 6000.0, "moving_time": 1800,
         "start_date_local": "2026-02-02T07:00:00Z", "name": "B"},
    ]
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_athlete_activities", lambda tok, after: activities)
    calls = {"n": 0}
    def fake_import(s, c, data):
        calls["n"] += 1
        # Beim ersten Import trennt der Nutzer die Verbindung
        s.delete(s.get(StravaConnection, c.id))
        s.commit()
        return False
    monkeypatch.setattr(strava, "import_activity", fake_import)

    strava.backfill_current_year(user.id)

    # Nach Wegfall der Connection bricht die Schleife ab -> nur 1 Aufruf
    assert calls["n"] == 1
    assert session.exec(select(Activity).where(Activity.source == "strava")).all() == []


def test_backfill_noop_without_connection(session, monkeypatch, bind_engine):
    make_category(session, name="Joggen", strava_sport_types='["Run"]')
    called = {"list": False}
    monkeypatch.setattr(strava, "fetch_athlete_activities",
                        lambda tok, after: called.__setitem__("list", True) or [])
    strava.backfill_current_year(user_id=4242)  # kein User/keine Connection
    assert called["list"] is False


def test_callback_triggers_backfill_on_fresh_connect(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    from app.routers import strava_router
    user = make_user(session)
    login(client)
    state = strava_router._state_serializer.dumps(user.id)
    monkeypatch.setattr(strava_router.strava, "exchange_code", lambda code: {
        "access_token": "AT", "refresh_token": "RT", "expires_at": 8888888888,
        "athlete": {"id": 77},
    })
    triggered = {"user_id": None}
    monkeypatch.setattr(strava_router.strava, "backfill_current_year",
                        lambda uid: triggered.__setitem__("user_id", uid))
    r = client.get("/api/strava/callback", params={"code": "xyz", "state": state},
                   follow_redirects=False)
    assert r.status_code in (302, 307)
    assert triggered["user_id"] == user.id


def test_callback_no_backfill_on_existing_connection(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    from app.routers import strava_router
    user = make_user(session)
    session.add(StravaConnection(user_id=user.id, athlete_id=77,
                                 access_token="old", refresh_token="old", expires_at=1))
    session.commit()
    login(client)
    state = strava_router._state_serializer.dumps(user.id)
    monkeypatch.setattr(strava_router.strava, "exchange_code", lambda code: {
        "access_token": "AT", "refresh_token": "RT", "expires_at": 8888888888,
        "athlete": {"id": 77},
    })
    triggered = {"called": False}
    monkeypatch.setattr(strava_router.strava, "backfill_current_year",
                        lambda uid: triggered.__setitem__("called", True))
    client.get("/api/strava/callback", params={"code": "xyz", "state": state},
               follow_redirects=False)
    assert triggered["called"] is False


def test_strava_import_since_parsing(monkeypatch):
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "")
    assert config.strava_import_since() is None
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "2026-07-11")
    assert config.strava_import_since().isoformat() == "2026-07-11"


def test_import_activity_respects_since_cutoff(session, monkeypatch):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "2026-07-11")
    alt = {"id": 1, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
           "start_date_local": "2026-07-10T07:00:00Z", "name": "Zu alt"}
    neu = {"id": 2, "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
           "start_date_local": "2026-07-11T07:00:00Z", "name": "Am Stichtag"}
    assert strava.import_activity(session, conn, alt) is False
    assert strava.import_activity(session, conn, neu) is True
    acts = session.exec(select(Activity)).all()
    assert len(acts) == 1
    assert acts[0].note == "Am Stichtag"


def test_webhook_event_respects_since_cutoff(session, monkeypatch):
    _user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "2026-07-11")
    monkeypatch.setattr(strava, "valid_access_token", lambda s, c: "tok")
    monkeypatch.setattr(strava, "fetch_activity", lambda tok, aid: {
        "sport_type": "Run", "distance": 5000.0, "moving_time": 1800,
        "start_date_local": "2026-01-05T07:00:00Z", "name": "Nachtrag von früher",
    })
    strava.handle_webhook_event(session, _payload())
    assert session.exec(select(Activity)).all() == []
