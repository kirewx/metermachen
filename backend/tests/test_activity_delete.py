from datetime import date, datetime, timezone

from sqlmodel import select

from app.models import Activity, ActivityTrack, FeedEvent, StravaConnection, StravaIgnored
from app.services import feed
from app.services.activity_delete import delete_activity
from tests.conftest import login, make_category, make_user


def _make_activity(session, user, cat, *, source="manual", external_id=None, date_=date(2026, 7, 1)):
    act = Activity(
        user_id=user.id, category_id=cat.id, date=date_, distance_km=5.0,
        source=source, external_id=external_id,
    )
    session.add(act)
    session.commit()
    session.refresh(act)
    return act


def _make_track(session, act):
    track = ActivityTrack(
        activity_id=act.id,
        start_utc=datetime(2026, 7, 1, 7, 0, tzinfo=timezone.utc),
        elapsed_s=1800,
    )
    session.add(track)
    session.commit()
    return track


def test_delete_strava_activity_writes_ignore_entry(session):
    user = make_user(session)
    cat = make_category(session)
    act = _make_activity(session, user, cat, source="strava", external_id="555")
    _make_track(session, act)

    delete_activity(session, act, ignore_strava=True)

    assert session.exec(select(Activity)).all() == []
    assert session.exec(select(ActivityTrack)).all() == []
    entries = session.exec(select(StravaIgnored)).all()
    assert len(entries) == 1
    assert entries[0].user_id == user.id
    assert entries[0].external_id == "555"


def test_delete_manual_activity_writes_no_ignore_entry(session):
    user = make_user(session)
    cat = make_category(session)
    act = _make_activity(session, user, cat, source="manual")

    delete_activity(session, act, ignore_strava=True)

    assert session.exec(select(Activity)).all() == []
    assert session.exec(select(StravaIgnored)).all() == []


def test_delete_twice_same_external_id_keeps_one_ignore_entry(session):
    user = make_user(session)
    cat = make_category(session)

    act1 = _make_activity(session, user, cat, source="strava", external_id="555")
    delete_activity(session, act1, ignore_strava=True)

    act2 = _make_activity(session, user, cat, source="strava", external_id="555")
    delete_activity(session, act2, ignore_strava=True)

    entries = session.exec(select(StravaIgnored)).all()
    assert len(entries) == 1
    assert entries[0].user_id == user.id
    assert entries[0].external_id == "555"


def _enable_strava(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "STRAVA_CLIENT_ID", "cid")
    monkeypatch.setattr(config, "STRAVA_CLIENT_SECRET", "sec")
    monkeypatch.setattr(config, "STRAVA_WEBHOOK_VERIFY_TOKEN", "verifytok")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://meter.example.com")


def test_disconnect_writes_no_ignore_entry(client, session, monkeypatch):
    _enable_strava(monkeypatch)
    user = make_user(session)
    cat = make_category(session, strava_sport_types='["Run"]')
    session.add(StravaConnection(user_id=user.id, athlete_id=42,
                                 access_token="a", refresh_token="r", expires_at=999))
    act = Activity(user_id=user.id, category_id=cat.id, date=date(2026, 7, 1),
                   distance_km=5.0, source="strava", external_id="1")
    session.add(act)
    session.commit()
    session.refresh(act)
    _make_track(session, act)
    feed.activity_event(session, act)

    login(client)
    assert client.delete("/api/strava/disconnect").status_code == 204

    assert session.exec(select(StravaIgnored)).all() == []
    assert session.exec(select(ActivityTrack)).all() == []
    assert session.exec(
        select(FeedEvent).where(FeedEvent.activity_id == act.id)
    ).all() == []
    assert session.exec(select(Activity)).all() == []
