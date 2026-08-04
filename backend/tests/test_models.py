from datetime import date

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Activity, Category, Season, User


def make_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_roundtrip_all_tables():
    with make_session() as s:
        user = User(username="erik", password_hash="x", display_name="Erik")
        cat = Category(name="Joggen", factor=4.0, color="#e74c3c", icon="laufen")
        s.add(user)
        s.add(cat)
        s.commit()
        s.add(
            Activity(
                user_id=user.id,
                category_id=cat.id,
                date=date(2026, 3, 1),
                distance_km=5.0,
            )
        )
        s.add(Season(year=2026, goal_km=1000.0))
        s.commit()

        act = s.exec(select(Activity)).one()
        assert act.distance_km == 5.0
        assert act.source == "manual"
        assert act.updated_at is None
        season = s.exec(select(Season)).one()
        assert season.milestones_json == "[]"
        assert user.avatar == "icon:laufen"
        assert user.is_admin is False
        assert cat.is_active is True


def test_achievement_unlock_unique_pro_user_und_key(session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import AchievementUnlock

    session.add(AchievementUnlock(user_id=1, key="stufe_rad_gold"))
    session.commit()
    session.add(AchievementUnlock(user_id=1, key="stufe_rad_gold"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    # gleiche Achievement-Keys für andere Nutzer sind ok
    session.add(AchievementUnlock(user_id=2, key="stufe_rad_gold"))
    session.commit()


def test_feed_reaction_unique_pro_user_und_emoji(session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import FeedEvent, FeedReaction

    ev = FeedEvent(season_year=2026, type="activity", user_id=1)
    session.add(ev)
    session.commit()
    session.add(FeedReaction(event_id=ev.id, user_id=1, emoji="🔥"))
    session.commit()
    session.add(FeedReaction(event_id=ev.id, user_id=1, emoji="🔥"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_challenge_defaults(session):
    from datetime import date

    from app.models import Challenge

    ch = Challenge(
        title="August bis Stuttgartlauf",
        creator_id=1,
        mode="ziel",
        target=300.0,
        metric="mm",
        join_mode="auto",
        period_start=date(2026, 8, 4),
        period_end=date(2026, 8, 31),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    assert ch.status == "geplant"
    assert ch.category_ids_json == "[]"
    assert ch.streak_min_mm == 5.0
    assert ch.top_n == 1
    assert ch.result_json == "{}"
    assert ch.prize is None
    assert ch.resolved_at is None


def test_challenge_participant_unique(session):
    from datetime import date

    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import Challenge, ChallengeParticipant

    ch = Challenge(
        title="X", creator_id=1, mode="ziel", target=1.0, metric="mm",
        join_mode="opt_in", period_start=date(2026, 8, 1), period_end=date(2026, 8, 2),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=7))
    session.commit()
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=7))
    with pytest.raises(IntegrityError):
        session.commit()
