from datetime import date

from app.models import Activity, Challenge
from tests.conftest import make_category, make_user


def make_challenge(session, **kw) -> Challenge:
    daten = dict(
        title="Test",
        creator_id=1,
        mode="ziel",
        target=100.0,
        metric="mm",
        join_mode="auto",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        status="laufend",
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def add_activity(session, user_id, cat_id, tag, km):
    session.add(
        Activity(user_id=user_id, category_id=cat_id, date=tag, distance_km=km)
    )
    session.commit()


def test_mm_summiert_km_mal_kategoriefaktor(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session)
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 6), 5.0)
    assert challenges.metric_value(session, user.id, ch) == 60.0


def test_mm_ignoriert_aktivitaeten_ausserhalb_des_zeitraums(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session)
    add_activity(session, user.id, lauf.id, date(2026, 7, 31), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 9, 1), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 1), 1.0)
    assert challenges.metric_value(session, user.id, ch) == 4.0


def test_mm_mit_kategoriefilter(session):
    import json

    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    rad = make_category(session, name="Rad", factor=1.0)
    ch = make_challenge(session, category_ids_json=json.dumps([lauf.id]))
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, user.id, rad.id, date(2026, 8, 5), 50.0)
    assert challenges.metric_value(session, user.id, ch) == 40.0


def test_mm_ignoriert_km_factor(session):
    from app.services import challenges

    user = make_user(session)
    user.km_factor = 2.0
    session.add(user)
    session.commit()
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session)
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    # Das Admin-Handicap gilt nur im Saison-Ranking, nicht in Challenges.
    assert challenges.metric_value(session, user.id, ch) == 40.0
