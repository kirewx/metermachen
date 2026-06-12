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
