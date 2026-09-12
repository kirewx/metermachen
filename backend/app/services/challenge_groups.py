"""Group challenges (spec 2026-09-12): seeding list, draw, group editing.

Groups live in Challenge.groups_json. The pure aggregation of a group's
standing (group_standings) sits in services/challenges.py next to the
per-person standings so that freezing and the feed can use it without a
circular import; this module builds on top of that.
"""

import random
from datetime import date as date_type
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..models import Challenge, ChallengeParticipant, utcnow
from . import challenges as svc
from .factors import FactorResolver

GROUP_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


class TooFewPeople(ValueError):
    """Fewer people in the pool than groups — 422."""


class InvalidGroups(ValueError):
    """A group setup breaks a rule (edited list or group_count) — 422 with the message."""


def default_name(index: int) -> str:
    """0 → 'Gruppe A', 25 → 'Gruppe Z', 26 → 'Gruppe 27'."""
    if index < len(GROUP_LETTERS):
        return f"Gruppe {GROUP_LETTERS[index]}"
    return f"Gruppe {index + 1}"


def pool(session: Session, ch: Challenge) -> list[int]:
    """Who can be drawn: auto = every active user, opt_in = joined and active."""
    return svc.eligible_ids(session, ch)


def seeding_value(
    session: Session,
    user_id: int,
    ch: Challenge,
    heute: date_type,
    *,
    resolver: FactorResolver | None = None,
    cats: dict | None = None,
) -> float:
    """The challenge's own metric over the last seeding_days days up to and
    including yesterday. Never uses User.km_factor. resolver and cats let a
    loop over many users load the factors and categories only once."""
    bis = heute - timedelta(days=1)
    von = heute - timedelta(days=ch.seeding_days)
    rows = svc.rows_between(session, user_id, ch, von, bis, cats=cats)
    if ch.metric == "anzahl":
        return float(len(rows))
    if ch.metric == "mm":
        if resolver is None:
            resolver = FactorResolver.load(session)
        return round(sum(resolver.mm(a) for a, _ in rows), 2)
    raise ValueError(f"Unbekannte Metrik: {ch.metric}")


def seeding(
    session: Session, ch: Challenge, heute: date_type, user_ids: list[int] | None = None
) -> list[tuple[int, float]]:
    """(user_id, value) sorted by value desc, ties by user_id. Defaults to the pool."""
    ids = pool(session, ch) if user_ids is None else user_ids
    cats = svc.category_map(session)
    resolver = FactorResolver.load(session) if ch.metric == "mm" else None
    values = [
        (uid, seeding_value(session, uid, ch, heute, resolver=resolver, cats=cats))
        for uid in ids
    ]
    values.sort(key=lambda t: (-t[1], t[0]))
    return values


def draw(
    session: Session,
    ch: Challenge,
    heute: date_type,
    jetzt: datetime | None = None,
    rng: random.Random | None = None,
) -> list[dict]:
    """Seeded random draw. Pots of group_count by seeding rank; inside a pot
    the assignment to groups is random; the partial last pot goes to random
    distinct groups, so sizes differ by at most one. Existing names are kept
    by group id. Members of a previous draw are discarded; only the current
    pool is assigned. Writes groups_json / groups_drawn_at on ch but does NOT
    commit — the caller decides (create wants to validate before commit)."""
    if rng is None:
        rng = random.Random()
    n = ch.group_count or 0
    if n < 2:
        raise InvalidGroups("Mindestens 2 Gruppen")
    order = [uid for uid, _ in seeding(session, ch, heute)]
    if len(order) < n:
        raise TooFewPeople("Weniger Personen als Gruppen")
    names = {g["id"]: g["name"] for g in svc.groups(ch)}
    result = [
        {"id": i + 1, "name": names.get(i + 1, default_name(i)), "member_ids": []}
        for i in range(n)
    ]
    for start in range(0, len(order), n):
        pot = order[start:start + n]
        targets = rng.sample(range(n), len(pot))
        for uid, gi in zip(pot, targets):
            result[gi]["member_ids"].append(uid)
    svc.set_groups(ch, result)
    ch.groups_drawn_at = jetzt or utcnow()
    return result


def _joined_ids(session: Session, ch: Challenge) -> set[int]:
    rows = session.exec(
        select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == ch.id)
    ).all()
    return {r.user_id for r in rows}


def validate_groups(session: Session, ch: Challenge, raw: list[dict]) -> list[dict]:
    """Normalise and check an edited group list. Returns the clean list or
    raises InvalidGroups with a German message for the admin."""
    if not ch.team_mode or not ch.group_count:
        raise InvalidGroups("Keine Gruppen-Challenge")
    if len(raw) != ch.group_count:
        raise InvalidGroups(f"Es müssen genau {ch.group_count} Gruppen sein")
    active = svc.active_ids(session)
    seen_ids: set[int] = set()
    seen_users: set[int] = set()
    clean = []
    for g in raw:
        gid = int(g["id"])
        name = str(g.get("name", "")).strip()
        if gid in seen_ids:
            raise InvalidGroups("Doppelte Gruppen-ID")
        seen_ids.add(gid)
        if not name:
            raise InvalidGroups("Jede Gruppe braucht einen Namen")
        members = [int(uid) for uid in g.get("member_ids", [])]
        if not members:
            raise InvalidGroups(f"{name} ist leer")
        for uid in members:
            if uid in seen_users:
                raise InvalidGroups("Eine Person steht mehrfach in den Gruppen")
            if uid not in active:
                raise InvalidGroups("Unbekannte oder inaktive Person")
            seen_users.add(uid)
        clean.append({"id": gid, "name": name, "member_ids": members})
    if seen_ids != set(range(1, ch.group_count + 1)):
        raise InvalidGroups(f"Gruppen-IDs müssen 1 bis {ch.group_count} sein")
    return clean


def save_groups(session: Session, ch: Challenge, raw: list[dict]) -> list[dict]:
    """Validate, store, and in opt_in mode make every placed person a
    participant (placing someone counts as joining). Commits."""
    clean = validate_groups(session, ch, raw)
    svc.set_groups(ch, clean)
    if ch.join_mode == "opt_in":
        joined = _joined_ids(session, ch)
        for g in clean:
            for uid in g["member_ids"]:
                if uid not in joined:
                    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=uid))
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return clean
