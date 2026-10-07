"""Together-Matching (Spec 2026-10-05 Teil 1, 2.1): erkennt, dass Strava-
Aktivitäten verschiedener Mitglieder gemeinsam absolviert wurden, und führt
sie in `TrainingSession`s zusammen; Lebenszyklus (Spec 2.2–2.7: Bestätigen,
Ablehnen, Ablauf, Löschen) und Feed-Event `together` (Spec 3.1)."""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..deps import addon_active
from ..models import (
    Activity,
    ActivityTrack,
    AddOn,
    SessionParticipant,
    TrainingSession,
    User,
)
from . import feed
from .notify import notify
from .together_geo import decode_polyline, route_overlap, times_overlap

AUTO_SHARE = 0.5
SUGGEST_SHARE = 0.3
MIN_KM = 2.0
SUGGESTION_DAYS = 14

ADDON_KEY = "together"


def enabled(session: Session) -> bool:
    """True, wenn das Add-on `together` existiert und gerade aktiv ist."""
    addon = session.exec(select(AddOn).where(AddOn.key == ADDON_KEY)).first()
    return addon is not None and addon_active(addon, datetime.now(timezone.utc))


def participation_for(session: Session, activity_id: int) -> SessionParticipant | None:
    return session.exec(
        select(SessionParticipant).where(SessionParticipant.activity_id == activity_id)
    ).first()


def _classify(km: float, share: float) -> str | None:
    if share >= AUTO_SHARE and km >= MIN_KM:
        return "auto"
    if share >= SUGGEST_SHARE or km >= MIN_KM:
        return "suggest"
    return None


def _decode(polyline: str | None) -> list[tuple[float, float]] | None:
    if not polyline:
        return None
    try:
        points = decode_polyline(polyline)
    except ValueError:
        return None
    return points if len(points) >= 2 else None


def _candidates(session: Session, act: Activity, track: ActivityTrack):
    """(Track, Activity) anderer aktiver Nutzer mit detect_together, deren
    Zeitfenster sich mit `track` überlappt."""
    window = timedelta(days=1)
    rows = session.exec(
        select(ActivityTrack, Activity)
        .join(Activity, Activity.id == ActivityTrack.activity_id)
        .join(User, User.id == Activity.user_id)
        .where(
            Activity.user_id != act.user_id,
            User.is_active,
            User.detect_together,
            ActivityTrack.polyline.is_not(None),
            ActivityTrack.start_utc >= track.start_utc - window,
            ActivityTrack.start_utc <= track.start_utc + window,
        )
        .order_by(ActivityTrack.start_utc, ActivityTrack.id)
    ).all()
    return [
        (t, a) for t, a in rows
        if times_overlap(track.start_utc, track.elapsed_s, t.start_utc, t.elapsed_s)
    ]


def _pair_blocked(pa: SessionParticipant | None, pb: SessionParticipant | None) -> bool:
    """Schon in derselben Session, oder eine Seite hat ihre Teilnahme
    abgelehnt (Spec 2.3) — eine abgelehnte Aktivität zieht keine neuen
    Partner in ihre Session und löst keine Zusammenführung aus."""
    if any(p is not None and p.status == "declined" for p in (pa, pb)):
        return True
    return pa is not None and pb is not None and pa.session_id == pb.session_id


def _naive_utc(ts: datetime) -> datetime:
    """Frisch angelegte Objekte tragen eine zeitzonen-bewusste Zeit, aus
    SQLite geladene eine naive (UTC) — für Vergleiche vereinheitlichen."""
    return ts.astimezone(timezone.utc).replace(tzinfo=None) if ts.tzinfo else ts


def _age_key(obj) -> tuple[datetime, int]:
    """Sortierschlüssel (created_at naiv UTC, id)."""
    return _naive_utc(obj.created_at), obj.id


def _merge(session: Session, keep: TrainingSession, drop: TrainingSession) -> None:
    """Teilnahmen von `drop` nach `keep` umhängen und `drop` löschen. Hat der
    Nutzer in beiden Sessions eine Teilnahme, wird die jüngere verworfen."""
    in_keep = {
        p.user_id: p for p in session.exec(
            select(SessionParticipant).where(SessionParticipant.session_id == keep.id)
        ).all()
    }
    moving = []
    for p in session.exec(
        select(SessionParticipant).where(SessionParticipant.session_id == drop.id)
    ).all():
        other = in_keep.get(p.user_id)
        if other is not None and _age_key(other) <= _age_key(p):
            session.delete(p)
            continue
        if other is not None:
            session.delete(other)
        moving.append(p)
    session.flush()  # Löschungen vor dem Umhängen (unique session_id, user_id)
    for p in moving:
        p.session_id = keep.id
        session.add(p)
    session.flush()
    feed.remove_together_event(session, drop)
    session.delete(drop)
    session.flush()


def _choose_session(
    session: Session, pa: SessionParticipant | None, pb: SessionParticipant | None
) -> tuple[TrainingSession, int | None]:
    """Ziel-Session für das Paar und ggf. die id der darin aufgegangenen."""
    if pa is not None and pb is not None:
        sa = session.get(TrainingSession, pa.session_id)
        sb = session.get(TrainingSession, pb.session_id)
        keep, drop = sorted((sa, sb), key=_age_key)
        drop_id = drop.id
        _merge(session, keep, drop)
        return keep, drop_id
    if pb is not None:
        return session.get(TrainingSession, pb.session_id), None
    if pa is not None:
        return session.get(TrainingSession, pa.session_id), None
    ts = TrainingSession(source="auto")
    session.add(ts)
    session.flush()
    return ts, None


def _join(
    session: Session, ts: TrainingSession, act: Activity, status: str, km: float
) -> SessionParticipant | None:
    """Teilnahme für `act` in `ts` anlegen oder aktualisieren (nie herabstufen).
    Gibt die Teilnahme zurück, wenn sie neu angelegt wurde."""
    p = participation_for(session, act.id)
    if p is None:
        p = session.exec(
            select(SessionParticipant).where(
                SessionParticipant.session_id == ts.id,
                SessionParticipant.user_id == act.user_id,
            )
        ).first()
    if p is None:
        p = SessionParticipant(
            session_id=ts.id, user_id=act.user_id, activity_id=act.id,
            status=status, km_together=km,
        )
        session.add(p)
        session.flush()
        return p
    if p.status == "suggested" and status == "confirmed":
        # Session-Werte stammen nur aus bestätigten Paaren (Spec 1.6)
        p.status = "confirmed"
        p.km_together = km
    elif p.status == status:
        p.km_together = max(p.km_together, km)
    session.add(p)
    session.flush()
    return None


def match_activity(session: Session, act: Activity, *, emit_feed: bool = True) -> None:
    """Sucht gemeinsame Aktivitäten zu `act` und legt/erweitert Sessions."""
    if not enabled(session):
        return
    user = session.get(User, act.user_id)
    if user is None or not user.is_active or not user.detect_together:
        return
    track = session.exec(
        select(ActivityTrack).where(ActivityTrack.activity_id == act.id)
    ).first()
    if track is None:
        return
    points_a = _decode(track.polyline)
    if points_a is None:
        return

    touched: dict[int, TrainingSession] = {}
    pending: list[tuple[int, str, dict]] = []
    for track_b, act_b in _candidates(session, act, track):
        pa, pb = participation_for(session, act.id), participation_for(session, act_b.id)
        if _pair_blocked(pa, pb):
            continue
        points_b = _decode(track_b.polyline)
        if points_b is None:
            continue
        km, share = route_overlap(points_a, points_b, act.distance_km, act_b.distance_km)
        result = _classify(km, share)
        if result is None:
            continue

        ts, dropped = _choose_session(session, pa, pb)
        if dropped is not None:
            touched.pop(dropped, None)
            for _, _, payload in pending:
                if payload["session_id"] == dropped:
                    payload["session_id"] = ts.id
        touched[ts.id] = ts
        status = "confirmed" if result == "auto" else "suggested"
        kind = "together_auto" if result == "auto" else "together_suggested"
        for a in (act, act_b):
            new = _join(session, ts, a, status, km)
            if new is not None:
                pending.append((a.user_id, kind, {
                    "session_id": ts.id, "activity_id": a.id, "km_together": km,
                }))

    for ts in touched.values():
        refresh_session(session, ts, emit_feed=emit_feed)
    session.commit()
    for user_id, kind, payload in pending:
        notify(user_id, kind, payload)


def _confirmed(session: Session, ts: TrainingSession) -> list[SessionParticipant]:
    return list(session.exec(
        select(SessionParticipant).where(
            SessionParticipant.session_id == ts.id,
            SessionParticipant.status == "confirmed",
        )
    ).all())


def is_real(session: Session, ts: TrainingSession) -> bool:
    """Echt = mindestens zwei bestätigte Teilnahmen (Spec 2.1)."""
    return len(_confirmed(session, ts)) >= 2


def _now() -> datetime:
    """Jetzt als naive UTC-Zeit (so liest SQLite die Zeitstempel zurück)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _respond(session: Session, participant: SessionParticipant, status: str) -> None:
    participant.status = status
    participant.responded_at = _now()
    session.add(participant)
    session.flush()
    ts = session.get(TrainingSession, participant.session_id)
    if ts is not None:
        refresh_session(session, ts)
    session.commit()


def confirm(
    session: Session, participant: SessionParticipant, activity_id: int | None = None
) -> None:
    """Eigene Teilnahme bestätigen. Eine mitgegebene `activity_id` wird hier
    nur übernommen — ihre Prüfung (Tag ±1, noch in keiner Session) folgt mit
    dem manuellen Taggen."""
    if activity_id is not None:
        participant.activity_id = activity_id
    _respond(session, participant, "confirmed")


def decline(session: Session, participant: SessionParticipant) -> None:
    """„War ich nicht dabei“: Teilnahme bleibt als `declined` gespeichert
    (Spec 2.3), damit das Paar nicht erneut vorgeschlagen wird."""
    _respond(session, participant, "declined")


def expire_suggestions(session: Session, now: datetime | None = None) -> None:
    """Unbeantwortete Vorschläge älter als SUGGESTION_DAYS gelten als
    abgelehnt (Spec 2.4, lazy beim Abruf). `responded_at` bleibt leer — es
    gab keine Antwort."""
    cutoff = _naive_utc(now or datetime.now(timezone.utc)) - timedelta(days=SUGGESTION_DAYS)
    affected: dict[int, TrainingSession] = {}
    for p in session.exec(
        select(SessionParticipant).where(SessionParticipant.status == "suggested")
    ).all():
        if _naive_utc(p.created_at) >= cutoff:
            continue
        p.status = "declined"
        session.add(p)
        ts = session.get(TrainingSession, p.session_id)
        if ts is not None:
            affected[ts.id] = ts
    if not affected:
        return
    session.flush()
    for ts in affected.values():
        refresh_session(session, ts)
    session.commit()


def remove_activity(session: Session, activity_id: int) -> None:
    """Teilnahme einer gelöschten Aktivität entfernen (Spec 2.6). Session
    ohne Teilnahmen wird samt Feed-Event gelöscht, sonst neu berechnet."""
    p = participation_for(session, activity_id)
    if p is None:
        return
    ts = session.get(TrainingSession, p.session_id)
    session.delete(p)
    session.flush()
    if ts is not None:
        rest = session.exec(
            select(SessionParticipant).where(SessionParticipant.session_id == ts.id)
        ).first()
        if rest is None:
            feed.remove_together_event(session, ts)
            session.delete(ts)
            session.flush()
        else:
            refresh_session(session, ts)
    session.commit()


def refresh_session(
    session: Session, ts: TrainingSession, *, emit_feed: bool = True
) -> None:
    """`km_together`/`share` aus den bestätigten Teilnahmen neu berechnen
    (jeweils Maximum). `share` je Teilnahme = km_together / eigene Distanz,
    gedeckelt auf 1 — das Maximum darüber entspricht dem paarweisen Maximum.
    Danach Feed-Event angleichen und, wenn echt, Achievements prüfen."""
    confirmed = _confirmed(session, ts)
    ts.km_together = max((p.km_together for p in confirmed), default=0)
    shares = []
    for p in confirmed:
        if p.activity_id is None:
            continue
        a = session.get(Activity, p.activity_id)
        if a is not None and a.distance_km > 0 and p.km_together > 0:
            shares.append(min(1.0, p.km_together / a.distance_km))
    ts.share = max(shares) if shares else None
    session.add(ts)
    session.flush()

    feed.sync_together_event(session, ts, emit=emit_feed)
    if len(confirmed) < 2:
        return
    # Achievements committen selbst und rollen bei Unique-Konflikten zurück —
    # vorher sichern, damit nichts Ungespeichertes verloren geht.
    session.commit()
    from . import achievements  # function-level: achievements kennt bald together

    for p in confirmed:
        achievements.check_unlocks(session, p.user_id)
