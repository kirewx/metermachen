import json
from datetime import date

from sqlmodel import select

from app.models import Activity, FeedEvent, Season
from app.services import feed
from tests.conftest import make_category, make_user


def _setup_saison(session, start=date(2026, 7, 20)):
    session.add(Season(year=2026, goal_km=1000.0, start_date=start,
                       end_date=date(2027, 5, 16),
                       milestones_json=json.dumps([{"km": 50.0, "label": "Ärmelkanal", "icon": "fahne"}])))
    session.commit()


def _act(session, user, cat, km, tag=date(2026, 8, 3)):
    act = Activity(user_id=user.id, category_id=cat.id, date=tag, distance_km=km)
    session.add(act)
    session.commit()
    session.refresh(act)
    return act


def test_activity_event_mit_kategorie_und_mm(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=4.0)
    act = _act(session, user, cat, 10.0)
    feed.activity_event(session, act)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "activity")).one()
    p = json.loads(ev.payload_json)
    assert ev.user_id == user.id and ev.activity_id == act.id
    assert p["mm"] == 40.0 and p["category"]["name"] == cat.name


def test_rank_events_nur_top5_aufsteiger(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    before = [b.id, a.id]
    after = [a.id, b.id]
    feed.rank_events(session, before, after)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "rank_change")).one()
    p = json.loads(ev.payload_json)
    assert ev.user_id == a.id
    assert p["ueberholt_user_id"] == b.id and p["neuer_rang"] == 1


def test_rank_events_keine_events_ohne_aenderung(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    feed.rank_events(session, [a.id, b.id], [a.id, b.id])
    assert session.exec(select(FeedEvent)).all() == []


def test_milestone_event_bei_ueberschreitung(session):
    _setup_saison(session)
    user = make_user(session)
    feed.milestone_events(session, user.id, total_before=45.0, total_after=52.0)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "milestone")).one()
    assert json.loads(ev.payload_json)["label"] == "Ärmelkanal"


def test_milestone_kein_event_ohne_ueberschreitung(session):
    _setup_saison(session)
    user = make_user(session)
    feed.milestone_events(session, user.id, total_before=52.0, total_after=60.0)
    assert session.exec(select(FeedEvent)).all() == []


def test_challenge_order_nach_mm_mit_handicap(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    cat = make_category(session, factor=1.0)
    _act(session, a, cat, 10.0)
    _act(session, b, cat, 20.0)
    assert feed.challenge_order(session) == [b.id, a.id]


def test_remove_activity_events(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session)
    act = _act(session, user, cat, 10.0)
    feed.activity_event(session, act)
    feed.remove_activity_events(session, act.id)
    assert session.exec(select(FeedEvent)).all() == []


def test_unlock_erzeugt_achievement_event(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    for _ in range(3):  # Hattrick: 3 Aktivitäten an einem Tag
        _act(session, user, cat, 2.0)
    from app.services.achievements import check_unlocks
    check_unlocks(session, user.id)
    evs = session.exec(select(FeedEvent).where(FeedEvent.type == "achievement")).all()
    keys = [json.loads(e.payload_json)["key"] for e in evs]
    assert "hattrick" in keys
    hat = next(json.loads(e.payload_json) for e in evs
               if json.loads(e.payload_json)["key"] == "hattrick")
    assert hat["title"] == "Hattrick" and hat["emoji"] == "🎩"
