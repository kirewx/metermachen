# PR 2: Newsfeed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neuer Feed-Tab mit chronologischem Gruppen-Feed (Aktivitäten, Überholungen, Achievements/Meilensteine, Wochen-/Monatsrückblicke) und Emoji-Reaktionen — Spec `docs/superpowers/specs/2026-07-25-anpassungen-und-newsfeed-design.md` Teil B.

**Architecture:** Materialisierte Event-Tabelle (`FeedEvent`), Events entstehen an den bestehenden Schreibpfaden (Aktivitäten-Router, Strava-Import, `check_unlocks`). Rückblicke werden lazy beim Feed-Abruf erzeugt (Muster `ensure_monthly_tip`). Reaktionen als eigene Tabelle mit Unique-Toggle. Frontend: neuer Tab mit Cursor-Pagination.

**Tech Stack:** FastAPI + SQLModel + pytest (`cd backend && uv run pytest`), React 19 + TanStack Query 5 + Vitest (`cd frontend && npx vitest run`).

**Voraussetzung:** PR 1 ist gemergt (nutzt `SHOWCASE_INFO` aus `backend/app/services/achievements.py`). Branch:
```bash
git fetch origin && git checkout -b feature/newsfeed origin/main
```

**Beim Bauen des Frontends (Tasks 7–9):** den `frontend-design`-Skill laden — Politur innerhalb der bestehenden Designsprache, keine Neugestaltung; die validierten Mockups aus der Spec sind maßgeblich.

---

### Task 1: Modelle FeedEvent / FeedReaction / FeedSeen

**Files:**
- Modify: `backend/app/models.py` (ans Ende anhängen; `Index` zu den sqlalchemy-Imports)
- Test: `backend/tests/test_models.py` (anhängen)

- [ ] **Step 1: Failing Test** — in `test_models.py` anhängen:

```python
def test_feed_reaction_unique_pro_user_und_emoji(session):
    ev = FeedEvent(season_year=2026, type="activity", user_id=1)
    session.add(ev)
    session.commit()
    session.add(FeedReaction(event_id=ev.id, user_id=1, emoji="🔥"))
    session.commit()
    session.add(FeedReaction(event_id=ev.id, user_id=1, emoji="🔥"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
```

(Imports: `pytest`, `from sqlalchemy.exc import IntegrityError`, `from app.models import FeedEvent, FeedReaction` — vorhandene Imports der Datei prüfen.)

- [ ] **Step 2:** `cd backend && uv run pytest tests/test_models.py -q` → FAIL (Import-Fehler).

- [ ] **Step 3: Implementieren** — in `models.py` oben `from sqlalchemy import Index, UniqueConstraint` und ans Dateiende:

```python
class FeedEvent(SQLModel, table=True):
    """Chronologisches Gruppen-Feed-Event (Spec 2026-07-25 Teil B).
    type: "activity" | "rank_change" | "achievement" | "milestone"
        | "recap_week" | "recap_month"."""

    __table_args__ = (
        Index("ix_feedevent_season_created", "season_year", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    season_year: int
    type: str
    user_id: int | None = Field(default=None, foreign_key="user.id")
    activity_id: int | None = Field(default=None, foreign_key="activity.id")
    payload_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)


class FeedReaction(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", "emoji", name="uq_reaction"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="feedevent.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    emoji: str
    created_at: datetime = Field(default_factory=utcnow)


class FeedSeen(SQLModel, table=True):
    """Zuletzt gesehener Feed-Stand pro Nutzer (Punkt am Tab)."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    seen_at: datetime = Field(default_factory=utcnow)
```

Keine `db.py`-Migration nötig: `SQLModel.metadata.create_all` legt neue Tabellen automatisch an.

- [ ] **Step 4:** `uv run pytest tests/test_models.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Modelle FeedEvent, FeedReaction, FeedSeen"`.

---

### Task 2: Feed-Service — Aktivitäts-, Rang- und Meilenstein-Events

**Files:**
- Create: `backend/app/services/feed.py`
- Test (create): `backend/tests/test_feed.py`

- [ ] **Step 1: Failing Tests** — `backend/tests/test_feed.py` anlegen:

```python
import json
from datetime import date

from sqlmodel import select

from app.models import Activity, FeedEvent, Season
from app.services import feed
from tests.conftest import make_category, make_user


def _setup_saison(session, start=date(2026, 7, 20)):
    session.add(Season(year=2026, goal_km=1000.0, start_date=start,
                       end_date=date(2027, 5, 16),
                       milestones_json=json.dumps([{"km": 50.0, "label": "Ärmelkanal", "icon": "fahne"}])))
    session.commit()


def _act(session, user, cat, km, tag=date(2026, 8, 3)):
    act = Activity(user_id=user.id, category_id=cat.id, date=tag, distance_km=km)
    session.add(act)
    session.commit()
    session.refresh(act)
    return act


def test_activity_event_mit_kategorie_und_mm(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=4.0)
    act = _act(session, user, cat, 10.0)
    feed.activity_event(session, act)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "activity")).one()
    p = json.loads(ev.payload_json)
    assert ev.user_id == user.id and ev.activity_id == act.id
    assert p["mm"] == 40.0 and p["category"]["name"] == cat.name


def test_rank_events_nur_top5_aufsteiger(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    before = [b.id, a.id]
    after = [a.id, b.id]
    feed.rank_events(session, before, after)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "rank_change")).one()
    p = json.loads(ev.payload_json)
    assert ev.user_id == a.id
    assert p["ueberholt_user_id"] == b.id and p["neuer_rang"] == 1


def test_rank_events_keine_events_ohne_aenderung(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    feed.rank_events(session, [a.id, b.id], [a.id, b.id])
    assert session.exec(select(FeedEvent)).all() == []


def test_milestone_event_bei_ueberschreitung(session):
    _setup_saison(session)
    user = make_user(session)
    feed.milestone_events(session, user.id, total_before=45.0, total_after=52.0)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "milestone")).one()
    assert json.loads(ev.payload_json)["label"] == "Ärmelkanal"


def test_milestone_kein_event_ohne_ueberschreitung(session):
    _setup_saison(session)
    user = make_user(session)
    feed.milestone_events(session, user.id, total_before=52.0, total_after=60.0)
    assert session.exec(select(FeedEvent)).all() == []


def test_challenge_order_nach_mm_mit_handicap(session):
    _setup_saison(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    cat = make_category(session, factor=1.0)
    _act(session, a, cat, 10.0)
    _act(session, b, cat, 20.0)
    assert feed.challenge_order(session) == [b.id, a.id]


def test_remove_activity_events(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session)
    act = _act(session, user, cat, 10.0)
    feed.activity_event(session, act)
    feed.remove_activity_events(session, act.id)
    assert session.exec(select(FeedEvent)).all() == []
```

- [ ] **Step 2:** `uv run pytest tests/test_feed.py -q` → FAIL (Modul fehlt).

- [ ] **Step 3: Implementieren** — `backend/app/services/feed.py`:

```python
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
```

- [ ] **Step 4:** `uv run pytest tests/test_feed.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Event-Service (Aktivitaet, Ueberholung, Meilenstein)"`.

---

### Task 3: Achievement-Events aus `check_unlocks`

**Files:**
- Modify: `backend/app/services/achievements.py` (`_unlock`, ~Zeile 171; Helper danach)
- Test: `backend/tests/test_feed.py` (anhängen)

- [ ] **Step 1: Failing Test** — in `test_feed.py` anhängen:

```python
def test_unlock_erzeugt_achievement_event(session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    for _ in range(3):  # Hattrick: 3 Aktivitäten an einem Tag
        _act(session, user, cat, 2.0)
    from app.services.achievements import check_unlocks
    check_unlocks(session, user.id)
    evs = session.exec(select(FeedEvent).where(FeedEvent.type == "achievement")).all()
    keys = [json.loads(e.payload_json)["key"] for e in evs]
    assert "hattrick" in keys
    hat = next(json.loads(e.payload_json) for e in evs
               if json.loads(e.payload_json)["key"] == "hattrick")
    assert hat["title"] == "Hattrick" and hat["emoji"] == "🎩"
```

- [ ] **Step 2:** `uv run pytest tests/test_feed.py::test_unlock_erzeugt_achievement_event -q` → FAIL.

- [ ] **Step 3: Implementieren.** In `achievements.py` einen Titel-Helper ergänzen (nach `SHOWCASE_INFO`):

```python
def achievement_info(key: str) -> tuple[str, str | None]:
    """(titel, emoji|None) für jeden Unlock-Key — auch Stufen ohne Emoji."""
    info = SHOWCASE_INFO.get(key)
    if info is not None:
        emoji, titel, _desc = info
        return titel, emoji
    for bucket, label in DISZIPLIN_LABEL.items():
        for tier in TIERS:
            if key == stufen_key(bucket, tier):
                return f"{label} {tier.capitalize()}", None
    return key, None
```

und `_unlock` erweitert — nach dem erfolgreichen `session.commit()` (im `try`-Zweig, vor `return True`):

```python
        from .feed import _emit

        titel, emoji = achievement_info(key)
        _emit(session, type_="achievement", user_id=user_id, payload={
            "key": key, "title": titel, "emoji": emoji, "context": context or {},
        })
```

(Function-level Import vermeidet den Zyklus feed↔achievements.)

- [ ] **Step 4:** `uv run pytest tests/test_feed.py tests/test_achievements.py tests/test_achievement_unlocks.py -q` → PASS (Achievement-Tests zählen ggf. Events nicht — nur bei Fehlschlägen anpassen).
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Achievement-Unlocks erzeugen Feed-Events"`.

---

### Task 4: Hooks in Aktivitäten-Router und Strava-Import

**Files:**
- Modify: `backend/app/routers/activities.py` (create/patch/delete), `backend/app/services/strava.py` (`import_activity`, `backfill_current_year`)
- Test: `backend/tests/test_feed.py` (anhängen)

- [ ] **Step 1: Failing Tests** — in `test_feed.py` anhängen (API-Ebene; Login-Muster aus `tests/test_activities.py` übernehmen):

```python
def test_create_activity_emittiert_events(client, session):
    _setup_saison(session)
    make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    r = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-08-03", "distance_km": 60.0,
    })
    assert r.status_code == 201
    typen = {e.type for e in session.exec(select(FeedEvent)).all()}
    assert "activity" in typen
    assert "milestone" in typen  # 60 MM > 50-km-Meilenstein


def test_delete_activity_entfernt_feed_eintrag(client, session):
    _setup_saison(session)
    make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    act_id = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-08-03", "distance_km": 10.0,
    }).json()["id"]
    client.delete(f"/api/activities/{act_id}")
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "activity")
    ).all() == []


def test_strava_backfill_erzeugt_keine_feed_events(session):
    _setup_saison(session)
    user = make_user(session)
    make_category(session, factor=1.0, strava_sport_types='["Run"]')
    from app.models import StravaConnection
    from app.services.strava import import_activity
    conn = StravaConnection(user_id=user.id, athlete_id=1, access_token="t",
                            refresh_token="r", expires_at=9999999999)
    session.add(conn)
    session.commit()
    data = {"id": 42, "sport_type": "Run", "distance": 8000,
            "start_date_local": "2026-08-03T07:00:00Z"}
    import_activity(session, conn, data, emit_feed=False)
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "activity")
    ).all() == []
```

Hinweis: `test_create_activity_emittiert_events` erwartet ggf. auch `achievement`-Events (Startschuss o. Ä.) — deshalb wird mit `in typen` geprüft, nicht mit Gleichheit.

- [ ] **Step 2:** `uv run pytest tests/test_feed.py -q` → neue Tests FAIL.

- [ ] **Step 3: Implementieren.**

`activities.py` — Import ergänzen: `from ..services import feed`. In `create_activity` (Zeilen 66–78):

```python
    cat = _validate_category(session, data.category_id)
    order_before = feed.challenge_order(session)
    total_before = feed.challenge_total(session, user.id)
    act = Activity(user_id=user.id, **data.model_dump())
    session.add(act)
    session.commit()
    session.refresh(act)
    check_unlocks(session, user.id)
    feed.activity_event(session, act)
    feed.milestone_events(session, user.id, total_before, feed.challenge_total(session, user.id))
    feed.rank_events(session, order_before, feed.challenge_order(session))
    return _to_out(act, cat.factor)
```

In `patch_activity`: vor den Änderungen `order_before = feed.challenge_order(session)` und `total_before = feed.challenge_total(session, user.id)`; nach `check_unlocks(...)`:

```python
    feed.milestone_events(session, user.id, total_before, feed.challenge_total(session, user.id))
    feed.rank_events(session, order_before, feed.challenge_order(session))
```

(kein neues `activity`-Event beim Bearbeiten — Spec B5.)

In `delete_activity`:

```python
    act = _own_activity(session, user, activity_id)
    order_before = feed.challenge_order(session)
    feed.remove_activity_events(session, act.id)
    session.delete(act)
    session.commit()
    feed.rank_events(session, order_before, feed.challenge_order(session))
```

`strava.py` — Signatur: `def import_activity(session, conn, data, emit_feed: bool = True) -> bool:`. Vor dem `session.add(act)`:

```python
    from . import feed

    order_before = feed.challenge_order(session) if emit_feed else []
    total_before = feed.challenge_total(session, conn.user_id) if emit_feed else 0.0
```

Nach `check_unlocks(session, conn.user_id)`:

```python
    if emit_feed:
        feed.activity_event(session, act)
        feed.milestone_events(
            session, conn.user_id, total_before,
            feed.challenge_total(session, conn.user_id),
        )
        feed.rank_events(session, order_before, feed.challenge_order(session))
    return True
```

In `backfill_current_year` den Aufruf ändern: `if import_activity(session, conn, data, emit_feed=False):` — der Webhook-Pfad (`handle_webhook_event`) bleibt beim Default `emit_feed=True`.

- [ ] **Step 4:** `uv run pytest tests/test_feed.py tests/test_activities.py tests/test_strava.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Events aus Aktivitaeten-Router und Strava-Import (Backfill-Schutz)"`.

---

### Task 5: Rückblicke (lazy, Wochen-/Monatsgrenzen deutsche Zeit)

**Files:**
- Modify: `backend/app/services/feed.py` (anhängen)
- Test: `backend/tests/test_feed.py` (anhängen)

- [ ] **Step 1: Failing Tests:**

```python
def test_wochenrueckblick_wird_einmal_erzeugt(session):
    _setup_saison(session, start=date(2026, 7, 20))
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    # Aktivität + Event in der Vorwoche (Mo 27.07.–So 02.08.)
    act = _act(session, user, cat, 12.0, tag=date(2026, 7, 28))
    feed.activity_event(session, act)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "activity")).one()
    ev.created_at = datetime(2026, 7, 28, 10, 0)
    session.add(ev)
    session.commit()

    heute = date(2026, 8, 3)  # Montag danach
    feed.ensure_recaps(session, today=heute)
    feed.ensure_recaps(session, today=heute)  # idempotent
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all()
    assert len(recaps) == 1
    p = json.loads(recaps[0].payload_json)
    assert p["period"] == "2026-W31"
    assert p["total_mm"] == 12.0
    assert p["per_user"][0]["user_id"] == user.id


def test_kein_rueckblick_ohne_events_im_zeitraum(session):
    _setup_saison(session, start=date(2026, 7, 20))
    make_user(session)
    feed.ensure_recaps(session, today=date(2026, 8, 3))
    assert session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_week")
    ).all() == []


def test_monatsrueckblick_am_monatsersten(session):
    _setup_saison(session, start=date(2026, 7, 20))
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    act = _act(session, user, cat, 10.0, tag=date(2026, 8, 15))
    feed.activity_event(session, act)
    ev = session.exec(select(FeedEvent).where(FeedEvent.type == "activity")).one()
    ev.created_at = datetime(2026, 8, 15, 10, 0)
    session.add(ev)
    session.commit()

    feed.ensure_recaps(session, today=date(2026, 9, 1))
    recaps = session.exec(
        select(FeedEvent).where(FeedEvent.type == "recap_month")
    ).all()
    assert len(recaps) == 1
    assert json.loads(recaps[0].payload_json)["period"] == "2026-08"
```

(Import oben ergänzen: `from datetime import datetime`.)

- [ ] **Step 2:** `uv run pytest tests/test_feed.py -q` → FAIL.

- [ ] **Step 3: Implementieren** — in `feed.py` anhängen:

```python
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
```

- [ ] **Step 4:** `uv run pytest tests/test_feed.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Wochen- und Monatsrueckblicke (lazy, deutsche Zeitgrenzen)"`.

---

### Task 6: Feed-API (Seite, Reaktionen, Seen)

**Files:**
- Modify: `backend/app/schemas.py` (anhängen), `backend/app/main.py` (Router registrieren)
- Create: `backend/app/routers/feed.py`
- Test: `backend/tests/test_feed.py` (anhängen)

- [ ] **Step 1: Failing Tests:**

```python
def test_feed_api_paginierung_und_reaktionen(client, session):
    _setup_saison(session)
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    for _ in range(35):
        client.post("/api/activities", json={
            "category_id": cat.id, "date": "2026-08-03", "distance_km": 6.0,
        })
    page = client.get("/api/feed?year=2026").json()
    assert len(page["events"]) == 30
    assert page["next_before"] is not None
    page2 = client.get(f"/api/feed?year=2026&before={page['next_before']}").json()
    assert 0 < len(page2["events"]) <= 30

    ev_id = page["events"][0]["id"]
    r = client.post(f"/api/feed/{ev_id}/reactions", json={"emoji": "🔥"}).json()
    fire = next(x for x in r if x["emoji"] == "🔥")
    assert fire["count"] == 1 and fire["mine"] is True
    r = client.post(f"/api/feed/{ev_id}/reactions", json={"emoji": "🔥"}).json()
    assert all(x["emoji"] != "🔥" for x in r)  # Toggle aus
    assert client.post(
        f"/api/feed/{ev_id}/reactions", json={"emoji": "🍕"}
    ).status_code == 422


def test_feed_unseen_und_seen(client, session):
    _setup_saison(session)
    make_user(session)
    cat = make_category(session, factor=1.0)
    login(client)
    client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-08-03", "distance_km": 6.0,
    })
    assert client.get("/api/feed/unseen").json() == {"has_new": True}
    client.post("/api/feed/seen")
    assert client.get("/api/feed/unseen").json() == {"has_new": False}
```

- [ ] **Step 2:** `uv run pytest tests/test_feed.py -q` → FAIL.

- [ ] **Step 3: Implementieren.** `schemas.py` anhängen:

```python
class FeedReactionOut(BaseModel):
    emoji: str
    count: int
    mine: bool
    users: list[str]


class FeedEventOut(BaseModel):
    id: int
    type: str
    user_id: int | None
    display_name: str | None
    avatar: str | None
    created_at: datetime
    payload: dict
    reactions: list[FeedReactionOut]


class FeedPage(BaseModel):
    events: list[FeedEventOut]
    next_before: int | None


class FeedReactionIn(BaseModel):
    emoji: str
```

`backend/app/routers/feed.py`:

```python
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..deps import get_current_user, get_session
from ..models import FeedEvent, FeedReaction, FeedSeen, User, utcnow
from ..schemas import FeedEventOut, FeedPage, FeedReactionIn, FeedReactionOut
from ..services.feed import REACTION_EMOJIS, ensure_recaps

router = APIRouter(prefix="/api/feed", tags=["feed"])

PAGE_SIZE = 30


def _reactions_for(
    session: Session, event_ids: list[int], me: User
) -> dict[int, list[FeedReactionOut]]:
    users = {u.id: u for u in session.exec(select(User)).all()}
    rows = session.exec(
        select(FeedReaction).where(FeedReaction.event_id.in_(event_ids))  # type: ignore[attr-defined]
    ).all() if event_ids else []
    out: dict[int, list[FeedReactionOut]] = {}
    for eid in event_ids:
        mine = [r for r in rows if r.event_id == eid]
        per_emoji: dict[str, list[FeedReaction]] = {}
        for r in mine:
            per_emoji.setdefault(r.emoji, []).append(r)
        out[eid] = [
            FeedReactionOut(
                emoji=emoji,
                count=len(rs),
                mine=any(r.user_id == me.id for r in rs),
                users=[
                    users[r.user_id].display_name
                    for r in rs if r.user_id in users
                ],
            )
            for emoji, rs in sorted(per_emoji.items())
        ]
    return out


def _to_out(session, events, me) -> list[FeedEventOut]:
    users = {u.id: u for u in session.exec(select(User)).all()}
    reactions = _reactions_for(session, [e.id for e in events], me)
    out = []
    for e in events:
        u = users.get(e.user_id)
        out.append(FeedEventOut(
            id=e.id, type=e.type, user_id=e.user_id,
            display_name=u.display_name if u else None,
            avatar=u.avatar if u else None,
            created_at=e.created_at,
            payload=json.loads(e.payload_json),
            reactions=reactions.get(e.id, []),
        ))
    return out


@router.get("", response_model=FeedPage)
def feed_page(
    year: int,
    before: int | None = None,
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    ensure_recaps(session)
    stmt = select(FeedEvent).where(FeedEvent.season_year == year)
    if before is not None:
        stmt = stmt.where(FeedEvent.id < before)
    events = session.exec(
        stmt.order_by(FeedEvent.id.desc()).limit(PAGE_SIZE)  # type: ignore[attr-defined]
    ).all()
    next_before = events[-1].id if len(events) == PAGE_SIZE else None
    return FeedPage(events=_to_out(session, events, me), next_before=next_before)


@router.get("/unseen")
def feed_unseen(
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    seen = session.exec(
        select(FeedSeen).where(FeedSeen.user_id == me.id)
    ).first()
    stmt = select(FeedEvent)
    newest = session.exec(
        stmt.order_by(FeedEvent.created_at.desc()).limit(1)  # type: ignore[attr-defined]
    ).first()
    has_new = newest is not None and (seen is None or newest.created_at > seen.seen_at)
    return {"has_new": has_new}


@router.post("/seen", status_code=204)
def mark_feed_seen(
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    seen = session.exec(
        select(FeedSeen).where(FeedSeen.user_id == me.id)
    ).first()
    if seen is None:
        seen = FeedSeen(user_id=me.id)
    seen.seen_at = utcnow()
    session.add(seen)
    session.commit()


@router.post("/{event_id}/reactions", response_model=list[FeedReactionOut])
def toggle_reaction(
    event_id: int,
    data: FeedReactionIn,
    session: Session = Depends(get_session),
    me: User = Depends(get_current_user),
):
    if data.emoji not in REACTION_EMOJIS:
        raise HTTPException(status_code=422, detail="Unbekanntes Reaktions-Emoji")
    if session.get(FeedEvent, event_id) is None:
        raise HTTPException(status_code=404)
    existing = session.exec(
        select(FeedReaction).where(
            FeedReaction.event_id == event_id,
            FeedReaction.user_id == me.id,
            FeedReaction.emoji == data.emoji,
        )
    ).first()
    if existing is not None:
        session.delete(existing)
    else:
        session.add(FeedReaction(event_id=event_id, user_id=me.id, emoji=data.emoji))
    session.commit()
    return _reactions_for(session, [event_id], me)[event_id]
```

`main.py`: `feed` zum Router-Import-Block hinzufügen und `app.include_router(feed.router)` ergänzen. Achtung Namenskollision: der Import heißt dort `from .routers import (…, feed, …)` — der Service wird in Routern als `from ..services.feed import …` importiert, das kollidiert nicht.

- [ ] **Step 4:** `uv run pytest tests/test_feed.py -q` und danach `uv run pytest -q` (kompletter Lauf) → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): API mit Cursor-Paginierung, Reaktions-Toggle und Seen-Status"`.

---

### Task 7: Frontend-Grundlage — Typen, Tab, Route, Ungelesen-Punkt

**Files:**
- Modify: `frontend/src/api/client.ts`, `frontend/src/components/ui/tabs.ts`, `frontend/src/App.tsx`, `frontend/src/components/ui/Layout.tsx`
- Create: `frontend/src/pages/Feed.tsx` (Platzhalter, wird in Task 8 gefüllt)
- Test: `frontend/src/components/ui/tabs.test.ts`

- [ ] **Step 1: Typen + API** — `client.ts` anhängen:

```ts
export type FeedReaction = { emoji: string; count: number; mine: boolean; users: string[] }
export type FeedEvent = {
  id: number
  type: 'activity' | 'rank_change' | 'achievement' | 'milestone' | 'recap_week' | 'recap_month'
  user_id: number | null
  display_name: string | null
  avatar: string | null
  created_at: string
  payload: {
    category?: { name: string; icon: string; color: string }
    distance_km?: number
    mm?: number
    titel?: string | null
    datum?: string
    name?: string
    ueberholt_name?: string
    neuer_rang?: number
    key?: string
    title?: string
    emoji?: string | null
    km?: number
    label?: string
    icon?: string
    period?: string
    von?: string
    bis?: string
    total_mm?: number
    per_user?: { user_id: number; name: string; mm: number }[]
    ueberholungen?: { name: string; ueberholt_name: string; neuer_rang: number }[]
    achievements?: { user_id: number | null; title?: string; emoji?: string | null; label?: string }[]
  }
  reactions: FeedReaction[]
}
export type FeedPage = { events: FeedEvent[]; next_before: number | null }
```

und im `api`-Objekt:

```ts
  feed: (year: number, before?: number) =>
    request<FeedPage>(`/api/feed?year=${year}${before ? `&before=${before}` : ''}`),
  toggleFeedReaction: (eventId: number, emoji: string) =>
    request<FeedReaction[]>(`/api/feed/${eventId}/reactions`, post({ emoji })),
  feedUnseen: () => request<{ has_new: boolean }>('/api/feed/unseen'),
  markFeedSeen: () => request<void>('/api/feed/seen', { method: 'POST' }),
```

- [ ] **Step 2: Tab + Route.** `tabs.ts` — nach dem Vergleich-Eintrag:

```ts
  { to: '/feed', label: 'Feed', icon: 'chart', end: false, adminOnly: false, abStart: true },
```

`App.tsx`: Import `Feed` + `<Route path="/feed" element={<Feed />} />` (nach der `/`-Route). `pages/Feed.tsx` vorerst:

```tsx
export default function Feed() {
  return <p className="p-8 text-ink-mute">Lade…</p>
}
```

`tabs.test.ts`: Test ergänzen, dass `/feed` nur mit `gestartet: true` sichtbar ist.

- [ ] **Step 3: Ungelesen-Punkt.** In `Layout.tsx` (nach den anderen Queries):

```tsx
  const { data: feedUnseen } = useQuery({
    queryKey: ['feed-unseen'],
    queryFn: api.feedUnseen,
    refetchInterval: 60_000,
    enabled: gestartet,
  })
```

und in BEIDEN Tab-Renderings (Desktop-`pill`-NavLink und mobile Bottom-Bar) hinter `{t.label}`:

```tsx
              {t.to === '/feed' && feedUnseen?.has_new && (
                <span aria-label="Neue Einträge" className="ml-0.5 inline-block h-1.5 w-1.5 rounded-full bg-accent" />
              )}
```

- [ ] **Step 4:** `npx vitest run src/components/ui/tabs.test.ts && npm run build` → PASS/OK.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Tab, Route, API-Client und Ungelesen-Punkt"`.

---

### Task 8: Feed-Seite mit Einträgen und Tages-Trennern

**Files:**
- Modify: `frontend/src/pages/Feed.tsx` (echte Implementierung)
- Create: `frontend/src/components/feed/FeedItem.tsx`
- Test (create): `frontend/src/pages/Feed.test.tsx`

- [ ] **Step 1: Failing Test** — `Feed.test.tsx` (Mock-Muster von bestehenden Page-Tests wie `Wetten.test.tsx` übernehmen — `vi.mock('../api/client', …)`):

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import Feed from './Feed'

const events = [
  {
    id: 2, type: 'activity', user_id: 1, display_name: 'Anna', avatar: '🦊',
    created_at: new Date().toISOString(),
    payload: { category: { name: 'Rad', icon: 'rad', color: '#60a5fa' }, distance_km: 42.3, mm: 38, titel: 'Feierabendrunde' },
    reactions: [{ emoji: '👏', count: 3, mine: false, users: ['Ben'] }],
  },
  {
    id: 1, type: 'rank_change', user_id: 1, display_name: 'Anna', avatar: '🦊',
    created_at: new Date().toISOString(),
    payload: { name: 'Anna', ueberholt_name: 'Ben', neuer_rang: 2 },
    reactions: [],
  },
]

vi.mock('../api/client', async (orig) => {
  const mod = (await orig()) as object
  return {
    ...mod,
    api: {
      seasons: vi.fn().mockResolvedValue([
        { id: 1, year: 2026, goal_km: 1000, milestones: [], start_date: '2026-07-20', end_date: '2027-05-16' },
      ]),
      feed: vi.fn().mockResolvedValue({ events, next_before: null }),
      feedUnseen: vi.fn().mockResolvedValue({ has_new: false }),
      markFeedSeen: vi.fn().mockResolvedValue(undefined),
      toggleFeedReaction: vi.fn(),
    },
  }
})

it('zeigt Aktivitaets- und Ueberholungs-Eintraege', async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Feed />
    </QueryClientProvider>,
  )
  await waitFor(() => expect(screen.getByText(/Feierabendrunde/)).toBeInTheDocument())
  expect(screen.getByText(/überholt/)).toBeInTheDocument()
  expect(screen.getByText(/Heute/)).toBeInTheDocument()
})
```

- [ ] **Step 2:** `npx vitest run src/pages/Feed.test.tsx` → FAIL.

- [ ] **Step 3: Implementieren.** `components/feed/FeedItem.tsx` (Reaktionsleiste kommt in Task 9 — hier zunächst statisch die vorhandenen Chips rendern):

```tsx
import type { FeedEvent } from '../../api/client'
import Avatar from '../ui/Avatar'
import Icon from '../ui/Icon'
import RecapCard from './RecapCard'
import ReactionBar from './ReactionBar'

const TYP_FARBE: Record<string, string> = {
  rank_change: '#c084fc',
  achievement: '#fbbf24',
  milestone: '#fbbf24',
  recap_week: '#fbbf24',
  recap_month: '#fbbf24',
}

function borderColor(ev: FeedEvent): string {
  if (ev.type === 'activity') return ev.payload.category?.color ?? '#8b8f98'
  return TYP_FARBE[ev.type] ?? '#8b8f98'
}

export default function FeedItem({ ev }: { ev: FeedEvent }) {
  return (
    <div
      className="rounded-xl border border-line bg-card p-3"
      style={{ borderLeft: `3px solid ${borderColor(ev)}` }}
    >
      {ev.type === 'activity' && (
        <>
          <div className="flex items-baseline gap-2 text-sm">
            {ev.payload.category && (
              <Icon name={ev.payload.category.icon} size={16} className="shrink-0 self-center text-accent" />
            )}
            <span className="font-bold text-ink">{ev.display_name}</span>
            <span className="text-ink-mute">· {ev.payload.category?.name}</span>
            <Zeit iso={ev.created_at} />
          </div>
          <p className="mt-0.5 break-words text-[13px] text-ink-soft">
            {ev.payload.titel ? `„${ev.payload.titel}" — ` : ''}
            {ev.payload.distance_km} km →{' '}
            <span className="font-bold text-accent">{ev.payload.mm} MM</span>
          </p>
        </>
      )}
      {ev.type === 'rank_change' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>📈</span>
          <span className="text-ink">
            <b>{ev.payload.name}</b> überholt <b>{ev.payload.ueberholt_name}</b> → Platz{' '}
            {ev.payload.neuer_rang}
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {(ev.type === 'achievement' || ev.type === 'milestone') && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏆</span>
          <span className="text-ink">
            <b>{ev.display_name}</b>{' '}
            {ev.type === 'achievement' ? (
              <>
                hat <b>{ev.payload.emoji ? `${ev.payload.emoji} ` : ''}{ev.payload.title}</b>{' '}
                freigeschaltet
              </>
            ) : (
              <>
                hat den Meilenstein <b>{ev.payload.label}</b> erreicht ({ev.payload.km} km)
              </>
            )}
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {(ev.type === 'recap_week' || ev.type === 'recap_month') && <RecapCard ev={ev} />}
      <ReactionBar ev={ev} />
    </div>
  )
}

function Zeit({ iso }: { iso: string }) {
  const t = new Date(iso)
  return (
    <span className="ml-auto shrink-0 text-[11px] text-ink-mute">
      {t.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
    </span>
  )
}
```

`pages/Feed.tsx`:

```tsx
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../api/client'
import type { FeedEvent } from '../api/client'
import FeedItem from '../components/feed/FeedItem'
import { aktiveSeason } from '../components/ui/season'

function tagLabel(iso: string): string {
  const d = new Date(iso)
  const heute = new Date()
  const gestern = new Date(heute)
  gestern.setDate(heute.getDate() - 1)
  const gleicherTag = (a: Date, b: Date) => a.toDateString() === b.toDateString()
  if (gleicherTag(d, heute)) return 'Heute'
  if (gleicherTag(d, gestern)) return 'Gestern'
  const tage = (heute.getTime() - d.getTime()) / 86_400_000
  if (tage < 7) return d.toLocaleDateString('de-DE', { weekday: 'long' })
  return d.toLocaleDateString('de-DE')
}

export default function Feed() {
  const queryClient = useQueryClient()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const year = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const { data, error, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['feed', year],
    queryFn: ({ pageParam }) => api.feed(year, pageParam ?? undefined),
    initialPageParam: null as number | null,
    getNextPageParam: (last) => last.next_before,
    enabled: seasons.length > 0,
  })
  useEffect(() => {
    api.markFeedSeen().then(() => {
      queryClient.invalidateQueries({ queryKey: ['feed-unseen'] })
    }).catch(() => {})
  }, [queryClient])

  const events: FeedEvent[] = data?.pages.flatMap((p) => p.events) ?? []
  let letzterTag = ''
  if (error) return <p className="text-sm text-danger">{error.message}</p>
  return (
    <div className="mx-auto max-w-xl space-y-2.5">
      {events.map((ev) => {
        const tag = tagLabel(ev.created_at)
        const trenner = tag !== letzterTag
        letzterTag = tag
        return (
          <div key={ev.id} className="space-y-2.5">
            {trenner && (
              <p className="px-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-ink-mute">
                {tag}
              </p>
            )}
            <FeedItem ev={ev} />
          </div>
        )
      })}
      {events.length === 0 && (
        <p className="p-8 text-center text-sm text-ink-mute">
          Noch nichts passiert — trag eine Aktivität ein!
        </p>
      )}
      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="w-full rounded-xl border border-line py-2 text-sm text-ink-mute transition hover:text-ink"
        >
          {isFetchingNextPage ? 'Lädt…' : 'Mehr laden …'}
        </button>
      )}
    </div>
  )
}
```

Damit das kompiliert, in diesem Task auch minimale `RecapCard.tsx`/`ReactionBar.tsx` in `components/feed/` anlegen (echte Implementierung in Task 9):

```tsx
// ReactionBar.tsx (Platzhalter, Task 9 füllt ihn)
import type { FeedEvent } from '../../api/client'
export default function ReactionBar({ ev }: { ev: FeedEvent }) {
  if (ev.reactions.length === 0) return null
  return (
    <div className="mt-2 flex gap-1.5">
      {ev.reactions.map((r) => (
        <span key={r.emoji} className="rounded-full border border-line px-2 py-0.5 text-xs">
          {r.emoji} {r.count}
        </span>
      ))}
    </div>
  )
}
```

```tsx
// RecapCard.tsx (Platzhalter, Task 9 füllt ihn)
import type { FeedEvent } from '../../api/client'
export default function RecapCard({ ev }: { ev: FeedEvent }) {
  return <p className="text-sm font-bold text-ink">📊 Rückblick {ev.payload.label}</p>
}
```

- [ ] **Step 4:** `npx vitest run src/pages/Feed.test.tsx && npm run build` → PASS/OK.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Feed-Seite mit Eintraegen, Tages-Trennern und Mehr-laden"`.

---

### Task 9: ReactionBar (Toggle + Auswahl) und RecapCard (Mini-Rennen)

**Files:**
- Modify: `frontend/src/components/feed/ReactionBar.tsx`, `frontend/src/components/feed/RecapCard.tsx`
- Test (create): `frontend/src/components/feed/ReactionBar.test.tsx`

- [ ] **Step 1: Failing Test:**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { vi } from 'vitest'
import type { FeedEvent } from '../../api/client'
import { api } from '../../api/client'
import ReactionBar from './ReactionBar'

vi.mock('../../api/client', async (orig) => {
  const mod = (await orig()) as object
  return { ...mod, api: { toggleFeedReaction: vi.fn().mockResolvedValue([]) } }
})

const ev = {
  id: 1, type: 'activity', user_id: 1, display_name: 'Anna', avatar: '🦊',
  created_at: new Date().toISOString(), payload: {},
  reactions: [{ emoji: '🔥', count: 2, mine: true, users: ['Ben', 'Clara'] }],
} as FeedEvent

function mount() {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <ReactionBar ev={ev} />
    </QueryClientProvider>,
  )
}

it('zeigt Chips und oeffnet die Auswahl', () => {
  mount()
  expect(screen.getByText(/🔥/)).toBeInTheDocument()
  fireEvent.click(screen.getByLabelText('Reagieren'))
  expect(screen.getByText('👏')).toBeInTheDocument()
})

it('togglet beim Klick auf einen Chip', () => {
  mount()
  fireEvent.click(screen.getByText(/🔥/))
  expect(api.toggleFeedReaction).toHaveBeenCalledWith(1, '🔥')
})
```

- [ ] **Step 2:** `npx vitest run src/components/feed/ReactionBar.test.tsx` → FAIL.

- [ ] **Step 3: Implementieren.** `ReactionBar.tsx`:

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { FeedEvent } from '../../api/client'

export const REACTION_EMOJIS = ['👏', '🔥', '💪', '😂', '😮'] as const

export default function ReactionBar({ ev }: { ev: FeedEvent }) {
  const queryClient = useQueryClient()
  const [auswahlOffen, setAuswahlOffen] = useState(false)
  const [namenFuer, setNamenFuer] = useState<string | null>(null)
  const toggle = useMutation({
    mutationFn: (emoji: string) => api.toggleFeedReaction(ev.id, emoji),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['feed'] }),
  })
  return (
    <div className="relative mt-2 flex flex-wrap items-center gap-1.5">
      {ev.reactions.map((r) => (
        <button
          key={r.emoji}
          onClick={() => toggle.mutate(r.emoji)}
          onMouseEnter={() => setNamenFuer(r.emoji)}
          onMouseLeave={() => setNamenFuer(null)}
          className={`rounded-full border px-2 py-0.5 text-xs transition ${
            r.mine
              ? 'border-accent bg-accent/10 text-ink'
              : 'border-line bg-surface text-ink-soft hover:text-ink'
          }`}
        >
          {r.emoji} {r.count}
          {namenFuer === r.emoji && r.users.length > 0 && (
            <span className="absolute bottom-full left-0 z-40 mb-1 rounded-lg border border-line bg-card px-2 py-1 text-[11px] text-ink-mute shadow-lg">
              {r.users.join(', ')}
            </span>
          )}
        </button>
      ))}
      <button
        aria-label="Reagieren"
        onClick={() => setAuswahlOffen((o) => !o)}
        className="rounded-full border border-dashed border-line px-2 py-0.5 text-xs text-ink-mute hover:text-ink"
      >
        ＋
      </button>
      {auswahlOffen && (
        <span className="flex gap-1.5 rounded-full border border-line bg-card px-2.5 py-1 shadow-lg">
          {REACTION_EMOJIS.map((e) => (
            <button
              key={e}
              onClick={() => {
                toggle.mutate(e)
                setAuswahlOffen(false)
              }}
              className="text-sm transition hover:scale-125"
            >
              {e}
            </button>
          ))}
        </span>
      )}
    </div>
  )
}
```

`RecapCard.tsx` („Mini-Rennen", Personen-Farben wie im Vergleich):

```tsx
import type { FeedEvent } from '../../api/client'
import { userColor } from '../comparison/userColor'

export default function RecapCard({ ev }: { ev: FeedEvent }) {
  const p = ev.payload
  const perUser = p.per_user ?? []
  const ids = perUser.map((e) => e.user_id)
  const max = Math.max(1, ...perUser.map((e) => e.mm))
  const art = ev.type === 'recap_week' ? 'Wochenrückblick' : 'Monatsrückblick'
  return (
    <div>
      <p className="text-sm font-bold text-ink">
        📊 {art} · {p.label}
      </p>
      <p className="mt-0.5 text-xs text-ink-mute">
        Gruppe gesamt: <b className="text-accent">{p.total_mm} MM</b>
      </p>
      <div className="mt-2 space-y-1.5">
        {perUser.map((e) => (
          <div key={e.user_id} className="flex items-center gap-2 text-xs">
            <span className="w-14 shrink-0 truncate text-ink-soft">{e.name}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full border border-line bg-surface">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(e.mm / max) * 100}%`,
                  background: `linear-gradient(90deg, transparent, ${userColor(e.user_id, ids)})`,
                }}
              />
            </div>
            <span className="w-14 shrink-0 text-right font-mono font-bold tabular-nums text-ink">
              {Math.round(e.mm)} MM
            </span>
          </div>
        ))}
      </div>
      {((p.ueberholungen?.length ?? 0) > 0 || (p.achievements?.length ?? 0) > 0) && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-mute">
          {(p.ueberholungen?.length ?? 0) > 0 && (
            <span>
              📈{' '}
              {p.ueberholungen!
                .map((u) => `${u.name} → P${u.neuer_rang}`)
                .join(' · ')}
            </span>
          )}
          {(p.achievements?.length ?? 0) > 0 && (
            <span>
              🏆{' '}
              {p.achievements!
                .map((a) => a.emoji ? `${a.emoji} ${a.title ?? a.label ?? ''}` : (a.title ?? a.label ?? ''))
                .join(' · ')}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
```

Hinweis: In der Rückblick-Fußzeile steht `P{rang}` NICHT — nach PR 1 gilt „ohne P": `→ Platz {u.neuer_rang}` verwenden, falls der Platz reicht, sonst kürzen auf `→ {u.neuer_rang}.`; an PR-1-Konvention halten.

- [ ] **Step 4:** `npx vitest run src/components/feed && npm run build` → PASS/OK.
- [ ] **Step 5: Commit** — `git commit -m "feat(feed): Reaktions-Toggle mit festem Emoji-Set und Rueckblick-Karte (Mini-Rennen)"`.

---

### Task 10: Gesamtverifikation + PR

- [ ] **Step 1:** `cd backend && uv run pytest -q` → PASS.
- [ ] **Step 2:** `cd frontend && npx vitest run && npm run build` → PASS/OK.
- [ ] **Step 3:** Manuell im Dev-Setup: Aktivität eintragen → Feed-Eintrag erscheint, Punkt am Tab bei zweitem Nutzer, Reaktion togglen, „Mehr laden" bei >30 Events. Mobile Breite prüfen.
- [ ] **Step 4:** Push + PR:

```bash
git push -u origin feature/newsfeed
gh pr create --title "Newsfeed: Feed-Tab mit Events, Reaktionen und Rueckblicken" --body "Setzt Teil B der Spec docs/superpowers/specs/2026-07-25-anpassungen-und-newsfeed-design.md um."
```

## Self-Review (erledigt)

- Spec-Abdeckung: B1→Task 1, B2→Tasks 2/3/4/5, B3→Task 6, B4→Tasks 7/8/9, B5 (Löschen/Bearbeiten/Launch-Guard)→Tasks 2/4/5, B6 (Index/Cursor)→Tasks 1/6.
- Typkonsistenz: `payload`-Felder (`category.color`, `mm`, `titel`, `name`, `ueberholt_name`, `neuer_rang`, `label`, `period`, `per_user`, `ueberholungen`, `achievements`) sind zwischen Service (Tasks 2/3/5), API (Task 6) und `client.ts` (Task 7) identisch benannt.
- Bewusste Entscheidungen: Aktivitäts-Farbbalken nutzt die vorhandene `Category.color` (statt neuer Palette) — konsistent mit Verlauf/Sport-Mix. Löschen wird explizit im Code aufgeräumt statt über FK-Cascade (SQLite-Pragma-Falle). Rückblick nur, wenn im Zeitraum Feed-Events existieren — implementiert den Launch-Guard aus B5 ohne Extra-Konstante.
- Kein Cron: Rückblicke hängen am `GET /api/feed` (`ensure_recaps`), wie `ensure_monthly_tip`.
