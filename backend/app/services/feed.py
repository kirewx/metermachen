"""Newsfeed: Event-Erzeugung + Rückblicke (Spec 2026-07-25 Teil B).

Events werden an den Schreibpfaden erzeugt (Aktivität, Überholung,
Achievement, Meilenstein); Rückblicke lazy beim Feed-Abruf — gleiches
Muster wie bets.ensure_monthly_tip. Kein Cron.
"""

import json
from datetime import date as date_type
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from ..models import Activity, Category, FeedEvent, FeedReaction, User
from .season_window import current_season, in_window, season_window

REACTION_EMOJIS = ("👏", "🔥", "💪", "😂", "😮")
TOP_N = 5
# Feed-Tage/Rückblick-Grenzen um Mitternacht deutscher Zeit — fester
# Sommerzeit-Offset wie in services/achievements.py und seed.py.
_MESZ = timezone(timedelta(hours=2))


def _emit(session: Session, *, type_: str, user_id: int | None = None,
          activity_id: int | None = None, payload: dict | None = None) -> None:
    season = current_season(session)
    if season is None:
        return
    session.add(FeedEvent(
        season_year=season.year, type=type_, user_id=user_id,
        activity_id=activity_id, payload_json=json.dumps(payload or {}),
    ))
    session.commit()


def activity_event(session: Session, act: Activity) -> None:
    cat = session.get(Category, act.category_id)
    if cat is None:
        return
    _emit(session, type_="activity", user_id=act.user_id, activity_id=act.id, payload={
        "category": {"name": cat.name, "icon": cat.icon, "color": cat.color},
        "distance_km": act.distance_km,
        "mm": round(act.distance_km * cat.factor, 2),
        "titel": act.note,
        "datum": act.date.isoformat(),
    })


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


def rank_events(session: Session, before: list[int], after: list[int]) -> None:
    """Emittiert ein Event pro Überholvorgang in den Top 5."""
    pos_b = {uid: i for i, uid in enumerate(before)}
    pos_a = {uid: i for i, uid in enumerate(after)}
    users = {u.id: u for u in session.exec(select(User)).all()}

    def name(uid: int) -> str:
        return users[uid].display_name if uid in users else f"#{uid}"

    for uid, neu in pos_a.items():
        if neu >= TOP_N or uid not in pos_b or neu >= pos_b[uid]:
            continue  # nur Aufsteiger in die/innerhalb der Top 5
        ueberholte = [
            o for o in pos_b
            if o != uid and pos_b[o] < pos_b[uid] and pos_a.get(o, len(pos_a)) > neu
        ]
        for o in ueberholte:
            _emit(session, type_="rank_change", user_id=uid, payload={
                "name": name(uid),
                "ueberholt_user_id": o,
                "ueberholt_name": name(o),
                "neuer_rang": neu + 1,
            })


def milestone_events(
    session: Session, user_id: int, total_before: float, total_after: float
) -> None:
    season = current_season(session)
    if season is None:
        return
    for m in json.loads(season.milestones_json or "[]"):
        if total_before < m["km"] <= total_after:
            _emit(session, type_="milestone", user_id=user_id, payload={
                "km": m["km"], "label": m["label"], "icon": m.get("icon", "fahne"),
            })


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


def _german_today() -> date_type:
    return datetime.now(tz=_MESZ).date()


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
                von: date_type, bis: date_type) -> None:
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
    _emit(session, type_=type_, payload={
        "period": period, "label": label,
        "von": von.isoformat(), "bis": bis.isoformat(),
        "total_mm": round(sum(mm.values()), 1),
        "per_user": per_user,
        "ueberholungen": ueberholungen,
        "achievements": achievements,
    })


def ensure_recaps(session: Session, today: date_type | None = None) -> None:
    """Erzeugt fällige Wochen-/Monatsrückblicke (lazy, idempotent).
    Zeitraum ohne Feed-Events (= vor Feature-Launch oder komplett leer)
    bekommt keinen Rückblick — Spec B5."""
    season = current_season(session)
    if season is None or season.start_date is None:
        return
    heute = today or _german_today()
    if heute < season.start_date:
        return

    # Woche: Vorwoche Mo–So, sobald der neue Montag erreicht ist
    montag = heute - timedelta(days=heute.weekday())
    w_von, w_bis = montag - timedelta(days=7), montag - timedelta(days=1)
    iso = w_von.isocalendar()
    w_period = f"{iso.year}-W{iso.week:02d}"
    if (
        w_von >= season.start_date
        and not _recap_exists(session, "recap_week", w_period)
        and _events_in_period(session, w_von, w_bis,
                              ("activity", "rank_change", "achievement", "milestone"))
    ):
        _emit_recap(session, "recap_week", w_period, f"KW {iso.week}", w_von, w_bis)

    # Monat: Vormonat, sobald der Monatserste erreicht ist
    erster = heute.replace(day=1)
    m_bis = erster - timedelta(days=1)
    m_von = max(m_bis.replace(day=1), season.start_date)
    m_period = m_bis.strftime("%Y-%m")
    monat_label = m_bis.strftime("%m/%Y")
    if (
        m_bis >= season.start_date
        and not _recap_exists(session, "recap_month", m_period)
        and _events_in_period(session, m_von, m_bis,
                              ("activity", "rank_change", "achievement", "milestone"))
    ):
        _emit_recap(session, "recap_month", m_period, monat_label, m_von, m_bis)
