"""Challenges: Metriken, Stand, Lebenszyklus (Spec 2026-08-04).

Der Stand wird zur Lesezeit aus den Activities gerechnet, solange die
Challenge laeuft — genau wie compute_comparison. Dadurch ziehen Strava-
Nachzuegler und Korrekturen automatisch mit und es braucht keinen Cron.
Erst beim Einfrieren wird das Ergebnis in result_json festgeschrieben.

Alle Metriken rechnen ohne User.km_factor: das Admin-Handicap gilt nur im
Saison-Ranking, eine 300-MM-Huerde soll fuer alle dieselbe Huerde sein.

Group state (Spec 2026-09-12) lives in Challenge.groups_json. The pure group
helpers and group_standings live in this module rather than a separate one so
that services/challenge_groups.py (seeding/draw, added next) can import from
here without a circular import.
"""

import json
from collections import defaultdict
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from datetime import time as time_type

from sqlmodel import Session, select

from ..models import Activity, Category, Challenge, ChallengeParticipant, User
from . import feed
from .factors import FactorResolver

# Karenz nach Challenge-Ende: Einfrieren erst am Folgetag um 06:00 deutscher
# Zeit. Deckt einen ausstehenden Strava-Sync und eine Aktivitaet kurz vor
# Mitternacht ab, die erst am naechsten Morgen eingetragen wird.
KARENZ_STUNDE = 6
# Fester Sommerzeit-Offset wie in services/feed.py und services/achievements.py.
_MESZ = timezone(timedelta(hours=2))


def category_ids(ch: Challenge) -> list[int]:
    """Leere Liste = alle Kategorien."""
    return json.loads(ch.category_ids_json or "[]")


def groups(ch: Challenge) -> list[dict]:
    """[{"id": 1, "name": "Gruppe A", "member_ids": [3, 7]}] — empty until drawn.
    Returns a fresh copy parsed from JSON; write changes back with set_groups."""
    return json.loads(ch.groups_json or "[]")


def set_groups(ch: Challenge, gruppen: list[dict]) -> None:
    """Only changes the in-memory model; the caller persists (session.add + commit)."""
    ch.groups_json = json.dumps(gruppen)


def group_member_ids(ch: Challenge) -> list[int]:
    """All member ids across all groups, deduped while preserving order. A person
    belongs to at most one group (validate_groups enforces it later); the dedupe
    here is a safety net for the standings path."""
    return list(dict.fromkeys(uid for g in groups(ch) for uid in g["member_ids"]))


def remove_group_member(ch: Challenge, user_id: int) -> None:
    """Used when a person leaves a planned group challenge. No-op if absent.
    Only changes the in-memory model; the caller persists (session.add + commit)."""
    gruppen = groups(ch)
    for g in gruppen:
        g["member_ids"] = [uid for uid in g["member_ids"] if uid != user_id]
    set_groups(ch, gruppen)


def group_of(ch: Challenge, user_id: int) -> dict | None:
    """The group containing user_id, or None. Returns a fresh copy parsed from
    JSON; write changes back with set_groups."""
    return next((g for g in groups(ch) if user_id in g["member_ids"]), None)


def rows_between(
    session: Session, user_id: int, ch: Challenge, von: date_type, bis: date_type
) -> list[tuple[Activity, Category]]:
    """Activities of the user between von and bis (inclusive), category-filtered
    with the challenge's category list."""
    erlaubt = set(category_ids(ch))
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= von,
            Activity.date <= bis,
        )
    ).all()
    return [
        (a, cats[a.category_id])
        for a in acts
        if a.category_id in cats and (not erlaubt or a.category_id in erlaubt)
    ]


def _rows(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> list[tuple[Activity, Category]]:
    """Challenge window; bis is clamped to period_end."""
    ende = ch.period_end if bis is None else min(ch.period_end, bis)
    return rows_between(session, user_id, ch, ch.period_start, ende)


def metric_mm(session: Session, user_id: int, ch: Challenge) -> float:
    resolver = FactorResolver.load(session)
    return round(sum(resolver.mm(a) for a, _ in _rows(session, user_id, ch)), 2)


def metric_anzahl(session: Session, user_id: int, ch: Challenge) -> int:
    return len(_rows(session, user_id, ch))


def per_day(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> dict[date_type, float]:
    """MM je Kalendertag im Zeitraum (Kategorie-gefiltert)."""
    resolver = FactorResolver.load(session)
    tage: dict[date_type, float] = defaultdict(float)
    for a, _ in _rows(session, user_id, ch, bis):
        tage[a.date] += resolver.mm(a)
    return tage


def laengste_serie(
    tage: dict[date_type, float], von: date_type, bis: date_type, min_mm: float
) -> int:
    best = run = 0
    tag = von
    while tag <= bis:
        run = run + 1 if tage.get(tag, 0.0) >= min_mm else 0
        best = max(best, run)
        tag += timedelta(days=1)
    return best


def serie_endend_am(
    tage: dict[date_type, float], von: date_type, bis: date_type, min_mm: float
) -> int:
    """Laenge der Serie, die genau am Tag `bis` endet. 0, wenn `bis` nicht zaehlt."""
    run = 0
    tag = bis
    while tag >= von and tage.get(tag, 0.0) >= min_mm:
        run += 1
        tag -= timedelta(days=1)
    return run


def metric_streak(
    session: Session, user_id: int, ch: Challenge, heute: date_type
) -> int:
    bis = min(heute, ch.period_end)
    if bis < ch.period_start:
        return 0
    return laengste_serie(
        per_day(session, user_id, ch, bis), ch.period_start, bis, ch.streak_min_mm
    )


def metric_value(
    session: Session, user_id: int, ch: Challenge, heute: date_type | None = None
) -> float:
    heute = heute or date_type.today()
    if ch.metric == "mm":
        return metric_mm(session, user_id, ch)
    if ch.metric == "anzahl":
        return metric_anzahl(session, user_id, ch)
    if ch.metric == "streak":
        return metric_streak(session, user_id, ch, heute)
    raise ValueError(f"Unbekannte Metrik: {ch.metric}")


def streak_noch_moeglich(
    session: Session, user_id: int, ch: Challenge, heute: date_type
) -> bool:
    """False, sobald das Streak-Ziel rechnerisch nicht mehr erreichbar ist.

    Gilt nur fuer mode='ziel' + metric='streak' — bei mm/anzahl gibt es kein
    Tageslimit, dort ist Unmoeglichkeit nie beweisbar.
    """
    if ch.mode != "ziel" or ch.metric != "streak" or ch.target is None:
        return True
    if heute < ch.period_start:
        return True
    bis = min(heute, ch.period_end)
    tage = per_day(session, user_id, ch, ch.period_end)
    beste = laengste_serie(tage, ch.period_start, bis, ch.streak_min_mm)
    if beste >= ch.target:
        return True
    gestern = min(heute - timedelta(days=1), ch.period_end)
    laufend = (
        serie_endend_am(tage, ch.period_start, gestern, ch.streak_min_mm)
        if gestern >= ch.period_start
        else 0
    )
    resttage = max((ch.period_end - heute).days + 1, 0)
    return laufend + resttage >= ch.target


def _active_ids(session: Session) -> set[int]:
    return {u.id for u in session.exec(select(User).where(User.is_active)).all()}


def eligible_ids(session: Session, ch: Challenge) -> list[int]:
    """Active users who may take part: everyone for join_mode 'auto',
    the joined ones for 'opt_in'. Group membership is not considered here."""
    aktive = _active_ids(session)
    if ch.join_mode == "auto":
        return sorted(aktive)
    rows = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id
        )
    ).all()
    return sorted(r.user_id for r in rows if r.user_id in aktive)


def teilnehmer_ids(session: Session, ch: Challenge) -> list[int]:
    """Who is scored. Group challenges: active members of any group. Otherwise
    every eligible user (see eligible_ids). Inactive users drop out in every case."""
    if ch.team_mode:
        aktive = _active_ids(session)
        return sorted(uid for uid in group_member_ids(ch) if uid in aktive)
    return eligible_ids(session, ch)


def _rank(items: list[dict]) -> None:
    """Shared rank on equal value, following rank skipped (1, 2, 2, 4). In place,
    items must already be sorted by value descending."""
    letzter_wert = None
    letzter_rang = 0
    for i, e in enumerate(items, start=1):
        if letzter_wert is not None and e["value"] == letzter_wert:
            e["rank"] = letzter_rang
        else:
            e["rank"] = i
            letzter_rang = i
            letzter_wert = e["value"]


def standings(
    session: Session, ch: Challenge, heute: date_type | None = None
) -> list[dict]:
    """Aktueller Stand, absteigend nach Wert. Gleichstand teilt sich den Rang,
    der Folgerang wird uebersprungen (1, 2, 2, 4)."""
    heute = heute or date_type.today()
    eintraege = [
        {
            "user_id": uid,
            "value": metric_value(session, uid, ch, heute),
            "rank": 0,
            "geschafft": False,
            "nicht_mehr_schaffbar": False,
        }
        for uid in teilnehmer_ids(session, ch)
    ]
    eintraege.sort(key=lambda e: (-e["value"], e["user_id"]))
    _rank(eintraege)

    for e in eintraege:
        if ch.mode == "ziel":
            e["geschafft"] = ch.target is not None and e["value"] >= ch.target
            if not e["geschafft"]:
                e["nicht_mehr_schaffbar"] = not streak_noch_moeglich(
                    session, e["user_id"], ch, heute
                )
        else:
            e["geschafft"] = e["rank"] <= ch.top_n
    return eintraege


def group_standings(ch: Challenge, eintraege: list[dict]) -> list[dict]:
    """Aggregate per-person entries (output of standings()) into groups.
    Pure: members missing from eintraege (inactive) drop out of sum and
    divisor. Value is per head; target is per head. An empty group (no scored
    member) is never geschafft."""
    werte = {e["user_id"]: e["value"] for e in eintraege}
    result = []
    for g in groups(ch):
        members = [
            {"user_id": uid, "value": werte[uid]} for uid in g["member_ids"] if uid in werte
        ]
        members.sort(key=lambda m: (-m["value"], m["user_id"]))
        total = round(sum(m["value"] for m in members), 2)
        result.append(
            {
                "id": g["id"],
                "name": g["name"],
                "member_ids": [m["user_id"] for m in members],
                "size": len(members),
                "sum": total,
                "value": round(total / len(members), 2) if members else 0.0,
                "rank": 0,
                "geschafft": False,
                "members": members,
            }
        )
    result.sort(key=lambda g: (-g["value"], g["id"]))
    _rank(result)
    for g in result:
        if ch.mode == "ziel":
            g["geschafft"] = (
                g["size"] > 0 and ch.target is not None and g["value"] >= ch.target
            )
        else:
            g["geschafft"] = g["size"] > 0 and g["rank"] <= ch.top_n
    return result


def freeze_at(ch: Challenge) -> datetime:
    """UTC-Zeitpunkt, ab dem das Ergebnis feststeht."""
    tag = ch.period_end + timedelta(days=1)
    return datetime.combine(
        tag, time_type(KARENZ_STUNDE, 0), tzinfo=_MESZ
    ).astimezone(timezone.utc)


def ist_vorlaeufig(ch: Challenge, heute: date_type) -> bool:
    """Zeitraum vorbei, Ergebnis aber noch nicht eingefroren."""
    return ch.status == "laufend" and heute > ch.period_end


FROZEN_GROUP_KEYS = ("id", "name", "member_ids", "sum", "value", "rank", "geschafft")


def _einfrieren(session: Session, ch: Challenge, jetzt: datetime, heute: date_type) -> None:
    eintraege = standings(session, ch, heute)
    ergebnis: dict = {
        "entries": [
            {k: e[k] for k in ("user_id", "value", "rank", "geschafft")}
            for e in eintraege
        ],
    }
    gewinner_gruppen_namen: list[str] = []
    if ch.team_mode:
        gruppen = group_standings(ch, eintraege)
        sieger_gruppen = [g for g in gruppen if g["geschafft"]]
        gewinner = [uid for g in sieger_gruppen for uid in g["member_ids"]]
        gewinner_gruppen_namen = [g["name"] for g in sieger_gruppen]
        ergebnis["groups"] = [{k: g[k] for k in FROZEN_GROUP_KEYS} for g in gruppen]
        ergebnis["gewinner_group_ids"] = [g["id"] for g in sieger_gruppen]
    else:
        gewinner = [e["user_id"] for e in eintraege if e["geschafft"]]
    ergebnis["gewinner_ids"] = gewinner
    ch.result_json = json.dumps(ergebnis)
    ch.status = "beendet"
    ch.resolved_at = jetzt
    session.add(ch)
    session.commit()
    feed.challenge_end_event(session, ch, gewinner, gewinner_gruppen_namen)


def resolve_due(session: Session, jetzt: datetime | None = None) -> None:
    """Faellige Statusuebergaenge, lazy beim Request — kein Cron.
    Gleiches Muster wie bets.resolve_due."""
    jetzt = jetzt or datetime.now(timezone.utc)
    heute = jetzt.astimezone(_MESZ).date()

    for ch in session.exec(
        select(Challenge).where(Challenge.status == "geplant").order_by(Challenge.id)
    ).all():
        if ch.team_mode and not groups(ch):
            continue  # a group challenge only starts once the groups are drawn
        if heute >= ch.period_start:
            ch.status = "laufend"
            session.add(ch)
            session.commit()
            feed.challenge_start_event(session, ch)

    for ch in session.exec(
        select(Challenge).where(Challenge.status == "laufend").order_by(Challenge.id)
    ).all():
        if jetzt >= freeze_at(ch):
            _einfrieren(session, ch, jetzt, heute)


def emit_qualified(session: Session, ch: Challenge, eintraege: list[dict]) -> None:
    """Feed event for everyone (or every group) that hit the target. Idempotent."""
    if ch.mode != "ziel" or ch.status != "laufend":
        return
    if ch.team_mode:
        for g in group_standings(ch, eintraege):
            if g["geschafft"]:
                feed.challenge_group_qualified_event(session, ch, g)
        return
    for e in eintraege:
        if e["geschafft"]:
            feed.challenge_qualified_event(session, ch, e["user_id"])


class NichtQualifiziert(ValueError):
    """Sieger steht nicht auf der Liste der Qualifizierten — 422, nicht 409."""


def sieger_id(ch: Challenge) -> int | None:
    return json.loads(ch.result_json or "{}").get("sieger", {}).get("user_id")


def sieger_group_id(ch: Challenge) -> int | None:
    return json.loads(ch.result_json or "{}").get("sieger", {}).get("group_id")


def setze_sieger(
    session: Session,
    ch: Challenge,
    jetzt: datetime,
    *,
    user_id: int | None = None,
    group_id: int | None = None,
) -> None:
    """Record the offline-drawn prize winner: a person, or (group challenges
    only) a whole group. Overwritable — a typo must be correctable."""
    if ch.mode != "ziel":
        raise ValueError("Ranglisten haben ihren Sieger bereits")
    if ch.status != "beendet":
        raise ValueError("Erst nach dem Ende der Challenge")
    ergebnis = json.loads(ch.result_json or "{}")
    gruppe: dict | None = None
    if group_id is not None:
        if not ch.team_mode:
            raise NichtQualifiziert("Diese Challenge hat keine Gruppen")
        if group_id not in ergebnis.get("gewinner_group_ids", []):
            raise NichtQualifiziert("Diese Gruppe hat das Ziel nicht erreicht")
        gruppe = next(g for g in groups(ch) if g["id"] == group_id)
        ergebnis["sieger"] = {"group_id": group_id, "gesetzt_am": jetzt.isoformat()}
    else:
        if user_id not in ergebnis.get("gewinner_ids", []):
            raise NichtQualifiziert("Diese Person hat das Ziel nicht erreicht")
        gruppe = group_of(ch, user_id) if ch.team_mode else None
        ergebnis["sieger"] = {"user_id": user_id, "gesetzt_am": jetzt.isoformat()}
    ch.result_json = json.dumps(ergebnis)
    session.add(ch)
    session.commit()
    feed.challenge_sieger_event(
        session, ch, user_id=user_id if group_id is None else None,
        group_id=gruppe["id"] if gruppe else None,
        gruppe=gruppe["name"] if gruppe else None,
    )
