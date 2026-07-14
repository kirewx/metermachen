import os
from datetime import date
from pathlib import Path

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")  # leer → DATA_DIR/meter.db
SKIP_SEED = os.environ.get("METER_SKIP_SEED") == "1"

STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
STRAVA_WEBHOOK_VERIFY_TOKEN = os.environ.get("STRAVA_WEBHOOK_VERIFY_TOKEN", "")
# Aktivitäten vor diesem Datum (ISO, z. B. 2026-07-11) werden nie importiert —
# weder beim Backfill noch per Webhook. Leer = kein Stichtag.
STRAVA_IMPORT_SINCE = os.environ.get("STRAVA_IMPORT_SINCE", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")

# Session-Cookie mit Secure-Flag ausliefern (nur über HTTPS senden). Default aus,
# damit lokale Entwicklung + Tests über http funktionieren; Prod setzt es auf 1.
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in (
    "1",
    "true",
    "yes",
)


def strava_import_since() -> date | None:
    if not STRAVA_IMPORT_SINCE:
        return None
    return date.fromisoformat(STRAVA_IMPORT_SINCE)


def strava_enabled() -> bool:
    return bool(
        STRAVA_CLIENT_ID
        and STRAVA_CLIENT_SECRET
        and STRAVA_WEBHOOK_VERIFY_TOKEN
        and PUBLIC_BASE_URL
    )


def database_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATA_DIR / 'meter.db'}"
