from datetime import date as date_type
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    display_name: str
    avatar: str = "icon:laufen"
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    factor: float
    color: str
    icon: str = "medaille"
    default_km: float = 10.0
    is_active: bool = True
    strava_sport_types: str = "[]"  # JSON-Liste gemappter Strava-Sportarten, z.B. ["Run","TrailRun"]


class StravaConnection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    athlete_id: int = Field(index=True)
    access_token: str
    refresh_token: str
    expires_at: int  # Unix-Epoch-Sekunden (Strava-Format), keine Zeitzonen-Fallen
    created_at: datetime = Field(default_factory=utcnow)


class Activity(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    category_id: int = Field(foreign_key="category.id")
    date: date_type = Field(index=True)
    distance_km: float
    duration_min: int | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None
    source: str = "manual"
    external_id: str | None = None


class Season(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    year: int = Field(unique=True)
    goal_km: float
    milestones_json: str = "[]"  # JSON-Liste [{"km":..,"label":..,"icon":..}]
    map_image: str | None = None
