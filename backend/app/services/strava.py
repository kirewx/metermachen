import json
import logging
import time
from datetime import date as date_type
from datetime import datetime
from datetime import time as time_type
from urllib.parse import urlencode

import httpx
from sqlmodel import Session, select

from .. import config
from ..db import engine
from ..models import Activity, Category, StravaConnection

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
API_BASE = "https://www.strava.com/api/v3"
SCOPE = "activity:read_all"
_TIMEOUT = 10


def authorize_url(state: str) -> str:
    params = {
        "client_id": config.STRAVA_CLIENT_ID,
        "redirect_uri": f"{config.PUBLIC_BASE_URL}/api/strava/callback",
        "response_type": "code",
        "scope": SCOPE,
        "approval_prompt": "auto",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    r = httpx.post(TOKEN_URL, data={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def refresh_tokens(refresh_token: str) -> dict:
    r = httpx.post(TOKEN_URL, data={
        "client_id": config.STRAVA_CLIENT_ID,
        "client_secret": config.STRAVA_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def fetch_activity(access_token: str, activity_id: int) -> dict:
    r = httpx.get(
        f"{API_BASE}/activities/{activity_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def apply_tokens(conn: StravaConnection, data: dict) -> None:
    conn.access_token = data["access_token"]
    conn.refresh_token = data["refresh_token"]
    conn.expires_at = int(data["expires_at"])


def valid_access_token(session: Session, conn: StravaConnection) -> str:
    if conn.expires_at > int(time.time()) + 60:
        return conn.access_token
    data = refresh_tokens(conn.refresh_token)
    apply_tokens(conn, data)
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn.access_token


def category_for_sport(session: Session, sport_type: str | None) -> Category | None:
    if not sport_type:
        return None
    cats = session.exec(select(Category).where(Category.is_active)).all()
    for cat in cats:
        if sport_type in json.loads(cat.strava_sport_types or "[]"):
            return cat
    return None


def _parse_date(value: str | None) -> date_type:
    if not value:
        return date_type.today()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _parse_time(value: str | None) -> time_type | None:
    """Zeitanteil von start_date_local — Strava liefert lokale Wanduhrzeit mit 'Z'."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).time()


def import_activity(session: Session, conn: StravaConnection, data: dict) -> bool:
    """Importiert eine Strava-Aktivität (Summary oder Detail) idempotent.
    Gibt True zurück, wenn neu angelegt; False bei Skip/Dublette."""
    activity_id = data.get("id")
    if not activity_id:
        return False
    existing = session.exec(
        select(Activity).where(
            Activity.user_id == conn.user_id,
            Activity.external_id == str(activity_id),
            Activity.source == "strava",
        )
    ).first()
    if existing is not None:
        return False
    cat = category_for_sport(session, data.get("sport_type") or data.get("type"))
    if cat is None:
        return False
    distance_km = round((data.get("distance") or 0) / 1000, 2)
    if distance_km <= 0:
        return False
    elevation_m = round(data.get("total_elevation_gain") or 0, 1) or None
    act_date = _parse_date(data.get("start_date_local") or data.get("start_date"))
    act_time = _parse_time(data.get("start_date_local") or data.get("start_date"))
    # Stichtag gilt überall — auch für nachträglich bei Strava erfasste alte
    # Aktivitäten, die per Webhook als "create" hereinkommen.
    since = config.strava_import_since()
    if since is not None and act_date < since:
        return False
    duration_min = round((data.get("moving_time") or 0) / 60) or None
    act = Activity(
        user_id=conn.user_id,
        category_id=cat.id,
        date=act_date,
        start_time=act_time,
        distance_km=distance_km,
        duration_min=duration_min,
        elevation_m=elevation_m,
        note=data.get("name"),
        source="strava",
        external_id=str(activity_id),
    )
    session.add(act)
    session.commit()

    from .achievements import check_unlocks

    check_unlocks(session, conn.user_id)
    return True


def fetch_athlete_activities(access_token: str, after: int) -> list[dict]:
    """Holt Summary-Aktivitäten ab Epoch `after`, paginiert (100/Seite)."""
    out: list[dict] = []
    page = 1
    while True:
        r = httpx.get(
            f"{API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"after": after, "per_page": 100, "page": page},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


def _is_importable(session: Session, data: dict) -> bool:
    if category_for_sport(session, data.get("sport_type") or data.get("type")) is None:
        return False
    return (data.get("distance") or 0) > 0


def backfill_current_year(user_id: int) -> None:
    """Importiert alle Aktivitäten des laufenden Kalenderjahres beim ersten Connect.
    Läuft als BackgroundTask, eigene DB-Session, idempotent, best-effort.
    Ein gesetzter STRAVA_IMPORT_SINCE-Stichtag verschiebt den Startpunkt nach hinten."""
    start_date = date_type(date_type.today().year, 1, 1)
    since = config.strava_import_since()
    if since is not None and since > start_date:
        start_date = since
    year_start = int(datetime(start_date.year, start_date.month, start_date.day).timestamp())
    with Session(engine) as session:
        conn = session.exec(
            select(StravaConnection).where(StravaConnection.user_id == user_id)
        ).first()
        if conn is None:
            return
        conn.backfill_state = "running"
        conn.backfill_done = 0
        conn.backfill_total = 0
        session.add(conn)
        session.commit()
        try:
            token = valid_access_token(session, conn)
            activities = fetch_athlete_activities(token, year_start)
            importable = [a for a in activities if _is_importable(session, a)]
            conn.backfill_total = len(importable)
            session.add(conn)
            session.commit()
            for data in importable:
                if session.get(StravaConnection, conn.id) is None:
                    return
                if import_activity(session, conn, data):
                    conn.backfill_done += 1
                    session.add(conn)
                    session.commit()
            conn.backfill_state = "done"
            session.add(conn)
            session.commit()
        except Exception:
            logging.getLogger(__name__).exception(
                "Strava-Backfill fehlgeschlagen fuer user_id=%s", user_id
            )
            try:
                session.rollback()
                conn.backfill_state = "error"
                session.add(conn)
                session.commit()
            except Exception:
                logging.getLogger(__name__).exception(
                    "Konnte Backfill-Fehlerstatus nicht speichern fuer user_id=%s", user_id
                )


def handle_webhook_event(session: Session, payload: dict) -> None:
    """Importiert genau neue Strava-Aktivitäten (aspect 'create'). Idempotent über external_id."""
    if payload.get("object_type") != "activity" or payload.get("aspect_type") != "create":
        return
    owner_id = payload.get("owner_id")
    activity_id = payload.get("object_id")
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.athlete_id == owner_id)
    ).first()
    if conn is None:
        return
    already = session.exec(
        select(Activity).where(
            Activity.user_id == conn.user_id,
            Activity.external_id == str(activity_id),
            Activity.source == "strava",
        )
    ).first()
    if already is not None:
        return
    token = valid_access_token(session, conn)
    data = fetch_activity(token, activity_id)
    data.setdefault("id", activity_id)
    import_activity(session, conn, data)
