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
