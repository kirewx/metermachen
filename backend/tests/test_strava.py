from sqlmodel import select

from app import config
from app.models import Category, StravaConnection


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
