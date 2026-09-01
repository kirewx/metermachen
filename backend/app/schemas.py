import json
from datetime import date as date_type
from datetime import datetime, timezone
from datetime import time as time_type

from pydantic import BaseModel, Field, field_validator

from .models import AddOn, Category, CategoryFactorChange, Season


class Milestone(BaseModel):
    km: float
    label: str
    icon: str = "fahne"


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    factor: float = Field(gt=0)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str = "medaille"
    default_km: float = Field(default=10.0, gt=0)
    strava_sport_types: list[str] = []


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    factor: float | None = Field(default=None, gt=0)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = None
    default_km: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
    strava_sport_types: list[str] | None = None


class FactorChangeCreate(BaseModel):
    factor: float = Field(gt=0)
    valid_from: date_type


class FactorChangeOut(BaseModel):
    id: int
    factor: float
    valid_from: date_type


class CategoryOut(BaseModel):
    id: int
    name: str
    factor: float  # der HEUTE gültige Faktor (berechnet, nie gespeichert)
    base_factor: float  # Ur-Faktor vor der ältesten Änderung
    color: str
    icon: str
    default_km: float
    is_active: bool
    strava_sport_types: list[str]
    pending_changes: list[FactorChangeOut] = []
    history: list[FactorChangeOut] = []

    @classmethod
    def from_category(
        cls, cat: Category, changes: list[CategoryFactorChange] | None = None
    ) -> "CategoryOut":
        changes = sorted(changes or [], key=lambda c: c.valid_from)
        heute = date_type.today()
        wirksam = [c for c in changes if c.valid_from <= heute]
        return cls(
            id=cat.id,
            name=cat.name,
            factor=wirksam[-1].factor if wirksam else cat.factor,
            base_factor=cat.factor,
            color=cat.color,
            icon=cat.icon,
            default_km=cat.default_km,
            is_active=cat.is_active,
            strava_sport_types=json.loads(cat.strava_sport_types or "[]"),
            pending_changes=[
                FactorChangeOut(id=c.id, factor=c.factor, valid_from=c.valid_from)
                for c in changes
                if c.valid_from > heute
            ],
            history=[
                FactorChangeOut(id=c.id, factor=c.factor, valid_from=c.valid_from)
                for c in wirksam
            ],
        )


class SeasonCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    goal_km: float = Field(gt=0)
    milestones: list[Milestone] = []
    start_date: date_type | None = None
    end_date: date_type | None = None


class SeasonPatch(BaseModel):
    goal_km: float | None = Field(default=None, gt=0)
    milestones: list[Milestone] | None = None
    start_date: date_type | None = None  # None + gesetzt = Startdatum löschen
    end_date: date_type | None = None  # None + gesetzt = Enddatum löschen (Fenster offen)


class SeasonOut(BaseModel):
    id: int
    year: int
    goal_km: float
    milestones: list[Milestone]
    start_date: date_type | None
    end_date: date_type | None

    @classmethod
    def from_season(cls, season: Season) -> "SeasonOut":
        return cls(
            id=season.id,
            year=season.year,
            goal_km=season.goal_km,
            milestones=json.loads(season.milestones_json),
            start_date=season.start_date,
            end_date=season.end_date,
        )


class AddOnCreate(BaseModel):
    key: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=1)
    description: str = ""
    enabled: bool = False
    active_from: datetime | None = None
    active_until: datetime | None = None


class AddOnPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1)
    description: str | None = None
    enabled: bool | None = None
    active_from: datetime | None = None  # None + gesetzt = Fenster-Start löschen
    active_until: datetime | None = None


class AddOnOut(BaseModel):
    id: int
    key: str
    label: str
    description: str
    enabled: bool
    active_from: datetime | None
    active_until: datetime | None
    active: bool

    @classmethod
    def from_addon(cls, addon: AddOn) -> "AddOnOut":
        from .deps import addon_active

        return cls(
            id=addon.id,
            key=addon.key,
            label=addon.label,
            description=addon.description,
            enabled=addon.enabled,
            active_from=addon.active_from,
            active_until=addon.active_until,
            active=addon_active(addon, datetime.now(timezone.utc)),
        )


class ActivityCreate(BaseModel):
    category_id: int
    date: date_type
    distance_km: float = Field(gt=0)
    duration_min: int | None = Field(default=None, gt=0)
    start_time: time_type | None = None
    elevation_m: float | None = Field(default=None, ge=0)
    note: str | None = None

    @field_validator("date")
    @classmethod
    def not_in_future(cls, v: date_type) -> date_type:
        if v > date_type.today():
            raise ValueError("Datum darf nicht in der Zukunft liegen")
        return v


class ActivityPatch(BaseModel):
    category_id: int | None = None
    date: date_type | None = None
    distance_km: float | None = Field(default=None, gt=0)
    duration_min: int | None = Field(default=None, gt=0)
    start_time: time_type | None = None
    elevation_m: float | None = Field(default=None, ge=0)
    note: str | None = None

    @field_validator("date")
    @classmethod
    def not_in_future(cls, v: date_type | None) -> date_type | None:
        if v is not None and v > date_type.today():
            raise ValueError("Datum darf nicht in der Zukunft liegen")
        return v


class ActivityOut(BaseModel):
    id: int
    category_id: int
    date: date_type
    distance_km: float
    duration_min: int | None
    start_time: time_type | None
    elevation_m: float | None
    note: str | None
    scaled_km: float
    edited: bool
    source: str
    strava_url: str | None


class CategoryShare(BaseModel):
    category_id: int
    name: str
    color: str
    icon: str
    scaled_km: float
    real_km: float = 0.0


class Segment(BaseModel):
    date: date_type
    category_id: int
    color: str
    scaled_km: float


class CumulativePoint(BaseModel):
    date: date_type
    scaled_km: float
    real_km: float = 0.0
    elevation_m: float = 0.0


class MonthElevation(BaseModel):
    """Höhenmeter eines Kalendermonats, Monat als 'YYYY-MM'."""

    month: str
    meters: float


class Auszeichnung(BaseModel):
    emoji: str
    title: str
    description: str


class ComparisonUser(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    rank: int
    total_scaled_km: float
    total_real_km: float = 0.0
    km_factor: float = 1.0
    emojis: list[str] = []
    auszeichnungen: list[Auszeichnung] = []
    total_elevation_m: float = 0.0
    by_category: list[CategoryShare]
    segments: list[Segment]
    cumulative: list[CumulativePoint]
    elevation_by_month: list[MonthElevation] = []


class ComparisonOut(BaseModel):
    year: int
    goal_km: float
    milestones: list[Milestone]
    users: list[ComparisonUser]
    start_date: date_type | None = None
    phase: str = "challenge"
    elevation_months: list[str] = []


class LastSeenEntry(BaseModel):
    user_id: int
    scaled_km: float
    rank: int


class LastSeenOut(BaseModel):
    seen_at: datetime
    entries: list[LastSeenEntry]


class FeedReactionOut(BaseModel):
    emoji: str
    count: int
    mine: bool
    users: list[str]


class FeedEventOut(BaseModel):
    id: int
    type: str
    user_id: int | None
    display_name: str | None
    avatar: str | None
    created_at: datetime
    payload: dict
    reactions: list[FeedReactionOut]


class FeedPage(BaseModel):
    events: list[FeedEventOut]
    next_before: int | None


class FeedReactionIn(BaseModel):
    emoji: str
