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
    is_active: bool = True
    km_factor: float = 1.0  # Admin-Handicap, wirkt nur im Challenge-Ranking
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
    backfill_state: str = "idle"  # "idle" | "running" | "done" | "error"
    backfill_total: int = 0
    backfill_done: int = 0


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
    start_date: date_type | None = None  # Challenge-Start; None = ab 1.1.


class AddOn(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    label: str
    description: str = ""
    enabled: bool = False
    active_from: datetime | None = None  # UTC; None = kein Startlimit
    active_until: datetime | None = None  # UTC; None = kein Endlimit
    created_at: datetime = Field(default_factory=utcnow)


class Bet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    type: str  # "duell" | "monats_tipp" | "ziel" | "streak" | "ueber_unter"
    creator_id: int = Field(foreign_key="user.id", index=True)
    title: str
    params_json: str = "{}"  # typspezifisch, siehe services/bets.py
    stake: int  # bei monats_tipp/ueber_unter: fixer Einsatz pro Teilnehmer
    period_start: date_type
    period_end: date_type
    status: str = "offen"  # "offen" | "laufend" | "entschieden" | "abgelehnt" | "abgebrochen"
    jackpot: int = 0  # nur monats_tipp: Übertrag aus dem Vormonat
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None
    result_json: str = "{}"  # nach Auflösung: Ist-Werte, Gewinner-IDs


class BetParticipant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    bet_id: int = Field(foreign_key="bet.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str  # "ersteller" | "gegner" | "tipper" | "gegenhalter" | "ueber" | "unter"
    choice_json: str = "{}"  # tipper: {"tipp_user_id": 5}; sonst leer
    stake: int = 0
    payout: int | None = None  # Gesamtgutschrift inkl. Einsatz; None = offen


class PointTransaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    amount: int  # + Gutschrift / - Belastung
    reason: str  # "start" | "einkommen" | "einsatz" | "gewinn" | "rueckzahlung"
    bet_id: int | None = Field(default=None, foreign_key="bet.id")
    created_at: datetime = Field(default_factory=utcnow)


class Invite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    created_by: int = Field(foreign_key="user.id")
    display_name: str | None = None
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = None
    used_by_user_id: int | None = Field(default=None, foreign_key="user.id")
