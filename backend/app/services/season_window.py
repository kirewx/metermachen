"""Season-Fenster: Wertungszeitraum einer Season (Spec Season-Zeitrahmen).

Fensterstart ist immer der 1. Januar des Season-Jahres — Warm-up-Aktivitäten
gehören zum Fenster, start_date trennt nur Warm-up von Challenge.
Fensterende ist end_date; fehlt es, läuft eine Season MIT start_date offen
weiter (Jahreswechsel!), eine OHNE start_date endet am 31.12. (reines
Kalenderjahr-Verhalten wie vor diesem Feature).
"""

from datetime import date as date_type

from sqlmodel import Session, select

from ..models import Season

Window = tuple[date_type, date_type | None]


def season_window(season: Season) -> Window:
    from_date = date_type(season.year, 1, 1)
    if season.end_date is not None:
        return from_date, season.end_date
    if season.start_date is not None:
        return from_date, None
    return from_date, date_type(season.year, 12, 31)


def window_bounds(session: Session, year: int) -> Window:
    """Fenster zum year-Pfadparameter; ohne Season-Zeile: Kalenderjahr."""
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        return date_type(year, 1, 1), date_type(year, 12, 31)
    return season_window(season)


def in_window(d: date_type, window: Window) -> bool:
    from_date, to_date = window
    return d >= from_date and (to_date is None or d <= to_date)


def current_season(session: Session, today: date_type | None = None) -> Season | None:
    """Aktive Season: Fenster enthält heute (bei mehreren: spätester
    Fensterstart); sonst die zuletzt begonnene; sonst die als Nächstes
    beginnende (Countdown-Phase)."""
    today = today or date_type.today()
    seasons = session.exec(select(Season)).all()
    if not seasons:
        return None

    def start(s: Season) -> date_type:
        return season_window(s)[0]

    enthaltend = [s for s in seasons if in_window(today, season_window(s))]
    if enthaltend:
        return max(enthaltend, key=start)
    begonnen = [s for s in seasons if start(s) <= today]
    if begonnen:
        return max(begonnen, key=start)
    return min(seasons, key=start)
