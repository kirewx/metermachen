import json

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app.db import migrate

OLD_SCHEMA = """
CREATE TABLE user (
    id INTEGER PRIMARY KEY, username VARCHAR, password_hash VARCHAR,
    display_name VARCHAR, avatar_emoji VARCHAR, is_admin BOOLEAN, created_at DATETIME
);
CREATE TABLE category (
    id INTEGER PRIMARY KEY, name VARCHAR, factor FLOAT, color VARCHAR,
    icon_emoji VARCHAR, is_active BOOLEAN
);
CREATE TABLE season (
    id INTEGER PRIMARY KEY, year INTEGER, goal_km FLOAT,
    milestones_json VARCHAR, map_image VARCHAR
);
"""


def make_old_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in OLD_SCHEMA.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
        conn.execute(
            text(
                "INSERT INTO user (username, password_hash, display_name, avatar_emoji, is_admin)"
                " VALUES ('erik', 'x', 'Erik', '🏃', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO category (name, factor, color, icon_emoji, is_active)"
                " VALUES ('Radfahren', 1.0, '#3498db', '🚴', 1), ('Kurios', 2.0, '#000000', '🦖', 1)"
            )
        )
        conn.execute(
            text("INSERT INTO season (year, goal_km, milestones_json) VALUES (2026, 1000, :m)"),
            {"m": json.dumps([{"km": 500, "label": "Halbzeit", "emoji": "🏔"}])},
        )
    return engine


def test_migration_benennt_um_und_mappt():
    engine = make_old_engine()
    migrate(engine)
    with engine.connect() as conn:
        user_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(user)"))]
        cat_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(category)"))]
        assert "avatar" in user_cols and "avatar_emoji" not in user_cols
        assert "icon" in cat_cols and "default_km" in cat_cols
        # Emojis bleiben als Avatar gültig
        assert conn.execute(text("SELECT avatar FROM user")).scalar() == "🏃"
        icons = [r[0] for r in conn.execute(text("SELECT icon FROM category ORDER BY id"))]
        assert icons == ["rad", "medaille"]  # bekannt gemappt, unbekannt → Fallback
        assert conn.execute(text("SELECT default_km FROM category")).scalar() == 10.0
        ms = json.loads(conn.execute(text("SELECT milestones_json FROM season")).scalar())
        assert ms == [{"km": 500, "label": "Halbzeit", "icon": "berg"}]


def test_migration_ist_idempotent():
    engine = make_old_engine()
    migrate(engine)
    migrate(engine)  # zweiter Lauf darf nichts kaputt machen
    with engine.connect() as conn:
        assert conn.execute(text("SELECT icon FROM category WHERE id = 1")).scalar() == "rad"


def test_migrate_adds_strava_sport_types_column(tmp_path):
    from sqlalchemy import text
    from sqlmodel import create_engine

    from app import db

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE category (id INTEGER PRIMARY KEY, name VARCHAR, factor FLOAT, "
            "color VARCHAR, icon VARCHAR, default_km FLOAT, is_active BOOLEAN)"
        ))
        conn.execute(text("INSERT INTO category (id, name, factor, color, icon, default_km, is_active) "
                          "VALUES (1, 'Alt', 2.0, '#000000', 'medaille', 10.0, 1)"))

    db.migrate(engine)

    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("category")'))]
        assert "strava_sport_types" in cols
        val = conn.execute(text("SELECT strava_sport_types FROM category WHERE id = 1")).scalar()
        assert val == "[]"


def test_migrate_adds_backfill_columns(tmp_path):
    from sqlalchemy import text
    from sqlmodel import create_engine

    from app import db

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE stravaconnection (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "athlete_id INTEGER, access_token VARCHAR, refresh_token VARCHAR, "
            "expires_at INTEGER, created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO stravaconnection (id, user_id, athlete_id, access_token, "
            "refresh_token, expires_at) VALUES (1, 1, 99, 'a', 'r', 123)"
        ))

    db.migrate(engine)

    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("stravaconnection")'))]
        assert "backfill_state" in cols
        assert "backfill_total" in cols
        assert "backfill_done" in cols
        row = conn.execute(text(
            "SELECT backfill_state, backfill_total, backfill_done FROM stravaconnection WHERE id = 1"
        )).first()
        assert row == ("idle", 0, 0)


def test_migration_adds_season_start_date_and_backfills_2026(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE season (id INTEGER PRIMARY KEY, year INTEGER, "
            "goal_km FLOAT, milestones_json TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO season (year, goal_km, milestones_json)"
            " VALUES (2026, 1000, '[]'), (2027, 1000, '[]')"
        ))
    migrate(engine)
    with engine.begin() as conn:
        rows = dict(conn.execute(
            text("SELECT year, start_date FROM season ORDER BY year")
        ).fetchall())
    assert rows[2026] == "2026-07-20"  # einmaliger Backfill
    assert rows[2027] is None


def test_migration_adds_user_km_factor(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR, "
            "password_hash VARCHAR, display_name VARCHAR, avatar VARCHAR, "
            "is_admin BOOLEAN, is_active BOOLEAN, created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO user (username, password_hash, display_name, avatar, is_admin, is_active)"
            " VALUES ('erik', 'x', 'Erik', 'icon:laufen', 1, 1)"
        ))
    migrate(engine)
    with engine.begin() as conn:
        val = conn.execute(text("SELECT km_factor FROM user")).scalar()
    assert val == 1.0


def test_migration_adds_activity_start_time(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE activity (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "category_id INTEGER, date DATE, distance_km FLOAT, duration_min INTEGER, "
            "elevation_m FLOAT, note VARCHAR, created_at DATETIME, updated_at DATETIME, "
            "source VARCHAR, external_id VARCHAR)"
        ))
        conn.execute(text(
            "INSERT INTO activity (user_id, category_id, date, distance_km, source)"
            " VALUES (1, 1, '2026-07-01', 5.0, 'manual')"
        ))
    migrate(engine)
    migrate(engine)  # zweiter Lauf: idempotent
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("activity")'))]
        assert "start_time" in cols
        assert conn.execute(text("SELECT start_time FROM activity")).scalar() is None
