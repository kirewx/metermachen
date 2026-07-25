"""Newsfeed: Event-Erzeugung + Rückblicke (Spec 2026-07-25 Teil B).

Events werden an den Schreibpfaden erzeugt (Aktivität, Überholung,
Achievement, Meilenstein); Rückblicke lazy beim Feed-Abruf — gleiches
Muster wie bets.ensure_monthly_tip. Kein Cron.
"""

import json
from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from datetime import time as time_type

from sqlmodel import Session, select

from ..models import (
    AchievementUnlock,
    Activity,
    Category,
    FeedEvent,
    FeedReaction,
    User,
)
from .season_window import current_season, in_window, season_window

REACTION_EMOJIS = ("👏", "🔥", "💪", "😂", "😮")
TOP_N = 5
# Feed-Tage/Rückblick-Grenzen um Mitternacht deutscher Zeit — fester
# Sommerzeit-Offset wie in services/achievements.py und seed.py.
_MESZ = timezone(timedelta(hours=2))


def _emit(session: Session, *, type_: str, user_id: int | None = None,
          activity_id: int | None = None, payload: dict | None = None,
          created_at: datetime | None = None) -> None:
    season = current_season(session)
    if season is None:
        return
    ev = FeedEvent(
        season_year=season.year, type=type_, user_id=user_id,
        activity_id=activity_id, payload_json=json.dumps(payload or {}),
    )
    if created_at is not None:
        ev.created_at = created_at.astimezone(timezone.utc)
    session.add(ev)
    session.commit()


def _activity_payload(act: Activity, cat: Category) -> dict:
    return {
        "category": {"name": cat.name, "icon": cat.icon, "color": cat.color},
        "distance_km": act.distance_km,
        "mm": round(act.distance_km * cat.factor, 2),
        "titel": act.note,
        "datum": act.date.isoformat(),
    }


def activity_event(session: Session, act: Activity) -> None:
    cat = session.get(Category, act.category_id)
    if cat is None:
        return
    _emit(session, type_="activity", user_id=act.user_id, activity_id=act.id,
          payload=_activity_payload(act, cat))


def _challenge_totals(session: Session) -> dict[int, float]:
    """Challenge-MM je aktivem User (Kategorie-Faktor × km_factor, wie
    Rennen-Tab). Leeres Dict, wenn die Challenge nicht läuft."""
    season = current_season(session)
    if season is None or season.start_date is None:
        return {}
    window = season_window(season)
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    totals: dict[int, float] = {uid: 0.0 for uid in users}
    for a in session.exec(
        select(Activity).where(Activity.date >= season.start_date)
    ).all():
        if a.user_id not in users or a.category_id not in cats:
            continue
        if not in_window(a.date, window):
            continue
        totals[a.user_id] += (
            a.distance_km * cats[a.category_id].factor * users[a.user_id].km_factor
        )
    return totals


def challenge_order(session: Session) -> list[int]:
    """Aktive User absteigend nach Challenge-MM; Gleichstand: kleinere ID vorn."""
    totals = _challenge_totals(session)
    return [uid for uid, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]


def challenge_total(session: Session, user_id: int) -> float:
    return _challenge_totals(session).get(user_id, 0.0)


def _rank_change_payloads(
    before: list[int], after: list[int], users: dict[int, User]
) -> list[tuple[int, dict]]:
    """(user_id, payload) je Überholvorgang in den Top 5 — gemeinsame Logik
    für Live-Emission (rank_events) und Feed-Backfill."""
    pos_b = {uid: i for i, uid in enumerate(before)}
    pos_a = {uid: i for i, uid in enumerate(after)}

    def name(uid: int) -> str:
        return users[uid].display_name if uid in users else f"#{uid}"

    out: list[tuple[int, dict]] = []
    for uid, neu in pos_a.items():
        if neu >= TOP_N or uid not in pos_b or neu >= pos_b[uid]:
            continue  # nur Aufsteiger in die/innerhalb der Top 5
        ueberholte = [
            o for o in pos_b
            if o != uid and pos_b[o] < pos_b[uid] and pos_a.get(o, len(pos_a)) > neu
        ]
        for o in ueberholte:
            out.append((uid, {
                "name": name(uid),
                "ueberholt_user_id": o,
                "ueberholt_name": name(o),
                "neuer_rang": neu + 1,
            }))
    return out


def rank_events(session: Session, before: list[int], after: list[int]) -> None:
    """Emittiert ein Event pro Überholvorgang in den Top 5."""
    users = {u.id: u for u in session.exec(select(User)).all()}
    for uid, payload in _rank_change_payloads(before, after, users):
        _emit(session, type_="rank_change", user_id=uid, payload=payload)


def _milestone_payload(m: dict) -> dict:
    return {"km": m["km"], "label": m["label"], "icon": m.get("icon", "fahne")}


def milestone_events(
    session: Session, user_id: int, total_before: float, total_after: float
) -> None:
    season = current_season(session)
    if season is None:
        return
    for m in json.loads(season.milestones_json or "[]"):
        if total_before < m["km"] <= total_after:
            _emit(session, type_="milestone", user_id=user_id,
                  payload=_milestone_payload(m))


def remove_activity_events(session: Session, activity_id: int) -> None:
    """Feed-Einträge (+ Reaktionen) einer gelöschten Aktivität entfernen."""
    for ev in session.exec(
        select(FeedEvent).where(FeedEvent.activity_id == activity_id)
    ).all():
        for r in session.exec(
            select(FeedReaction).where(FeedReaction.event_id == ev.id)
        ).all():
            session.delete(r)
        session.delete(ev)
    session.commit()


def _events_in_period(session: Session, von: date_type, bis: date_type,
                      typen: tuple[str, ...]) -> list[FeedEvent]:
    von_dt = datetime.combine(von, datetime.min.time(), tzinfo=_MESZ)
    bis_dt = datetime.combine(bis + timedelta(days=1), datetime.min.time(), tzinfo=_MESZ)
    out = []
    for ev in session.exec(
        select(FeedEvent).where(FeedEvent.type.in_(typen))  # type: ignore[attr-defined]
    ).all():
        t = ev.created_at
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        if von_dt <= t < bis_dt:
            out.append(ev)
    return out


def _recap_exists(session: Session, type_: str, period: str) -> bool:
    like = f'%"period": "{period}"%'
    return session.exec(
        select(FeedEvent).where(
            FeedEvent.type == type_,
            FeedEvent.payload_json.like(like),  # type: ignore[attr-defined]
        )
    ).first() is not None


def _emit_recap(session: Session, type_: str, period: str, label: str,
                von: date_type, bis: date_type, faellig: datetime) -> None:
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    mm: dict[int, float] = {uid: 0.0 for uid in users}
    for a in session.exec(
        select(Activity).where(Activity.date >= von, Activity.date <= bis)
    ).all():
        if a.user_id in users and a.category_id in cats:
            mm[a.user_id] += (
                a.distance_km * cats[a.category_id].factor * users[a.user_id].km_factor
            )
    per_user = sorted(
        (
            {"user_id": uid, "name": users[uid].display_name, "mm": round(km, 1)}
            for uid, km in mm.items()
        ),
        key=lambda e: -e["mm"],
    )
    ueberholungen = [
        json.loads(e.payload_json)
        for e in _events_in_period(session, von, bis, ("rank_change",))
    ]
    achievements = [
        json.loads(e.payload_json) | {"user_id": e.user_id}
        for e in _events_in_period(session, von, bis, ("achievement", "milestone"))
    ]
    _emit(session, type_=type_, created_at=faellig, payload={
        "period": period, "label": label,
        "von": von.isoformat(), "bis": bis.isoformat(),
        "total_mm": round(sum(mm.values()), 1),
        "per_user": per_user,
        "ueberholungen": ueberholungen,
        "achievements": achievements,
    })


_RECAP_QUELLEN = ("activity", "rank_change", "achievement", "milestone")


def ensure_recaps(session: Session, now: datetime | None = None) -> None:
    """Füllt alle fälligen Wochen-/Monatsrückblicke seit Saisonstart auf
    (lazy, idempotent). Der Wochenrückblick (Mo–So) wird am Sonntag derselben
    Woche um 19:00 deutscher Zeit fällig, der Monatsrückblick des Vormonats
    am Monatsersten 00:00; Rückblick-Events tragen den Fälligkeitszeitpunkt
    als created_at. Zeitraum ohne Feed-Events (= vor Feature-Launch oder
    komplett leer) bekommt keinen Rückblick — Spec B2/B5."""
    season = current_season(session)
    if season is None or season.start_date is None:
        return
    if now is None:
        now = datetime.now(tz=_MESZ)
    now = now.astimezone(_MESZ)

    # Wochen: erste Woche ist die Woche, die den Saisonstart enthält
    # (Zeitraum ab start_date), dann Woche für Woche bis heute.
    montag = season.start_date - timedelta(days=season.start_date.weekday())
    while True:
        sonntag = montag + timedelta(days=6)
        faellig = datetime.combine(sonntag, time_type(19, 0), tzinfo=_MESZ)
        if faellig > now:
            break
        von = max(montag, season.start_date)
        iso = montag.isocalendar()
        period = f"{iso.year}-W{iso.week:02d}"
        if (
            not _recap_exists(session, "recap_week", period)
            and _events_in_period(session, von, sonntag, _RECAP_QUELLEN)
        ):
            _emit_recap(session, "recap_week", period, f"KW {iso.week}",
                        von, sonntag, faellig)
        montag += timedelta(days=7)

    # Monate: jeder seit Saisonstart abgeschlossene Monat, fällig am
    # jeweils folgenden Monatsersten 00:00 deutscher Zeit.
    erster = season.start_date.replace(day=1)
    while True:
        naechster = (erster.replace(day=28) + timedelta(days=4)).replace(day=1)
        faellig = datetime.combine(naechster, time_type(0, 0), tzinfo=_MESZ)
        if faellig > now:
            break
        von = max(erster, season.start_date)
        bis = naechster - timedelta(days=1)
        period = erster.strftime("%Y-%m")
        if (
            not _recap_exists(session, "recap_month", period)
            and _events_in_period(session, von, bis, _RECAP_QUELLEN)
        ):
            _emit_recap(session, "recap_month", period, erster.strftime("%m/%Y"),
                        von, bis, faellig)
        erster = naechster


def backfill_feed_events(session: Session) -> None:
    """Einmaliger Feed-Backfill beim Backend-Start (Spec B5): Läuft nur,
    solange die FeedEvent-Tabelle komplett leer ist. Spielt alle
    Challenge-Aktivitäten seit Saisonstart chronologisch nach sportlichem
    Zeitpunkt (Datum + start_time, fehlt sie: 12:00 deutscher Zeit) durch
    und rekonstruiert activity-, milestone- und rank_change-Events;
    achievement-Events bekommen ihren echten unlocked_at-Zeitpunkt.
    Vergangene Rückblicke entstehen danach über ensure_recaps."""
    if session.exec(select(FeedEvent)).first() is not None:
        return
    season = current_season(session)
    if season is None or season.start_date is None:
        return
    window = season_window(season)
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = [
        a for a in session.exec(
            select(Activity).where(Activity.date >= season.start_date)
        ).all()
        if a.user_id in users and a.category_id in cats and in_window(a.date, window)
    ]
    acts.sort(key=lambda a: (a.date, a.start_time or time_type(12, 0), a.id))
    milestones = json.loads(season.milestones_json or "[]")

    def order(totals: dict[int, float]) -> list[int]:
        return [uid for uid, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))]

    totals: dict[int, float] = {uid: 0.0 for uid in users}
    before = order(totals)
    for a in acts:
        cat = cats[a.category_id]
        ts = datetime.combine(
            a.date, a.start_time or time_type(12, 0), tzinfo=_MESZ
        ).astimezone(timezone.utc)
        session.add(FeedEvent(
            season_year=season.year, type="activity", user_id=a.user_id,
            activity_id=a.id, created_at=ts,
            payload_json=json.dumps(_activity_payload(a, cat)),
        ))
        vorher = totals[a.user_id]
        totals[a.user_id] += a.distance_km * cat.factor * users[a.user_id].km_factor
        for m in milestones:
            if vorher < m["km"] <= totals[a.user_id]:
                session.add(FeedEvent(
                    season_year=season.year, type="milestone", user_id=a.user_id,
                    created_at=ts, payload_json=json.dumps(_milestone_payload(m)),
                ))
        after = order(totals)
        for uid, payload in _rank_change_payloads(before, after, users):
            session.add(FeedEvent(
                season_year=season.year, type="rank_change", user_id=uid,
                created_at=ts, payload_json=json.dumps(payload),
            ))
        before = after

    # Achievements aktiver User mit echtem Freischalt-Zeitpunkt
    from .achievements import achievement_info  # function-level: Import-Zyklus

    for unlock in session.exec(select(AchievementUnlock)).all():
        if unlock.user_id not in users:
            continue
        titel, emoji = achievement_info(unlock.key)
        session.add(FeedEvent(
            season_year=season.year, type="achievement", user_id=unlock.user_id,
            created_at=unlock.unlocked_at,
            payload_json=json.dumps({
                "key": unlock.key, "title": titel, "emoji": emoji,
                "context": json.loads(unlock.context_json or "{}"),
            }),
        ))
    session.commit()
