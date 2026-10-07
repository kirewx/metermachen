"""Together-Matching (Spec 2026-10-05 Teil 1, 2.1): Strava-Aktivitäten
verschiedener Mitglieder zu gemeinsamen TrainingSessions zusammenführen."""

import itertools
from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from app import config
from app.models import (
    Activity,
    ActivityTrack,
    SessionParticipant,
    StravaConnection,
    TrainingSession,
)
from app.services import strava, together
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
