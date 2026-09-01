from datetime import date as date_type
from datetime import datetime, timezone
from datetime import time as time_type

from sqlalchemy import Index, UniqueConstraint
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
    # Zeitpunkt der expliziten Einwilligung, die eigenen (auch via Strava
    # importierten) Aktivitäten den anderen Gruppenmitgliedern im Ranking zu
    # zeigen. None = noch nicht zugestimmt. Voraussetzung für Strava-Connect.
    strava_consent_at: datetime | None = None


class Category(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    factor: float
    color: str
    icon: str = "medaille"
    default_km: float = 10.0
    is_active: bool = True
    strava_sport_types: str = "[]"  # JSON-Liste gemappter Strava-Sportarten, z.B. ["Run","TrailRun"]


class CategoryFactorChange(SQLModel, table=True):
    """Faktor-Änderung ab Stichtag (Spec 2026-09-01). Category.factor bleibt
    der Ur-Faktor vor der ältesten Änderung; maßgeblich ist das
    Aktivitätsdatum — nie rückwirkend."""

    __table_args__ = (UniqueConstraint("category_id", "valid_from"),)

    id: int | None = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    factor: float
    valid_from: date_type
    created_at: datetime = Field(default_factory=utcnow)


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
    start_time: time_type | None = None  # nur Datensammlung, keine Auswertung (Spec §3)
    distance_km: float
    duration_min: int | None = None
    elevation_m: float | None = None  # Höhenmeter (Strava total_elevation_gain)
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
    end_date: date_type | None = None  # Challenge-Ende; None + start_date = offen


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


class ComparisonSeen(SQLModel, table=True):
    """Letzter vom jeweiligen Betrachter gesehener Vergleichsstand (pro Jahr)."""

    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_seen_user_year"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    year: int = Field(index=True)
    seen_at: datetime = Field(default_factory=utcnow)
    # JSON: [{"user_id": int, "scaled_km": float, "rank": int}, …]
    snapshot_json: str = "[]"


class AchievementUnlock(SQLModel, table=True):
    """Persistierter Achievement-Freischalt-Zeitpunkt. Einmal freigeschaltet
    bleibt freigeschaltet, auch wenn Aktivitäten später geändert werden."""

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_unlock_user_key"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key: str
    unlocked_at: datetime = Field(default_factory=utcnow)
    context_json: str = "{}"  # z. B. {"km": 4003.2} oder {"von": "...", "bis": "..."}
    showcased: bool = True  # Special-Emoji neben dem Namen zeigen (Spec §2.6)


class FeedEvent(SQLModel, table=True):
    """Chronologisches Gruppen-Feed-Event (Spec 2026-07-25 Teil B).
    type: "activity" | "rank_change" | "achievement" | "milestone"
        | "recap_week" | "recap_month"."""

    __table_args__ = (
        Index("ix_feedevent_season_created", "season_year", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    season_year: int
    type: str
    user_id: int | None = Field(default=None, foreign_key="user.id")
    activity_id: int | None = Field(default=None, foreign_key="activity.id")
    payload_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)


class FeedReaction(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "emoji", name="uq_reaction"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="feedevent.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    emoji: str
    created_at: datetime = Field(default_factory=utcnow)


class FeedSeen(SQLModel, table=True):
    """Zuletzt gesehener Feed-Stand pro Nutzer (Punkt am Tab)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    seen_at: datetime = Field(default_factory=utcnow)


class Challenge(SQLModel, table=True):
    """Zeitlich begrenzter Wettbewerb (Spec 2026-08-04). Der Stand wird zur
    Lesezeit aus den Activities gerechnet; persistiert wird nur das am Ende
    eingefrorene Ergebnis in result_json."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    creator_id: int = Field(foreign_key="user.id", index=True)
    prize: str | None = None  # freier Text, optional

    mode: str  # "ziel" | "rangliste"
    target: float | None = None  # mode="ziel": Schwelle
    top_n: int = 1  # mode="rangliste": gewertete Plaetze

    metric: str  # "mm" | "streak" | "anzahl"
    category_ids_json: str = "[]"  # leer = alle Kategorien
    streak_min_mm: float = 5.0  # nur metric="streak"

    join_mode: str  # "auto" | "opt_in"
    period_start: date_type
    period_end: date_type

    status: str = "geplant"  # "geplant" | "laufend" | "beendet" | "abgebrochen"
    result_json: str = "{}"  # bei Abschluss eingefroren
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


class ChallengeParticipant(SQLModel, table=True):
    """Nur fuer join_mode='opt_in'. Bei 'auto' sind alle aktiven User dabei,
    ohne dass Zeilen entstehen."""

    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_user"),
    )

    id: int | None = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    joined_at: datetime = Field(default_factory=utcnow)
