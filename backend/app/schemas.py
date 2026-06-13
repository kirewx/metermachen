import json
from datetime import date as date_type

from pydantic import BaseModel, Field, field_validator

from .models import Category, Season


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


class CategoryOut(BaseModel):
    id: int
    name: str
    factor: float
    color: str
    icon: str
    default_km: float
    is_active: bool
    strava_sport_types: list[str]

    @classmethod
    def from_category(cls, cat: Category) -> "CategoryOut":
        return cls(
            id=cat.id,
            name=cat.name,
            factor=cat.factor,
            color=cat.color,
            icon=cat.icon,
            default_km=cat.default_km,
            is_active=cat.is_active,
            strava_sport_types=json.loads(cat.strava_sport_types or "[]"),
        )


class SeasonCreate(BaseModel):
    year: int = Field(ge=2000, le=2100)
    goal_km: float = Field(gt=0)
    milestones: list[Milestone] = []


class SeasonPatch(BaseModel):
    goal_km: float | None = Field(default=None, gt=0)
    milestones: list[Milestone] | None = None


class SeasonOut(BaseModel):
    id: int
    year: int
    goal_km: float
    milestones: list[Milestone]

    @classmethod
    def from_season(cls, season: Season) -> "SeasonOut":
        return cls(
            id=season.id,
            year=season.year,
            goal_km=season.goal_km,
            milestones=json.loads(season.milestones_json),
        )


class ActivityCreate(BaseModel):
    category_id: int
    date: date_type
    distance_km: float = Field(gt=0)
    duration_min: int | None = Field(default=None, gt=0)
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
    note: str | None
    scaled_km: float
    edited: bool
    source: str


class CategoryShare(BaseModel):
    category_id: int
    name: str
    color: str
    icon: str
    scaled_km: float


class Segment(BaseModel):
    date: date_type
    category_id: int
    color: str
    scaled_km: float


class CumulativePoint(BaseModel):
    date: date_type
    scaled_km: float


class ComparisonUser(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    rank: int
    total_scaled_km: float
    by_category: list[CategoryShare]
    segments: list[Segment]
    cumulative: list[CumulativePoint]


class ComparisonOut(BaseModel):
    year: int
    goal_km: float
    milestones: list[Milestone]
    users: list[ComparisonUser]
