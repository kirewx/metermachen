import json

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from . import config
from . import models  # noqa: F401  — Tabellen registrieren

engine = create_engine(config.database_url(), connect_args={"check_same_thread": False})

ICON_KEYS = {
    "laufen", "gehen", "wandern", "rad", "schwimmen", "ski", "inline", "tanzen",
    "medaille", "fahne", "berg", "pokal", "blitz",
}
EMOJI_TO_ICON = {
    "🏃": "laufen", "👟": "laufen", "🚶": "gehen", "🥾": "wandern", "🏊": "schwimmen",
    "🚴": "rad", "💃": "tanzen", "🎿": "ski", "⛸": "inline", "🏅": "medaille",
    "🚩": "fahne", "🏔": "berg", "⛰": "berg", "🏆": "pokal",
}


def _columns(conn, table: str) -> list[str]:
    return [row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))]


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table}
    ).fetchone()
    return result is not None


def _icon_for(value: str, fallback: str) -> str:
    if value in ICON_KEYS:
        return value
    return EMOJI_TO_ICON.get(value, fallback)


def migrate(target=engine) -> None:
    """Schema-Anpassungen für Bestands-DBs (es gibt kein Alembic)."""
    with target.begin() as conn:
        user_cols = _columns(conn, "user")
        if "avatar_emoji" in user_cols:
            conn.execute(text('ALTER TABLE "user" RENAME COLUMN avatar_emoji TO avatar'))
        if user_cols and "is_active" not in user_cols:
            conn.execute(
                text('ALTER TABLE "user" ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1')
            )

        if _table_exists(conn, "category"):
            cat_cols = _columns(conn, "category")
            if "icon_emoji" in cat_cols:
                conn.execute(text("ALTER TABLE category RENAME COLUMN icon_emoji TO icon"))
                for id_, val in conn.execute(text("SELECT id, icon FROM category")).fetchall():
                    conn.execute(
                        text("UPDATE category SET icon = :i WHERE id = :id"),
                        {"i": _icon_for(val, "medaille"), "id": id_},
                    )
            if "default_km" not in cat_cols:
                conn.execute(
                    text("ALTER TABLE category ADD COLUMN default_km FLOAT NOT NULL DEFAULT 10.0")
                )
            if "strava_sport_types" not in cat_cols:
                conn.execute(text(
                    "ALTER TABLE category ADD COLUMN strava_sport_types TEXT NOT NULL DEFAULT '[]'"
                ))

        if _table_exists(conn, "season"):
            for id_, raw in conn.execute(text("SELECT id, milestones_json FROM season")).fetchall():
                milestones = json.loads(raw or "[]")
                if any("emoji" in m for m in milestones):
                    for m in milestones:
                        m["icon"] = _icon_for(m.pop("emoji", ""), "fahne")
                    conn.execute(
                        text("UPDATE season SET milestones_json = :m WHERE id = :id"),
                        {"m": json.dumps(milestones), "id": id_},
                    )

        if _table_exists(conn, "stravaconnection"):
            sc_cols = _columns(conn, "stravaconnection")
            if "backfill_state" not in sc_cols:
                conn.execute(text(
                    "ALTER TABLE stravaconnection ADD COLUMN backfill_state TEXT NOT NULL DEFAULT 'idle'"
                ))
            if "backfill_total" not in sc_cols:
                conn.execute(text(
                    "ALTER TABLE stravaconnection ADD COLUMN backfill_total INTEGER NOT NULL DEFAULT 0"
                ))
            if "backfill_done" not in sc_cols:
                conn.execute(text(
                    "ALTER TABLE stravaconnection ADD COLUMN backfill_done INTEGER NOT NULL DEFAULT 0"
                ))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    migrate(engine)
