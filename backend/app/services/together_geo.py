"""Reine Geo-Hilfsfunktionen für den Together-Abgleich (PR 2).

Keine DB-Zugriffe, keine Imports aus app.models — dieses Modul ist bewusst
unabhängig testbar und wird später von einem Matching-Service (Task 7)
verwendet, der `decode_polyline`, `times_overlap` und `route_overlap`
aufruft.

`time_overlap_s` funktioniert sowohl mit naiven als auch mit
zeitzonen-bewussten Datetimes, solange beide Argumente von der gleichen Art
sind (Strava-Zeiten aus SQLite sind naiv UTC).
"""

import math
from datetime import datetime, timedelta

_EARTH_RADIUS_M = 6371000.0


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Dekodiert eine Google-Encoded-Polyline (Präzision 5) zu (lat, lng)."""
    coordinates: list[tuple[float, float]] = []
    index = 0
    length = len(encoded)
    lat = 0
    lng = 0

    while index < length:
        lat_delta = _decode_signed_value(encoded, index, length)
        lat += lat_delta[0]
        index = lat_delta[1]

        lng_delta = _decode_signed_value(encoded, index, length)
        lng += lng_delta[0]
        index = lng_delta[1]

        coordinates.append((lat / 1e5, lng / 1e5))

    return coordinates


def _decode_signed_value(encoded: str, index: int, length: int) -> tuple[int, int]:
    shift = 0
    result = 0
    while True:
        if index >= length:
            raise ValueError("Kaputter Polyline-String: unerwartetes Ende")
        byte = ord(encoded[index]) - 63
        index += 1
        result |= (byte & 0x1F) << shift
        shift += 5
        if byte < 0x20:
            break
    delta = ~(result >> 1) if (result & 1) else (result >> 1)
    return delta, index


def time_overlap_s(
    start_a: datetime, elapsed_a: int, start_b: datetime, elapsed_b: int
) -> float:
    """Überlappung der Zeitfenster [start, start+elapsed) in Sekunden (>= 0)."""
    end_a = start_a + timedelta(seconds=elapsed_a)
    end_b = start_b + timedelta(seconds=elapsed_b)
    latest_start = max(start_a, start_b)
    earliest_end = min(end_a, end_b)
    overlap = (earliest_end - latest_start).total_seconds()
    return max(overlap, 0.0)


def times_overlap(
    start_a: datetime, elapsed_a: int, start_b: datetime, elapsed_b: int
) -> bool:
    """True, wenn Overlap >= 600s oder >= 0.5 * min(elapsed_a, elapsed_b).

    Bei min(elapsed_a, elapsed_b) == 0 gilt nur die 600s-Regel.
    """
    overlap = time_overlap_s(start_a, elapsed_a, start_b, elapsed_b)
    if overlap >= 600:
        return True
    shortest = min(elapsed_a, elapsed_b)
    if shortest == 0:
        return False
    return overlap >= 0.5 * shortest


def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lng1 = p1
    lat2, lng2 = p2
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a)) / 1000.0


def _project_xy(
    point: tuple[float, float], origin: tuple[float, float]
) -> tuple[float, float]:
    """Lokale equirektangulare Projektion von `point` relativ zu `origin`."""
    lat, lng = point
    lat0, lng0 = origin
    x = math.radians(lng - lng0) * math.cos(math.radians(lat0)) * _EARTH_RADIUS_M
    y = math.radians(lat - lat0) * _EARTH_RADIUS_M
    return x, y


def _point_segment_distance_m(
    point: tuple[float, float],
    seg_p: tuple[float, float],
    seg_q: tuple[float, float],
) -> float:
    """Minimale Distanz (Meter) von `point` zum Segment seg_p-seg_q.

    Projektion erfolgt lokal um `point` (Ursprung der equirektangularen
    Projektion), klassische Punkt-zu-Segment-Projektion mit Klemmung auf
    [0, 1].
    """
    origin = point
    px, py = _project_xy(point, origin)  # (0, 0)
    ax, ay = _project_xy(seg_p, origin)
    bx, by = _project_xy(seg_q, origin)

    dx, dy = bx - ax, by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0:
        return math.hypot(px - ax, py - ay)

    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    closest_x = ax + t * dx
    closest_y = ay + t * dy
    return math.hypot(px - closest_x, py - closest_y)


def covered_km(
    a: list[tuple[float, float]], b: list[tuple[float, float]], radius_m: float = 50.0
) -> float:
    """Summe (km) der Segmente von A, deren Mittelpunkt <= radius_m von
    einem Segment von B entfernt liegt. B mit < 2 Punkten -> 0."""
    if len(b) < 2:
        return 0.0

    total_km = 0.0
    for p, q in zip(a, a[1:]):
        midpoint = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        min_dist_m = min(
            _point_segment_distance_m(midpoint, b_p, b_q)
            for b_p, b_q in zip(b, b[1:])
        )
        if min_dist_m <= radius_m:
            total_km += _haversine_km(p, q)

    return total_km


def route_overlap(
    a: list[tuple[float, float]],
    b: list[tuple[float, float]],
    dist_a_km: float,
    dist_b_km: float,
) -> tuple[float, float]:
    """(km_together, share): km_together = min(covered_km(a,b), covered_km(b,a)),
    share = km_together / min(dist_a_km, dist_b_km) (0, wenn min == 0)."""
    km_together = min(covered_km(a, b), covered_km(b, a))
    shortest_dist = min(dist_a_km, dist_b_km)
    share = km_together / shortest_dist if shortest_dist else 0.0
    return km_together, share
