from app.services import notify


def test_notify_is_noop_and_returns_none():
    assert notify.notify(1, "together_suggested", {"foo": "bar"}) is None
    assert notify.notify(2, "together_tagged", {}) is None
    assert notify.notify(3, "together_auto", {"km": 5.0}) is None
