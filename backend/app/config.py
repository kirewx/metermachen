import os
from pathlib import Path

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")  # leer → DATA_DIR/meter.db
SKIP_SEED = os.environ.get("METER_SKIP_SEED") == "1"


def database_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DATA_DIR / 'meter.db'}"
