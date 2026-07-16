from datetime import date

from app.models import Season
from app.services.season_window import (
    current_season,
    in_window,
    season_window,
    window_bounds,
)


def test_season_window_kalenderjahr_ohne_daten():
    s = Season(year=2025, goal_km=1000)
    assert season_window(s) == (date(2025, 1, 1), date(2025, 12, 31))


def test_season_window_offen_mit_start_ohne_ende():
    s = Season(year=2026, goal_km=1000, start_date=date(2026, 7, 20))
    assert season_window(s) == (date(2026, 1, 1), None)


def test_season_window_mit_ende():
    s = Season(
        year=2026, goal_km=1000,
        start_date=date(2026, 7, 20), end_date=date(2027, 5, 16),
    )
    assert season_window(s) == (date(2026, 1, 1), date(2027, 5, 16))


def test_in_window():
    w = (date(2026, 1, 1), date(2027, 5, 16))
    assert in_window(date(2027, 1, 15), w) is True
    assert in_window(date(2027, 5, 16), w) is True  # Endtag zählt noch
    assert in_window(date(2027, 5, 17), w) is False
    assert in_window(date(2025, 12, 31), w) is False
    assert in_window(date(2027, 12, 1), (date(2026, 1, 1), None)) is True  # offen


def test_window_bounds_ohne_season_kalenderjahr(session):
    assert window_bounds(session, 2031) == (date(2031, 1, 1), date(2031, 12, 31))


def _add_season(session, **kw):
    s = Season(goal_km=1000, milestones_json="[]", **kw)
    session.add(s)
    session.commit()
    return s


def test_current_season_jahresuebergreifend(session):
    _add_season(session, year=2026,
                start_date=date(2026, 7, 20), end_date=date(2027, 5, 16))
    assert current_season(session, today=date(2027, 2, 1)).year == 2026


def test_current_season_nach_ende_zuletzt_begonnene(session):
    _add_season(session, year=2026,
                start_date=date(2026, 7, 20), end_date=date(2027, 5, 16))
    assert current_season(session, today=date(2027, 6, 1)).year == 2026


def test_current_season_countdown_naechste(session):
    _add_season(session, year=2028, start_date=date(2028, 7, 20))
    assert current_season(session, today=date(2027, 12, 1)).year == 2028


def test_current_season_bevorzugt_enthaltendes_fenster(session):
    _add_season(session, year=2025)  # Kalenderjahr 2025
    _add_season(session, year=2026, start_date=date(2026, 7, 20))
    assert current_season(session, today=date(2026, 8, 1)).year == 2026
    assert current_season(session, today=date(2025, 3, 1)).year == 2025


def test_current_season_leer(session):
    assert current_season(session) is None
