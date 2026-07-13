from datetime import date, timedelta

from app.models import Activity
from app.services import bet_metrics
from tests.conftest import make_category, make_user


def test_scaled_km_in_period_ignores_user_factor(session):
    user = make_user(session)
    user.km_factor = 3.0
    cat = make_category(session, factor=2.0)
    session.add(
        Activity(user_id=user.id, category_id=cat.id, date=date.today(), distance_km=10)
    )
    session.add(
        Activity(
            user_id=user.id,
            category_id=cat.id,
            date=date.today() - timedelta(days=30),
            distance_km=99,
        )
    )
    session.commit()
    km = bet_metrics.scaled_km(
        session, user.id, date.today() - timedelta(days=1), date.today()
    )
    assert km == 20.0  # 10 * 2.0, User-Faktor ignoriert, alte Aktivität raus


def test_group_scaled_km(session):
    a = make_user(session)
    b = make_user(session, username="lisa")
    cat = make_category(session, factor=1.0)
    session.add(Activity(user_id=a.id, category_id=cat.id, date=date.today(), distance_km=3))
    session.add(Activity(user_id=b.id, category_id=cat.id, date=date.today(), distance_km=4))
    session.commit()
    assert bet_metrics.group_scaled_km(
        session, [a.id, b.id], date.today(), date.today()
    ) == 7.0


def test_longest_streak(session):
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    d0 = date.today() - timedelta(days=6)
    for offset, km in [(0, 2), (1, 1), (2, 0.4), (3, 5), (4, 5), (5, 5)]:
        if km:
            session.add(
                Activity(
                    user_id=user.id,
                    category_id=cat.id,
                    date=d0 + timedelta(days=offset),
                    distance_km=km,
                )
            )
    session.commit()
    # Tag 2 hat nur 0.4 km (< 1 roh) -> unterbricht; längste Serie = Tage 3-5
    assert bet_metrics.longest_streak(session, user.id, d0, date.today()) == 3
