"""Tests für backend/app/services/together_geo.py (pure Geo-Hilfsfunktionen)."""

import math
from datetime import datetime, timedelta

import pytest

from app.services.together_geo import (
    covered_km,
    decode_polyline,
    route_overlap,
    time_overlap_s,
    times_overlap,
)

_R = 6371000.0


def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lng1 = p1
    lat2, lng2 = p2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(a)) / 1000.0


def _route_length_km(points: list[tuple[float, float]]) -> float:
    return sum(_haversine_km(p, q) for p, q in zip(points, points[1:]))


def _line_north(
    lat0: float = 48.0, lng0: float = 11.0, n: int = 50, step_m: float = 100.0
) -> list[tuple[float, float]]:
    """Gerade Linie nach Norden ab (lat0, lng0), Punkte alle ~step_m Meter."""
    points = []
    for i in range(n):
        d_lat_deg = math.degrees((step_m * i) / _R)
        points.append((lat0 + d_lat_deg, lng0))
    return points


def _shift_east(
    points: list[tuple[float, float]], offset_m: float
) -> list[tuple[float, float]]:
    """Verschiebt jeden Punkt um offset_m Meter nach Osten (lokal via cos(lat))."""
    shifted = []
    for lat, lng in points:
        d_lng_deg = math.degrees(offset_m / (_R * math.cos(math.radians(lat))))
        shifted.append((lat, lng + d_lng_deg))
    return shifted


def test_decode_google_reference():
    result = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    expected = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    assert len(result) == len(expected)
    for (lat, lng), (elat, elng) in zip(result, expected):
        assert lat == pytest.approx(elat, abs=1e-5)
        assert lng == pytest.approx(elng, abs=1e-5)


def test_decode_broken_raises():
    with pytest.raises(ValueError):
        decode_polyline("_p~iF~")


def test_identical_route_full_overlap():
    line = _line_north()
    dist = _route_length_km(line)
    km, share = route_overlap(line, line, dist, dist)
    assert km == pytest.approx(4.9, abs=0.1)
    assert share == pytest.approx(1.0, abs=0.01)


def test_half_route():
    line = _line_north()
    half = line[: len(line) // 2]
    dist_a = _route_length_km(line)
    dist_b = _route_length_km(half)
    km, share = route_overlap(line, half, dist_a, dist_b)
    assert km == pytest.approx(2.45, abs=0.1)
    assert share == pytest.approx(1.0, abs=0.01)
    assert covered_km(line, half) == pytest.approx(2.45, abs=0.1)


def test_parallel_street_100m_no_overlap():
    line = _line_north()
    shifted = _shift_east(line, 100.0)
    assert covered_km(line, shifted) == 0.0


def test_parallel_30m_counts():
    line = _line_north()
    shifted = _shift_east(line, 30.0)
    dist = _route_length_km(line)
    km, _share = route_overlap(line, shifted, dist, dist)
    assert km == pytest.approx(4.9, abs=0.1)


def test_reversed_route_full_overlap():
    line = _line_north()
    reversed_line = list(reversed(line))
    dist = _route_length_km(line)
    _km, share = route_overlap(line, reversed_line, dist, dist)
    assert share == pytest.approx(1.0, abs=0.01)


def test_times_overlap():
    start = datetime(2026, 1, 1, 10, 0, 0)

    # Gleiche Startzeit, gleiche Dauer -> klarer Overlap
    assert times_overlap(start, 3000, start, 3000) is True

    # B startet 20 Minuten nach Ende von A -> kein Overlap
    later = start + timedelta(seconds=3000 + 1200)
    assert times_overlap(start, 3000, later, 3000) is False

    # B (900s) komplett innerhalb A (3000s)
    inside = start + timedelta(seconds=1000)
    assert times_overlap(start, 3000, inside, 900) is True

    # Nur 5 Minuten (300s) Overlap bei 3000s/3000s -> unter beiden Schwellen
    short_overlap_start = start + timedelta(seconds=3000 - 300)
    assert times_overlap(start, 3000, short_overlap_start, 3000) is False


def test_time_overlap_s_naive_datetimes():
    start_a = datetime(2026, 1, 1, 10, 0, 0)
    start_b = datetime(2026, 1, 1, 10, 5, 0)
    assert time_overlap_s(start_a, 3000, start_b, 3000) == pytest.approx(2700.0)


def test_times_overlap_min_zero_only_600s_rule():
    start = datetime(2026, 1, 1, 10, 0, 0)
    # elapsed_b == 0 -> min == 0, nur die 600s-Regel darf greifen, Overlap hier 0
    assert times_overlap(start, 3000, start, 0) is False
