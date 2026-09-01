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


HIDDEN_KEYS = {
    "kletterkoenig", "hattrick", "wochenkoenig", "psychopath", "langstreckenguru",
    "kurzstreckenprofi", "dauerbrenner_bronze", "dauerbrenner_silber", "dauerbrenner_gold",
}


def test_hidden_admin_lists_every_definition_with_unlockers(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    tom = make_user(session, username="tom")
    tom.is_active = False
    session.add(tom)
    session.add(AchievementUnlock(user_id=lisa.id, key="hattrick"))
    session.add(AchievementUnlock(user_id=tom.id, key="hattrick"))  # inactive: not listed
    session.commit()
    login(client, username="chef")

    r = client.get("/api/achievements/hidden")
    assert r.status_code == 200
    body = {h["key"]: h for h in r.json()}
    assert set(body) == HIDDEN_KEYS
    assert body["hattrick"]["title"] == "Hattrick"
    assert body["hattrick"]["emoji"] == "\U0001F3A9"
    assert [u["display_name"] for u in body["hattrick"]["unlocks"]] == ["Lisa"]
    assert body["hattrick"]["unlocks"][0]["unlocked_at"]
    assert body["kletterkoenig"]["unlocks"] == []


def test_hidden_admin_forbidden_for_members(client, session):
    make_user(session)
    login(client)
    assert client.get("/api/achievements/hidden").status_code == 403
