"""Together-Matching (Spec 2026-10-05 Teil 1, 2.1): Strava-Aktivitäten
verschiedener Mitglieder zu gemeinsamen TrainingSessions zusammenführen."""

import itertools
import json
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlmodel import select

from app import config
from app.models import (
    Activity,
    ActivityTrack,
    FeedEvent,
    FeedReaction,
    Season,
    SessionParticipant,
    StravaConnection,
    TrainingSession,
)
from app.services import activity_delete, strava, together
from tests.conftest import make_addon, make_category, make_user

T0 = datetime(2026, 10, 1, 7, 0, 0)  # naiv UTC
ORIGIN = (48.0, 11.0)
_KM_PER_DEG_LAT = 111.195
_seq = itertools.count(1)


# --- Test-Helfer ------------------------------------------------------------


def _encode_value(value: int) -> str:
    value = ~(value << 1) if value < 0 else value << 1
    out = []
    while value >= 0x20:
        out.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    out.append(chr(value + 63))
    return "".join(out)


def encode_polyline(points: list[tuple[float, float]]) -> str:
    """Kleiner Google-Polyline-Encoder (Präzision 5), nur für Tests."""
    out = []
    prev_lat = prev_lng = 0
    for lat, lng in points:
        ilat, ilng = round(lat * 1e5), round(lng * 1e5)
        out.append(_encode_value(ilat - prev_lat))
        out.append(_encode_value(ilng - prev_lng))
        prev_lat, prev_lng = ilat, ilng
    return "".join(out)


def path(legs, start=ORIGIN, step_km=0.1) -> list[tuple[float, float]]:
    """Punktfolge aus Abschnitten [("N"|"E", km), ...] ab `start`."""
    lat, lng = start
    points = [(lat, lng)]
    for direction, km in legs:
        steps = round(km / step_km)
        for _ in range(steps):
            if direction == "N":
                lat += step_km / _KM_PER_DEG_LAT
            else:
                lng += step_km / (_KM_PER_DEG_LAT * 0.6691)  # cos(48°)
            points.append((lat, lng))
    return points


def make_strava_activity(
    session, user, *, start_utc, elapsed_s, polyline_points, distance_km,
    category=None, private=False,
) -> Activity:
    n = next(_seq)
    if category is None:
        category = make_category(session, name=f"Laufen-{n}")
    act = Activity(
        user_id=user.id,
        category_id=category.id,
        date=start_utc.date(),
        distance_km=distance_km,
        source="strava",
        external_id=f"t{n}",
    )
    session.add(act)
    session.commit()
    session.refresh(act)
    polyline = (
        polyline_points if isinstance(polyline_points, str)
        else encode_polyline(polyline_points)
    )
    session.add(ActivityTrack(
        activity_id=act.id, start_utc=start_utc, elapsed_s=elapsed_s,
        polyline=polyline, private=private,
    ))
    session.commit()
    return act


ROUTE_5 = path([("N", 5.0)])


@pytest.fixture
def addon(session):
    return make_addon(session, key="together", label="Zusammen", enabled=True)


def run(session, user, points=ROUTE_5, km=5.0, start=T0, elapsed=1800, **kw):
    return make_strava_activity(
        session, user, start_utc=start, elapsed_s=elapsed,
        polyline_points=points, distance_km=km, **kw,
    )


def sessions(session):
    return session.exec(select(TrainingSession)).all()


def parts(session):
    return session.exec(select(SessionParticipant)).all()


# --- Tests -------------------------------------------------------------------


def test_identical_routes_auto_confirmed(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)

    [ts] = sessions(session)
    ps = parts(session)
    assert {p.user_id for p in ps} == {erik.id, anna.id}
    assert all(p.status == "confirmed" for p in ps)
    assert all(p.km_together == pytest.approx(5.0, abs=0.1) for p in ps)
    assert ts.source == "auto"
    assert ts.km_together == pytest.approx(5.0, abs=0.1)
    assert ts.share == pytest.approx(1.0, abs=0.03)


def test_partial_overlap_suggested(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik, points=path([("N", 4.5)]), km=4.5)
    a = run(session, anna, points=path([("N", 1.8), ("E", 2.7)]), km=4.5)
    together.match_activity(session, a)

    [ts] = sessions(session)
    ps = parts(session)
    assert len(ps) == 2
    assert all(p.status == "suggested" for p in ps)
    # Vorschläge zählen nicht für die Session-Werte
    assert ts.km_together == 0
    assert ts.share is None


def test_below_threshold_no_session(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna, points=path([("N", 1.0), ("E", 4.0)]))
    together.match_activity(session, a)
    assert sessions(session) == []
    assert parts(session) == []


def test_late_arrival_matches(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    together.match_activity(session, e)
    assert sessions(session) == []
    # Anna lädt erst 5 h später hoch — die Aktivitätszeit ist dieselbe
    a = run(session, anna)
    together.match_activity(session, a)
    assert len(sessions(session)) == 1
    assert {p.activity_id for p in parts(session)} == {e.id, a.id}


def test_no_time_overlap_no_match(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna, start=T0 + timedelta(hours=5))
    together.match_activity(session, a)
    assert sessions(session) == []


def test_no_match_with_own_activity(session, addon):
    erik = make_user(session, "erik")
    run(session, erik)
    e2 = run(session, erik)
    together.match_activity(session, e2)
    assert sessions(session) == []


def test_no_match_when_opted_out(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    anna.detect_together = False
    session.add(anna)
    session.commit()
    e = run(session, erik)
    a = run(session, anna)
    together.match_activity(session, e)
    together.match_activity(session, a)
    assert sessions(session) == []


def test_no_match_with_inactive_user(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    anna.is_active = False
    session.add(anna)
    session.commit()
    e = run(session, erik)
    a = run(session, anna)
    together.match_activity(session, e)
    together.match_activity(session, a)
    assert sessions(session) == []


def test_only_me_activity_is_matched(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    run(session, anna, private=True)
    together.match_activity(session, e)
    assert len(sessions(session)) == 1
    assert all(p.status == "confirmed" for p in parts(session))


def test_no_match_when_addon_disabled(session):
    make_addon(session, key="together", label="Zusammen", enabled=False)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    assert together.enabled(session) is False
    together.match_activity(session, a)
    assert sessions(session) == []


def test_no_match_when_addon_missing(session):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    assert sessions(session) == []


def test_three_people_join_one_session(session, addon):
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    e = run(session, erik)
    together.match_activity(session, e)
    a = run(session, anna)
    together.match_activity(session, a)
    t = run(session, tom)
    together.match_activity(session, t)

    assert len(sessions(session)) == 1
    ps = parts(session)
    assert {p.user_id for p in ps} == {erik.id, anna.id, tom.id}
    assert all(p.status == "confirmed" for p in ps)


def test_sessions_merge_older_wins(session, addon):
    erik, anna, tom, lisa, max_ = (
        make_user(session, n) for n in ("erik", "anna", "tom", "lisa", "max")
    )
    # Session 1: Erik + Anna laufen 5 km nach Norden
    run(session, erik, points=path([("N", 5.0)]))
    a = run(session, anna, points=path([("N", 5.0)]))
    together.match_activity(session, a)
    # Session 2: Tom + Lisa laufen 5 km nach Osten, 5 km nördlich versetzt
    east_start = (ORIGIN[0] + 5.0 / _KM_PER_DEG_LAT, ORIGIN[1])
    run(session, tom, points=path([("E", 5.0)], start=east_start))
    lisa_act = run(session, lisa, points=path([("E", 5.0)], start=east_start))
    together.match_activity(session, lisa_act)
    s1, s2 = sorted(sessions(session), key=lambda s: s.id)

    # Max läuft beide Strecken: 5 km Nord, dann 5 km Ost (10 km)
    m = run(session, max_, points=path([("N", 5.0), ("E", 5.0)]), km=10.0)
    together.match_activity(session, m)

    [ts] = sessions(session)
    assert ts.id == s1.id
    assert session.get(TrainingSession, s2.id) is None
    ps = parts(session)
    assert {p.user_id for p in ps} == {erik.id, anna.id, tom.id, lisa.id, max_.id}
    assert all(p.session_id == s1.id for p in ps)


def test_rematch_is_idempotent(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    before = {(p.user_id, p.status, p.session_id) for p in parts(session)}
    together.match_activity(session, a)
    together.match_activity(session, e)
    assert len(sessions(session)) == 1
    assert {(p.user_id, p.status, p.session_id) for p in parts(session)} == before


def test_declined_pair_not_resuggested(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    a = run(session, anna)
    together.match_activity(session, e)
    p_anna = together.participation_for(session, a.id)
    p_anna.status = "declined"
    session.add(p_anna)
    session.commit()

    together.match_activity(session, e)
    together.match_activity(session, a)
    assert len(sessions(session)) == 1
    assert together.participation_for(session, a.id).status == "declined"
    assert together.participation_for(session, e.id).status == "confirmed"


def test_participation_for(session, addon):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    a = run(session, anna)
    assert together.participation_for(session, e.id) is None
    together.match_activity(session, a)
    p = together.participation_for(session, e.id)
    assert p is not None and p.user_id == erik.id


def test_notify_for_new_participations(session, addon, monkeypatch):
    calls = []
    monkeypatch.setattr(
        together, "notify", lambda uid, kind, payload: calls.append((uid, kind))
    )
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    assert sorted(calls) == sorted([(erik.id, "together_auto"), (anna.id, "together_auto")])
    calls.clear()
    together.match_activity(session, a)
    assert calls == []


def _import_payload(activity_id, polyline):
    return {
        "id": activity_id,
        "sport_type": "Run",
        "distance": 5000,
        "moving_time": 1800,
        "elapsed_time": 1800,
        "start_date": T0.isoformat() + "Z",
        "start_date_local": T0.isoformat() + "Z",
        "name": "Morgenrunde",
        "map": {"summary_polyline": polyline},
    }


def _conn(session, user, athlete_id):
    conn = StravaConnection(
        user_id=user.id, athlete_id=athlete_id,
        access_token="tok", refresh_token="ref", expires_at=9999999999,
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return conn


def test_import_triggers_matching(session, addon, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "")
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    conn = _conn(session, anna, 4711)
    assert strava.import_activity(session, conn, _import_payload(1, encode_polyline(ROUTE_5)))
    assert len(sessions(session)) == 1


def test_broken_polyline_does_not_break_import(session, addon, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "")
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    conn = _conn(session, anna, 4711)
    assert strava.import_activity(session, conn, _import_payload(2, "_p~iF~")) is True
    assert session.exec(select(Activity).where(Activity.user_id == anna.id)).first()
    assert sessions(session) == []


def test_matching_error_does_not_break_import(session, addon, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "")
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    anna = make_user(session, "anna")
    conn = _conn(session, anna, 4711)

    def boom(*a, **kw):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(together, "match_activity", boom)
    assert strava.import_activity(session, conn, _import_payload(3, "")) is True
    # Session bleibt benutzbar
    assert session.exec(select(Activity).where(Activity.user_id == anna.id)).first()


# --- Fix-Runde 1 ---------------------------------------------------------------


def _decline(session, act):
    p = together.participation_for(session, act.id)
    p.status = "declined"
    session.add(p)
    session.commit()


def _declined_setup(session):
    """A (Erik, 0–2 h) und C (Tom, 0–30 min) auto; B (Anna, 1 h–1,5 h)
    überlappt nur mit A. A lehnt ab."""
    erik, tom, anna = (make_user(session, n) for n in ("erik", "tom", "anna"))
    a = run(session, erik, elapsed=7200)
    c = run(session, tom, elapsed=1800)
    together.match_activity(session, c)
    _decline(session, a)
    b = run(session, anna, start=T0 + timedelta(hours=1), elapsed=1800)
    return a, b, c, anna


def _record_notify(monkeypatch):
    calls = []
    monkeypatch.setattr(
        together, "notify", lambda uid, kind, payload: calls.append((uid, kind))
    )
    return calls


def test_declined_candidate_does_not_pull_in_new_partner(session, addon, monkeypatch):
    a, b, c, anna = _declined_setup(session)
    calls = _record_notify(monkeypatch)
    together.match_activity(session, b)
    assert together.participation_for(session, b.id) is None
    assert len(sessions(session)) == 1
    assert calls == []


def test_declined_own_activity_does_not_match_new_partner(session, addon, monkeypatch):
    a, b, c, anna = _declined_setup(session)
    calls = _record_notify(monkeypatch)
    together.match_activity(session, a)
    assert together.participation_for(session, b.id) is None
    assert together.participation_for(session, a.id).status == "declined"
    assert len(sessions(session)) == 1
    assert calls == []


def test_suggested_pair_does_not_raise_confirmed_km(session, addon):
    erik, tom, anna = (make_user(session, n) for n in ("erik", "tom", "anna"))
    a = run(session, erik, points=path([("N", 20.0)]), km=20.0, elapsed=7200)
    c = run(session, tom, points=path([("N", 3.0)]), km=3.0, elapsed=1800)
    together.match_activity(session, c)  # A–C auto, 3 km
    # B überlappt zeitlich nur mit A: 8 km gemeinsam, Anteil 0,4 → Vorschlag
    b = run(
        session, anna, points=path([("N", 8.0), ("E", 12.0)]), km=20.0,
        start=T0 + timedelta(hours=1), elapsed=3600,
    )
    together.match_activity(session, b)

    [ts] = sessions(session)
    assert together.participation_for(session, b.id).status == "suggested"
    assert together.participation_for(session, a.id).km_together == pytest.approx(3.0, abs=0.1)
    assert ts.km_together == pytest.approx(3.0, abs=0.1)


def test_suggested_upgraded_by_auto_uses_auto_km(session, addon):
    erik, tom, anna = (make_user(session, n) for n in ("erik", "tom", "anna"))
    # A–B Vorschlag mit 8 km (Anteil 0,4)
    a = run(session, erik, points=path([("N", 20.0)]), km=20.0, elapsed=7200)
    b = run(
        session, anna, points=path([("N", 8.0), ("E", 12.0)]), km=20.0,
        start=T0 + timedelta(hours=1), elapsed=3600,
    )
    together.match_activity(session, b)
    assert together.participation_for(session, a.id).status == "suggested"
    # A–C auto mit 3 km → A wird bestätigt, km aus dem Auto-Paar
    c = run(session, tom, points=path([("N", 3.0)]), km=3.0, elapsed=1800)
    together.match_activity(session, c)
    pa = together.participation_for(session, a.id)
    assert pa.status == "confirmed"
    assert pa.km_together == pytest.approx(3.0, abs=0.1)
    [ts] = sessions(session)
    assert ts.km_together == pytest.approx(3.0, abs=0.1)


def test_merge_collision_discards_younger_participation(session, addon):
    erik, anna, tom, max_ = (make_user(session, n) for n in ("erik", "anna", "tom", "max"))
    an = run(session, anna, points=path([("N", 5.0)]))
    east_start = (ORIGIN[0] + 5.0 / _KM_PER_DEG_LAT, ORIGIN[1])
    to = run(session, tom, points=path([("E", 5.0)], start=east_start))
    cat = make_category(session, name="Ohne-Spur")
    watch, phone = (
        Activity(user_id=erik.id, category_id=cat.id, date=T0.date(), distance_km=5.0)
        for _ in range(2)
    )
    session.add_all([watch, phone])
    session.commit()
    t = [T0 + timedelta(minutes=m) for m in range(3)]
    s1 = TrainingSession(source="auto", created_at=t[0])
    s2 = TrainingSession(source="auto", created_at=t[1])
    session.add_all([s1, s2])
    session.commit()
    session.add_all([
        SessionParticipant(session_id=s1.id, user_id=anna.id, activity_id=an.id,
                           status="confirmed", km_together=5, created_at=t[0]),
        SessionParticipant(session_id=s1.id, user_id=erik.id, activity_id=watch.id,
                           status="confirmed", km_together=5, created_at=t[2]),
        SessionParticipant(session_id=s2.id, user_id=tom.id, activity_id=to.id,
                           status="confirmed", km_together=5, created_at=t[1]),
        SessionParticipant(session_id=s2.id, user_id=erik.id, activity_id=phone.id,
                           status="confirmed", km_together=5, created_at=t[1]),
    ])
    session.commit()
    s1_id, s2_id = s1.id, s2.id

    m = run(session, max_, points=path([("N", 5.0), ("E", 5.0)]), km=10.0)
    together.match_activity(session, m)

    assert [s.id for s in sessions(session)] == [s1_id]
    assert session.get(TrainingSession, s2_id) is None
    # Ältere Teilnahme (phone, t1) bleibt, jüngere (watch, t2) wird verworfen
    assert together.participation_for(session, watch.id) is None
    assert together.participation_for(session, phone.id).session_id == s1_id


def test_notify_only_after_commit(session, addon, monkeypatch):
    seen = []

    def spy(uid, kind, payload):
        # nach dem Commit läuft keine (ungespeicherte) Transaktion mehr
        seen.append((uid, kind, session.in_transaction()))

    monkeypatch.setattr(together, "notify", spy)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    assert len(seen) == 2
    assert not any(pending for _, _, pending in seen)
    assert len(parts(session)) == 2


def test_update_path_triggers_matching(session, addon, monkeypatch):
    monkeypatch.setattr(config, "STRAVA_IMPORT_SINCE", "")
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    conn = _conn(session, anna, 4711)
    assert strava.import_activity(session, conn, _import_payload(9, ""))
    assert sessions(session) == []
    strava.update_activity(session, conn, _import_payload(9, encode_polyline(ROUTE_5)))
    assert len(sessions(session)) == 1
    assert all(p.status == "confirmed" for p in parts(session))


@pytest.mark.parametrize(
    "km, share, expected",
    [
        (2.0, 0.5, "auto"),
        (1.99, 0.5, "suggest"),
        (2.0, 0.49, "suggest"),
        (1.9, 0.3, "suggest"),
        (2.0, 0.0, "suggest"),
        (1.9, 0.29, None),
        (0.0, 0.0, None),
    ],
)
def test_classify_thresholds(km, share, expected):
    assert together._classify(km, share) == expected


def test_notify_payload_follows_merge_in_same_run(session, addon, monkeypatch):
    """A matcht zuerst B (neue Session), dann C aus einer älteren Session →
    die neue geht auf; Benachrichtigungen nennen die überlebende Session."""
    calls = []
    monkeypatch.setattr(
        together, "notify", lambda uid, kind, payload: calls.append(payload["session_id"])
    )
    erik, anna, tom, lisa, max_ = (
        make_user(session, n) for n in ("erik", "anna", "tom", "lisa", "max")
    )
    # ältere Session: Tom + Lisa, später gestartet (Kandidaten nach start_utc sortiert)
    later = T0 + timedelta(minutes=5)
    run(session, tom, start=later)
    lisa_act = run(session, lisa, start=later)
    together.match_activity(session, lisa_act)
    [old] = sessions(session)
    old_id = old.id
    calls.clear()
    # Anna ohne Session, früher gestartet → Max matcht zuerst Anna, dann Tom
    run(session, anna)
    m = run(session, max_)
    together.match_activity(session, m)
    assert [s.id for s in sessions(session)] == [old_id]
    assert calls and all(sid == old_id for sid in calls)


# --- Lebenszyklus und Feed (Task 8) -------------------------------------------


@pytest.fixture
def season(session):
    s = Season(year=2026, goal_km=1000.0, start_date=date(2026, 7, 20),
               end_date=date(2027, 5, 16))
    session.add(s)
    session.commit()
    return s


def together_events(session):
    return session.exec(select(FeedEvent).where(FeedEvent.type == "together")).all()


def _payload(ev):
    return json.loads(ev.payload_json)


def test_auto_match_creates_feed_event(session, addon, season):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)

    [ts] = sessions(session)
    [ev] = together_events(session)
    assert ts.feed_event_id == ev.id
    assert ev.user_id is None
    assert ev.season_year == 2026
    p = _payload(ev)
    assert p["session_id"] == ts.id
    assert {x["display_name"] for x in p["participants"]} == {"Erik", "Anna"}
    assert {x["user_id"] for x in p["participants"]} == {erik.id, anna.id}
    assert p["km_together"] == pytest.approx(5.0, abs=0.1)
    assert p["share"] == pytest.approx(1.0, abs=0.03)
    assert set(p["category"]) == {"name", "icon", "color"}
    assert together.is_real(session, ts) is True


def test_feed_event_category_from_earliest_confirmed_activity(session, addon, season):
    """Maßgeblich ist Datum + Startzeit, nicht die Import-Reihenfolge."""
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    rad = make_category(session, name="Rad")
    lauf = make_category(session, name="Lauf")
    e = run(session, erik, category=rad)  # zuerst importiert, startet aber später
    e.start_time = time(9, 5)
    a = run(session, anna, category=lauf)
    a.start_time = time(9, 0)
    session.add_all([e, a])
    session.commit()
    together.match_activity(session, a)
    [ev] = together_events(session)
    assert _payload(ev)["category"]["name"] == "Lauf"


def test_third_person_updates_event(session, addon, season):
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    [ev] = together_events(session)
    ev_id = ev.id

    t = run(session, tom)
    together.match_activity(session, t)
    [ev] = together_events(session)
    assert ev.id == ev_id
    names = [x["display_name"] for x in _payload(ev)["participants"]]
    assert sorted(names) == ["Anna", "Erik", "Tom"]


def test_decline_removes_event(session, addon, season):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    [ev] = together_events(session)
    session.add(FeedReaction(event_id=ev.id, user_id=erik.id, emoji="🔥"))
    session.commit()

    p_anna = together.participation_for(session, a.id)
    together.decline(session, p_anna)

    assert together_events(session) == []
    assert session.exec(select(FeedReaction)).all() == []
    [ts] = sessions(session)
    assert ts.feed_event_id is None
    assert together.is_real(session, ts) is False
    p_anna = together.participation_for(session, a.id)
    assert p_anna.status == "declined"
    assert p_anna.responded_at is not None
    assert len(parts(session)) == 2


def _suggested_pair(session):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik, points=path([("N", 4.5)]), km=4.5)
    a = run(session, anna, points=path([("N", 1.8), ("E", 2.7)]), km=4.5)
    together.match_activity(session, a)
    assert all(p.status == "suggested" for p in parts(session))
    return e, a


def test_suggestion_confirmed_by_both_becomes_real(session, addon, season):
    e, a = _suggested_pair(session)
    [ts] = sessions(session)
    assert together_events(session) == []

    together.confirm(session, together.participation_for(session, e.id))
    assert together.is_real(session, ts) is False
    assert together_events(session) == []
    assert together.participation_for(session, e.id).responded_at is not None

    together.confirm(session, together.participation_for(session, a.id))
    assert together.is_real(session, ts) is True
    [ev] = together_events(session)
    assert ts.feed_event_id == ev.id
    assert ts.km_together > 0


def _age(session, p, days):
    p.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    session.add(p)
    session.commit()


def test_suggestion_expires_after_14_days(session, addon, season):
    e, a = _suggested_pair(session)
    pe, pa = together.participation_for(session, e.id), together.participation_for(session, a.id)
    _age(session, pe, 15)
    _age(session, pa, 13)

    together.expire_suggestions(session)
    assert together.participation_for(session, e.id).status == "declined"
    assert together.participation_for(session, a.id).status == "suggested"


def test_expire_suggestions_with_explicit_now(session, addon, season):
    e, a = _suggested_pair(session)
    for p in parts(session):
        _age(session, p, 0)
    later = datetime.now(timezone.utc) + timedelta(days=15)
    together.expire_suggestions(session, now=later)
    assert all(p.status == "declined" for p in parts(session))


def test_expire_leaves_confirmed_alone(session, addon, season):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    for p in parts(session):
        _age(session, p, 30)
    together.expire_suggestions(session)
    assert all(p.status == "confirmed" for p in parts(session))
    assert len(together_events(session)) == 1


def test_delete_activity_dissolves_session(session, addon, season):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    [ts] = sessions(session)
    ts_id = ts.id

    activity_delete.delete_activity(session, a, ignore_strava=False)
    assert together.participation_for(session, a.id) is None
    assert together_events(session) == []
    ts = session.get(TrainingSession, ts_id)
    assert ts is not None and ts.feed_event_id is None
    assert [p.user_id for p in parts(session)] == [erik.id]

    activity_delete.delete_activity(session, e, ignore_strava=False)
    assert parts(session) == []
    assert sessions(session) == []


def test_remove_activity_without_participation_is_noop(session, addon, season):
    erik = make_user(session, "erik")
    e = run(session, erik)
    together.remove_activity(session, e.id)
    assert sessions(session) == []


def test_backfill_match_without_feed_event(session, addon, season):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a, emit_feed=False)
    [ts] = sessions(session)
    assert together.is_real(session, ts) is True
    assert ts.feed_event_id is None
    assert together_events(session) == []


def test_real_session_triggers_check_unlocks(session, addon, season, monkeypatch):
    from app.services import achievements

    calls = []
    monkeypatch.setattr(achievements, "check_unlocks", lambda s, uid: calls.append(uid))
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)
    assert sorted(set(calls)) == sorted([erik.id, anna.id])


def test_session_merge_removes_younger_event(session, addon, season):
    erik, anna, tom, lisa, max_ = (
        make_user(session, n) for n in ("erik", "anna", "tom", "lisa", "max")
    )
    run(session, erik, points=path([("N", 5.0)]))
    a = run(session, anna, points=path([("N", 5.0)]))
    together.match_activity(session, a)
    east_start = (ORIGIN[0] + 5.0 / _KM_PER_DEG_LAT, ORIGIN[1])
    run(session, tom, points=path([("E", 5.0)], start=east_start))
    lisa_act = run(session, lisa, points=path([("E", 5.0)], start=east_start))
    together.match_activity(session, lisa_act)
    assert len(together_events(session)) == 2
    s1, s2 = sorted(sessions(session), key=lambda s: s.id)
    s1_event = s1.feed_event_id

    m = run(session, max_, points=path([("N", 5.0), ("E", 5.0)]), km=10.0)
    together.match_activity(session, m)

    [ev] = together_events(session)
    [ts] = sessions(session)
    assert ev.id == s1_event == ts.feed_event_id
    assert len(_payload(ev)["participants"]) == 5


# --- Fix-Runde 1 (Task 8) -------------------------------------------------------

TOM_PARTIAL = path([("N", 2.0), ("E", 3.0)])  # 2 km gemeinsam, Anteil 0,4 → Vorschlag


def _backfilled_real_with_suggested_tom(session):
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a, emit_feed=False)
    t = run(session, tom, points=TOM_PARTIAL)
    together.match_activity(session, t, emit_feed=False)
    pt = together.participation_for(session, t.id)
    assert pt is not None and pt.status == "suggested"
    [ts] = sessions(session)
    assert together.is_real(session, ts) and ts.feed_event_id is None
    return t


def test_backfilled_session_no_event_after_decline(session, addon, season):
    t = _backfilled_real_with_suggested_tom(session)
    together.decline(session, together.participation_for(session, t.id))
    assert together_events(session) == []


def test_backfilled_session_no_event_after_expiry(session, addon, season):
    t = _backfilled_real_with_suggested_tom(session)
    _age(session, together.participation_for(session, t.id), 15)
    together.expire_suggestions(session)
    assert together.participation_for(session, t.id).status == "declined"
    assert together_events(session) == []


def test_backfilled_session_no_event_when_third_confirms(session, addon, season):
    t = _backfilled_real_with_suggested_tom(session)
    together.confirm(session, together.participation_for(session, t.id))
    assert together.participation_for(session, t.id).status == "confirmed"
    assert together_events(session) == []


def test_backfilled_session_no_event_on_live_rematch(session, addon, season):
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    e = run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a, emit_feed=False)
    together.match_activity(session, e)  # Update-Webhook, live
    assert together_events(session) == []


def _boom(*a, **kw):
    raise RuntimeError("Achievement kaputt")


def test_check_unlocks_failure_does_not_break_matching(session, addon, season, monkeypatch):
    from app.services import achievements

    monkeypatch.setattr(achievements, "check_unlocks", _boom)
    calls = _record_notify(monkeypatch)
    erik, anna = make_user(session, "erik"), make_user(session, "anna")
    run(session, erik)
    a = run(session, anna)
    together.match_activity(session, a)  # wirft nicht

    session.rollback()  # nur Committetes zählt
    assert len(sessions(session)) == 1
    assert len(parts(session)) == 2
    assert len(together_events(session)) == 1
    assert sorted(calls) == sorted([(erik.id, "together_auto"), (anna.id, "together_auto")])


def test_check_unlocks_failure_does_not_break_delete(session, addon, season, monkeypatch):
    from app.services import achievements

    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    run(session, erik)
    run(session, anna)
    t = run(session, tom)
    together.match_activity(session, t)
    monkeypatch.setattr(achievements, "check_unlocks", _boom)
    t_id = t.id

    activity_delete.delete_activity(session, t, ignore_strava=False)
    session.rollback()
    assert session.get(Activity, t_id) is None
    assert together.participation_for(session, t_id) is None
    assert len(parts(session)) == 2


def test_merge_removes_dropped_event_reactions(session, addon, season):
    erik, anna, tom, lisa, max_ = (
        make_user(session, n) for n in ("erik", "anna", "tom", "lisa", "max")
    )
    run(session, erik, points=path([("N", 5.0)]))
    a = run(session, anna, points=path([("N", 5.0)]))
    together.match_activity(session, a)
    east_start = (ORIGIN[0] + 5.0 / _KM_PER_DEG_LAT, ORIGIN[1])
    run(session, tom, points=path([("E", 5.0)], start=east_start))
    lisa_act = run(session, lisa, points=path([("E", 5.0)], start=east_start))
    together.match_activity(session, lisa_act)
    s1, s2 = sorted(sessions(session), key=lambda s: s.id)
    session.add(FeedReaction(event_id=s1.feed_event_id, user_id=erik.id, emoji="🔥"))
    session.add(FeedReaction(event_id=s2.feed_event_id, user_id=tom.id, emoji="👏"))
    session.commit()
    s1_event = s1.feed_event_id

    m = run(session, max_, points=path([("N", 5.0), ("E", 5.0)]), km=10.0)
    together.match_activity(session, m)

    [r] = session.exec(select(FeedReaction)).all()
    assert r.event_id == s1_event and r.emoji == "🔥"


def test_delete_from_three_person_session_updates_payload(session, addon, season):
    erik, anna, tom = (make_user(session, n) for n in ("erik", "anna", "tom"))
    run(session, erik)
    run(session, anna)
    t = run(session, tom)
    together.match_activity(session, t)
    [ev] = together_events(session)
    ev_id = ev.id
    assert len(_payload(ev)["participants"]) == 3

    activity_delete.delete_activity(session, t, ignore_strava=False)
    [ev] = together_events(session)
    assert ev.id == ev_id
    assert sorted(x["display_name"] for x in _payload(ev)["participants"]) == ["Anna", "Erik"]
