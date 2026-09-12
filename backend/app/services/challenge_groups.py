"""Group challenges (spec 2026-09-12): seeding list, draw, group editing.

Groups live in Challenge.groups_json. The pure aggregation of a group's
standing (group_standings) sits in services/challenges.py next to the
per-person standings so that freezing and the feed can use it without a
circular import; this module builds on top of that.
"""

from datetime import date as date_type
from datetime import timedelta

from sqlmodel import Session, select

from ..models import Challenge, User
from . import challenges as svc
from .factors import FactorResolver

GROUP_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class TooFewPeople(ValueError):
    """Fewer people in the pool than groups — 422."""


class InvalidGroups(ValueError):
    """An edited group list breaks a rule — 422 with the message."""


def default_name(index: int) -> str:
    """0 → 'Gruppe A', 25 → 'Gruppe Z', 26 → 'Gruppe 27'."""
    if index < len(GROUP_LETTERS):
        return f"Gruppe {GROUP_LETTERS[index]}"
    return f"Gruppe {index + 1}"


def _active_ids(session: Session) -> set[int]:
    return {u.id for u in session.exec(select(User).where(User.is_active)).all()}


def pool(session: Session, ch: Challenge) -> list[int]:
    """Who can be drawn: auto = every active user, opt_in = joined and active."""
    return svc.eligible_ids(session, ch)


def seeding_value(session: Session, user_id: int, ch: Challenge, heute: date_type) -> float:
    """The challenge's own metric over the last seeding_days days up to and
    including yesterday. Never uses User.km_factor."""
    bis = heute - timedelta(days=1)
    von = heute - timedelta(days=ch.seeding_days)
    rows = svc.rows_between(session, user_id, ch, von, bis)
    if ch.metric == "anzahl":
        return float(len(rows))
    if ch.metric == "mm":
        resolver = FactorResolver.load(session)
        return round(sum(resolver.mm(a) for a, _ in rows), 2)
    raise ValueError(f"Unbekannte Metrik: {ch.metric}")


def seeding(
    session: Session, ch: Challenge, heute: date_type, user_ids: list[int] | None = None
) -> list[tuple[int, float]]:
    """(user_id, value) sorted by value desc, ties by user_id. Defaults to the pool."""
    ids = pool(session, ch) if user_ids is None else user_ids
    values = [(uid, seeding_value(session, uid, ch, heute)) for uid in ids]
    values.sort(key=lambda t: (-t[1], t[0]))
    return values
