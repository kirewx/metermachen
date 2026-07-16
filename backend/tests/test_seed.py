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


def test_seed_registers_sidebets_addon_scheduled(session):
    from datetime import datetime, timezone

    from app.deps import addon_active

    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "sidebets")).one()
    # Vorkonfiguriert: eingeschaltet, aber per Fenster auf den Challenge-Start terminiert.
    assert addon.enabled is True
    assert addon.active_from is not None
    # Vor dem 20.07.2026 noch nicht aktiv, danach schon.
    assert addon_active(addon, datetime(2026, 7, 1, tzinfo=timezone.utc)) is False
    assert addon_active(addon, datetime(2026, 7, 20, 12, tzinfo=timezone.utc)) is True


def test_seed_does_not_override_existing_addon(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "sidebets")).one()
    addon.enabled = False  # Admin schaltet bewusst wieder aus
    session.add(addon)
    session.commit()
    # Erneutes Seeding darf die Admin-Entscheidung nicht zurücksetzen.
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "sidebets")).one()
    assert addon.enabled is False


def test_seed_is_idempotent(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    assert len(session.exec(select(User)).all()) == 1
    assert len(session.exec(select(Category)).all()) == 7
    assert len(session.exec(select(Season)).all()) == 1
    assert len(session.exec(select(AddOn)).all()) == 2


def test_seed_registers_blackboard_addon_scheduled(session):
    from datetime import datetime, timezone

    from app.deps import addon_active

    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "blackboard")).one()
    # Gleiches Fenster wie sidebets: an, aber erst ab Challenge-Start aktiv.
    assert addon.enabled is True
    assert addon_active(addon, datetime(2026, 7, 1, tzinfo=timezone.utc)) is False
    assert addon_active(addon, datetime(2026, 7, 20, 12, tzinfo=timezone.utc)) is True


def test_seed_legt_keine_zweite_season_an(session):
    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    # Jahreswechsel: Seed mit neuem Jahr darf KEINE Season 2027 anlegen,
    # solange die 2026er-Saison existiert (läuft bis Stuttgartlauf 2027).
    seed_all(session, admin_user="chef", admin_password="geheim", year=2027)
    seasons = session.exec(select(Season)).all()
    assert [s.year for s in seasons] == [2026]
