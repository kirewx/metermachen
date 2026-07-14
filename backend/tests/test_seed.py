from sqlmodel import select

from app.models import AddOn, Category, Season, User
from app.seed import seed_all


def test_seed_creates_admin_categories_season(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    admin = session.exec(select(User)).one()
    assert admin.username == "chef"
    assert admin.is_admin is True
    cats = session.exec(select(Category)).all()
    assert {c.name for c in cats} == {
        "Joggen",
        "Laufen",
        "Spazieren",
        "Wandern",
        "Schwimmen",
        "Radfahren",
        "Tanzen",
    }
    assert {c.name: c.factor for c in cats}["Joggen"] == 4.0
    assert {c.name: c.factor for c in cats}["Radfahren"] == 1.0
    season = session.exec(select(Season)).one()
    assert season.year == 2026
    assert season.goal_km == 1000.0


def test_seed_registers_sidebets_addon_disabled(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "sidebets")).one()
    assert addon.enabled is False  # Default AUS — Rick schaltet selbst scharf


def test_seed_does_not_override_existing_addon(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "sidebets")).one()
    addon.enabled = True
    session.add(addon)
    session.commit()
    # Erneutes Seeding darf einen scharf geschalteten Toggle nicht zurücksetzen.
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "sidebets")).one()
    assert addon.enabled is True


def test_seed_is_idempotent(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    assert len(session.exec(select(User)).all()) == 1
    assert len(session.exec(select(Category)).all()) == 7
    assert len(session.exec(select(Season)).all()) == 1
    assert len(session.exec(select(AddOn)).all()) == 1
