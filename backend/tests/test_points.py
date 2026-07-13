from datetime import date, timedelta

from app.models import Activity, Season
from app.services import points
from tests.conftest import make_category, make_user


def _season(session, start_offset=-10):
    s = Season(
        year=date.today().year,
        goal_km=1000,
        milestones_json="[]",
        start_date=date.today() + timedelta(days=start_offset),
    )
    session.add(s)
    session.commit()
    session.refresh(s)
    return s


def test_start_credit_once(session):
    user = make_user(session)
    assert points.balance(session, user.id) == 0
    points.ensure_start_credit(session, user.id)
    points.ensure_start_credit(session, user.id)  # idempotent
    assert points.balance(session, user.id) == 100


def test_income_one_point_per_5_scaled_km_since_start(session):
    user = make_user(session)
    user.km_factor = 2.0
    cat = make_category(session, factor=1.0)
    season = _season(session)
    # 12 km roh * 1.0 * 2.0 = 24 gewertete km -> floor(24/5) = 4 Punkte
    session.add(
        Activity(user_id=user.id, category_id=cat.id, date=date.today(), distance_km=12)
    )
    # Warm-up-Aktivität zählt nicht:
    session.add(
        Activity(
            user_id=user.id,
            category_id=cat.id,
            date=season.start_date - timedelta(days=1),
            distance_km=100,
        )
    )
    session.commit()
    points.ensure_income(session, user.id)
    points.ensure_income(session, user.id)  # idempotent
    assert points.balance(session, user.id) == 4


def test_income_zero_before_challenge_start(session):
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    _season(session, start_offset=+5)  # Challenge noch nicht gestartet
    session.add(
        Activity(user_id=user.id, category_id=cat.id, date=date.today(), distance_km=50)
    )
    session.commit()
    points.ensure_income(session, user.id)
    assert points.balance(session, user.id) == 0
