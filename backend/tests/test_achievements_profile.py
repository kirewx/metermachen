"""Profile-facing achievement endpoints: another member's unlocked list and
the admin overview of hidden achievements."""

from datetime import date

from app.models import AchievementUnlock, Activity
from tests.conftest import login, make_category, make_user


def add_activity(session, user, cat, km, d=date(2026, 7, 12)):
    session.add(Activity(user_id=user.id, category_id=cat.id, date=d, distance_km=km))
    session.commit()


def test_user_achievements_requires_login(client):
    assert client.get("/api/achievements/user/1").status_code == 401


def test_user_achievements_returns_only_unlocked(client, session):
    make_user(session)  # erik, the requester
    lisa = make_user(session, username="lisa")
    cat = make_category(session, name="Laufen", icon="laufen")
    add_activity(session, lisa, cat, 5.0)
    session.add(AchievementUnlock(user_id=lisa.id, key="hattrick"))
    session.commit()
    login(client)

    r = client.get(f"/api/achievements/user/{lisa.id}")
    assert r.status_code == 200
    body = {a["key"]: a for a in r.json()}
    assert all(a["achieved"] for a in body.values())
    assert "startschuss" in body  # computed live from activities
    assert body["hattrick"]["title"] == "Hattrick"  # hidden but unlocked: revealed
    assert body["hattrick"]["hidden"] is True
    assert "kletterkoenig" not in body  # hidden and locked: absent
    assert "ironman" not in body  # visible but not achieved: absent


def test_user_achievements_404_for_unknown_or_inactive(client, session):
    make_user(session)
    tom = make_user(session, username="tom")
    tom.is_active = False
    session.add(tom)
    session.commit()
    login(client)
    assert client.get("/api/achievements/user/999").status_code == 404
    assert client.get(f"/api/achievements/user/{tom.id}").status_code == 404
