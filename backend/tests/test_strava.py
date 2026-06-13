from app import config


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
