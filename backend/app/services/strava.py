import json
import logging
import time
from datetime import date as date_type
from datetime import datetime, timezone
from datetime import time as time_type
from urllib.parse import urlencode

import httpx
from sqlmodel import Session, select

from .. import config
from ..db import engine
from ..models import Activity, ActivityTrack, Category, StravaConnection, StravaIgnored
from .season_window import current_season

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


def is_ignored(session: Session, user_id: int, external_id: str) -> bool:
    """True, wenn der Nutzer diese Strava-Aktivität zuvor gelöscht hat
    (StravaIgnored) — blockt den Re-Import über Webhook/Backfill."""
    return session.exec(
        select(StravaIgnored).where(
            StravaIgnored.user_id == user_id,
            StravaIgnored.external_id == external_id,
        )
    ).first() is not None


def _latlng(value: list | None) -> list | None:
    """Strava liefert bei fehlender GPS-Spur `[]`; vereinzelt kommen auch
    verstümmelte Listen mit nur einem Element vor. Beides → None statt
    IndexError bei track.start_lat/end_lat."""
    if not value or len(value) < 2:
        return None
    return value


def upsert_track(session: Session, act: Activity, data: dict) -> ActivityTrack | None:
    """Legt die GPS-Spur zu `act` an oder aktualisiert die bestehende.
    Gibt None zurück, wenn `start_date` fehlt (kein Commit)."""
    start_date = data.get("start_date")
    if not start_date:
        return None
    start_utc = (
        datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    elapsed_s = data.get("elapsed_time") or data.get("moving_time") or 0
    start_latlng = _latlng(data.get("start_latlng"))
    end_latlng = _latlng(data.get("end_latlng"))
    polyline = (data.get("map") or {}).get("summary_polyline") or None
    private = bool(data.get("private")) or data.get("visibility") == "only_me"

    track = session.exec(
        select(ActivityTrack).where(ActivityTrack.activity_id == act.id)
    ).first()
    if track is None:
        track = ActivityTrack(activity_id=act.id)
    track.start_utc = start_utc
    track.elapsed_s = elapsed_s
    track.start_lat = start_latlng[0] if start_latlng else None
    track.start_lng = start_latlng[1] if start_latlng else None
    track.end_lat = end_latlng[0] if end_latlng else None
    track.end_lng = end_latlng[1] if end_latlng else None
    track.polyline = polyline
    track.private = private
    session.add(track)
    return track


def _after_change(session: Session, act: Activity, emit_feed: bool = True) -> None:
    """Hook für Together-Matching (ausgefüllt in einem späteren Task, siehe
    Spec 2026-10-05 Teil B) — in diesem PR noch ein No-op."""
    pass


def _derive_fields(session: Session, data: dict) -> dict:
    """Berechnet die aus Strava-Rohdaten abgeleiteten Aktivitätsfelder —
    gemeinsame Logik für Import und Update. Die Skip-Regeln (Import) bzw.
    Pro-Feld-Bedingungen (Update) entscheiden jeweils der Aufrufer anhand
    dieser Werte."""
    cat = category_for_sport(session, data.get("sport_type") or data.get("type"))
    distance_km = round((data.get("distance") or 0) / 1000, 2)
    elevation_m = round(data.get("total_elevation_gain") or 0, 1) or None
    act_date = _parse_date(data.get("start_date_local") or data.get("start_date"))
    act_time = _parse_time(data.get("start_date_local") or data.get("start_date"))
    # Mindestens 1 min, sobald etwas aufgezeichnet wurde ("Der nimmt alles mit")
    moving_time = data.get("moving_time") or 0
    duration_min = max(1, round(moving_time / 60)) if moving_time > 0 else None
    return {
        "category": cat,
        "distance_km": distance_km,
        "elevation_m": elevation_m,
        "date": act_date,
        "start_time": act_time,
        "duration_min": duration_min,
        "note": data.get("name"),
    }


def import_activity(
    session: Session, conn: StravaConnection, data: dict, emit_feed: bool = True
) -> bool:
    """Importiert eine Strava-Aktivität (Summary oder Detail) idempotent.
    Gibt True zurück, wenn neu angelegt; False bei Skip/Dublette.
    emit_feed=False unterdrückt Feed-Events (Backfill-Schutz)."""
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
    if is_ignored(session, conn.user_id, str(activity_id)):
        return False
    fields = _derive_fields(session, data)
    cat = fields["category"]
    if cat is None:
        return False
    distance_km = fields["distance_km"]
    if distance_km <= 0:
        return False
    elevation_m = fields["elevation_m"]
    act_date = fields["date"]
    act_time = fields["start_time"]
    # Stichtag gilt überall — auch für nachträglich bei Strava erfasste alte
    # Aktivitäten, die per Webhook als "create" hereinkommen.
    since = config.strava_import_since()
    if since is not None and act_date < since:
        return False
    duration_min = fields["duration_min"]

    from . import feed

    order_before = feed.challenge_order(session) if emit_feed else []
    total_before = feed.challenge_total(session, conn.user_id) if emit_feed else 0.0
    act = Activity(
        user_id=conn.user_id,
        category_id=cat.id,
        date=act_date,
        start_time=act_time,
        distance_km=distance_km,
        duration_min=duration_min,
        elevation_m=elevation_m,
        note=fields["note"],
        source="strava",
        external_id=str(activity_id),
    )
    session.add(act)
    session.commit()

    # Track-Erfassung darf den Import nie zum Scheitern bringen (z.B.
    # unparsbares start_date oder sonstige Strava-Dateneigenheiten). Die
    # Aktivität ist bereits committed; ein Fehler hier wird nur geloggt und
    # verworfen, die Aktivität bleibt ohne Track importiert.
    try:
        upsert_track(session, act, data)
        session.commit()
    except Exception:
        logging.getLogger(__name__).exception(
            "Track-Erfassung fehlgeschlagen fuer activity_id=%s", act.id
        )
        session.rollback()

    from .achievements import check_unlocks

    check_unlocks(session, conn.user_id)
    if emit_feed:
        feed.activity_event(session, act)
        feed.milestone_events(
            session, conn.user_id, total_before,
            feed.challenge_total(session, conn.user_id),
        )
        feed.rank_events(session, order_before, feed.challenge_order(session))
    _after_change(session, act, emit_feed)
    return True


def update_activity(session: Session, conn: StravaConnection, data: dict) -> None:
    """Verarbeitet ein Strava-Update-Webhook-Event. Ignorierte Aktivitäten
    werden übersprungen; unbekannte wie ein Neuimport behandelt. Solange die
    Aktivität nicht in MeterMachen bearbeitet wurde (updated_at is None),
    übernimmt es Titel und Werte 1:1 von Strava; danach bleiben die Werte
    unverändert, nur der Track (z.B. nachträglich hochgeladene GPS-Spur,
    geänderte Sichtbarkeit) wird aktualisiert."""
    activity_id = data.get("id")
    if not activity_id:
        return
    if is_ignored(session, conn.user_id, str(activity_id)):
        return
    act = session.exec(
        select(Activity).where(
            Activity.user_id == conn.user_id,
            Activity.external_id == str(activity_id),
            Activity.source == "strava",
        )
    ).first()
    if act is None:
        import_activity(session, conn, data)
        return

    from . import feed

    changed = False
    order_before: list[int] = []
    total_before = 0.0

    if act.updated_at is None:
        order_before = feed.challenge_order(session)
        total_before = feed.challenge_total(session, conn.user_id)
        fields = _derive_fields(session, data)
        cat = fields["category"]
        distance_km = fields["distance_km"]
        elevation_m = fields["elevation_m"]
        act_date = fields["date"]
        act_time = fields["start_time"]
        duration_min = fields["duration_min"]
        note = fields["note"]

        if note != act.note:
            changed = True
        act.note = note
        if cat is not None and cat.id != act.category_id:
            changed = True
            act.category_id = cat.id
        if distance_km > 0 and distance_km != act.distance_km:
            changed = True
            act.distance_km = distance_km
        if duration_min != act.duration_min:
            changed = True
        act.duration_min = duration_min
        if elevation_m != act.elevation_m:
            changed = True
        act.elevation_m = elevation_m
        if act_date != act.date:
            changed = True
        act.date = act_date
        if act_time != act.start_time:
            changed = True
        act.start_time = act_time
        session.add(act)
        session.commit()

    # Track-Erfassung darf das Update nie zum Scheitern bringen (siehe
    # import_activity) — ein Fehler hier wird nur geloggt und verworfen.
    try:
        upsert_track(session, act, data)
        session.commit()
    except Exception:
        logging.getLogger(__name__).exception(
            "Track-Erfassung fehlgeschlagen fuer activity_id=%s", act.id
        )
        session.rollback()

    if changed:
        feed.refresh_activity_events(session, act)

        from .achievements import check_unlocks

        check_unlocks(session, conn.user_id)
        feed.milestone_events(
            session, conn.user_id, total_before,
            feed.challenge_total(session, conn.user_id),
        )
        feed.rank_events(session, order_before, feed.challenge_order(session))

    _after_change(session, act)


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


def _backfill_from(session: Session) -> date_type:
    """Importstart: 1. Januar des Jahres der aktiven Season — ein Neu-Connect
    im Frühjahr 2027 muss die 2026er-km der laufenden Saison mitholen.
    Der STRAVA_IMPORT_SINCE-Stichtag verschiebt weiterhin nach hinten."""
    season = current_season(session)
    jahr = season.year if season is not None else date_type.today().year
    start_date = date_type(jahr, 1, 1)
    since = config.strava_import_since()
    if since is not None and since > start_date:
        start_date = since
    return start_date


def backfill_current_year(user_id: int) -> None:
    """Importiert alle Aktivitäten der laufenden Saison beim ersten Connect.
    Läuft als BackgroundTask, eigene DB-Session, idempotent, best-effort."""
    with Session(engine) as session:
        start_date = _backfill_from(session)
        year_start = int(
            datetime(start_date.year, start_date.month, start_date.day).timestamp()
        )
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
                if import_activity(session, conn, data, emit_feed=False):
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


def _fetch_activity_data(session: Session, conn: StravaConnection, activity_id: int) -> dict:
    """Token + Detail-Abruf + id-Fallback — gemeinsame Beschaffung für die
    'create'- und 'update'-Zweige von handle_webhook_event."""
    token = valid_access_token(session, conn)
    data = fetch_activity(token, activity_id)
    data.setdefault("id", activity_id)
    return data


def handle_webhook_event(session: Session, payload: dict) -> None:
    """Verzweigt nach aspect_type: 'create' importiert neu (idempotent über
    external_id), 'update' pflegt Titel/Werte nach, solange die Aktivität
    nicht in MeterMachen bearbeitet wurde. 'delete' folgt in einem späteren
    Task."""
    if payload.get("object_type") != "activity":
        return
    aspect = payload.get("aspect_type")
    if aspect not in ("create", "update"):
        return  # 'delete' -> Task 4
    owner_id = payload.get("owner_id")
    activity_id = payload.get("object_id")
    conn = session.exec(
        select(StravaConnection).where(StravaConnection.athlete_id == owner_id)
    ).first()
    if conn is None:
        return

    if aspect == "create":
        already = session.exec(
            select(Activity).where(
                Activity.user_id == conn.user_id,
                Activity.external_id == str(activity_id),
                Activity.source == "strava",
            )
        ).first()
        if already is not None:
            return
        import_activity(session, conn, _fetch_activity_data(session, conn, activity_id))
        return

    # aspect == "update"
    update_activity(session, conn, _fetch_activity_data(session, conn, activity_id))
