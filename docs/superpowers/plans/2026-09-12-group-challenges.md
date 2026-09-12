# Group Challenges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin run a challenge as a group challenge: seeded random draw into N groups, hand-editable while planned, scored per head, with a group or a person as prize winner.

**Architecture:** Group challenges are a dimension of the existing `Challenge` row (five new columns, groups stored as JSON). Seeding, draw and editing live in a new `services/challenge_groups.py`; pure group aggregation (`group_standings`) and the JSON helpers live in `services/challenges.py` so there is no circular import. The router gains four endpoints and extends `ChallengeOut`. The frontend gets a group editor page, group cards in the detail view, and group-aware texts.

**Tech Stack:** FastAPI + SQLModel + SQLite (backend, `backend/.venv/Scripts/python.exe -m pytest`), React 19 + TanStack Query + Tailwind + Vitest (frontend, `npm test`, `npm run lint`, `npm run build` in `frontend/`).

**Spec:** `docs/superpowers/specs/2026-09-12-group-challenges-design.md`

**Conventions:**
- Code, comments and commit messages in English; UI copy in German. Existing German identifiers (`teilnehmer_ids`, `_einfrieren`, `heute`, …) stay.
- Backend commands run from `backend/`: `.venv/Scripts/python.exe -m pytest tests/test_x.py -q`.
- Frontend commands run from `frontend/`: `npx vitest run src/path/file.test.tsx`.
- Pre-existing ESLint errors in `Feed.tsx` / `ReactionBar.tsx` are known; do not fix them here.
- Multi-line files: write with the Write tool, not bash heredocs (this Windows setup mangles backslashes and quotes in heredocs).
- Commit after every task. End every commit message with:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_012KrtS1A3RAQan4QLRcM2we
  ```

---

## File structure

| File | Responsibility |
| --- | --- |
| `backend/app/models.py` | five new `Challenge` columns |
| `backend/app/db.py` | `migrate()` adds them to existing DBs |
| `backend/app/services/challenges.py` | JSON helpers `groups`, `group_member_ids`, `remove_group_member`; `rows_between`; pure `group_standings`; freeze/lifecycle/sieger learn about groups |
| `backend/app/services/challenge_groups.py` | new: `pool`, `seeding_value`, `seeding`, `draw`, `validate_groups`, `save_groups` |
| `backend/app/services/feed.py` | group payloads, per-group qualified event |
| `backend/app/routers/challenges.py` | schemas, rule checks, four new endpoints, `_challenge_out` additions |
| `backend/tests/test_challenge_groups.py` | new: service tests |
| `backend/tests/test_challenge_groups_api.py` | new: endpoint tests |
| `backend/tests/test_migration.py`, `test_feed.py` | additions |
| `frontend/src/api/client.ts` | types and API functions |
| `frontend/src/components/challenges/wertung.ts` | group texts, `meineGruppe` |
| `frontend/src/components/admin/ChallengesAdmin.tsx` | checkbox, fields, editor link |
| `frontend/src/components/challenges/GroupCard.tsx` | new: one group in the detail view |
| `frontend/src/components/challenges/ChallengeDetail.tsx` | group view, group winner select |
| `frontend/src/components/challenges/ChallengeRow.tsx`, `ChallengeHeroCard.tsx` | group texts |
| `frontend/src/components/challenges/GroupEditor.tsx` | new: admin editor page |
| `frontend/src/components/feed/FeedItem.tsx` | group payload rendering |
| `frontend/src/App.tsx` | editor route |

---

### Task 1: Model columns and migration

**Files:**
- Modify: `backend/app/models.py` (class `Challenge`, after `resolved_at`)
- Modify: `backend/app/db.py` (`migrate()`, before the `stravaconnection` block)
- Test: `backend/tests/test_migration.py`

- [ ] **Step 1: Write the failing migration test**

Append to `backend/tests/test_migration.py`:

```python
def test_migrate_adds_group_columns_to_challenge():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE challenge (id INTEGER PRIMARY KEY, title VARCHAR, "
            "description VARCHAR, creator_id INTEGER, prize VARCHAR, mode VARCHAR, "
            "target FLOAT, top_n INTEGER, metric VARCHAR, category_ids_json VARCHAR, "
            "streak_min_mm FLOAT, join_mode VARCHAR, period_start DATE, period_end DATE, "
            "status VARCHAR, result_json VARCHAR, created_at DATETIME, resolved_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO challenge (title, description, creator_id, mode, top_n, metric, "
            "category_ids_json, streak_min_mm, join_mode, period_start, period_end, status, "
            "result_json, created_at) VALUES ('Alt', '', 1, 'ziel', 1, 'mm', '[]', 5.0, "
            "'auto', '2026-08-01', '2026-08-31', 'beendet', '{}', '2026-08-01 00:00:00')"
        ))
    migrate(engine)
    with engine.begin() as conn:
        cols = [r[1] for r in conn.execute(text('PRAGMA table_info("challenge")'))]
        assert {"team_mode", "group_count", "seeding_days", "groups_json", "groups_drawn_at"} <= set(cols)
        row = conn.execute(text(
            "SELECT team_mode, group_count, seeding_days, groups_json FROM challenge"
        )).fetchone()
        assert row[0] == 0 and row[1] is None and row[2] == 30 and row[3] == "[]"
```

- [ ] **Step 2: Run it, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_migration.py::test_migrate_adds_group_columns_to_challenge -q`
Expected: FAIL (assertion on missing columns).

- [ ] **Step 3: Add the columns to the model**

In `backend/app/models.py`, class `Challenge`, after `resolved_at: datetime | None = None`:

```python
    # Group challenges (spec 2026-09-12). Groups live in groups_json:
    # [{"id": 1, "name": "Gruppe A", "member_ids": [3, 7]}]. Ids are small
    # integers unique within the challenge, not database ids.
    team_mode: bool = False
    group_count: int | None = None  # required when team_mode, >= 2
    seeding_days: int = 30  # window for the seeding list
    groups_json: str = "[]"
    groups_drawn_at: datetime | None = None
```

- [ ] **Step 4: Add the migration**

In `backend/app/db.py`, inside `migrate()`, before `if _table_exists(conn, "stravaconnection"):`:

```python
        if _table_exists(conn, "challenge"):
            ch_cols = _columns(conn, "challenge")
            if "team_mode" not in ch_cols:
                conn.execute(text(
                    "ALTER TABLE challenge ADD COLUMN team_mode BOOLEAN NOT NULL DEFAULT 0"
                ))
            if "group_count" not in ch_cols:
                conn.execute(text("ALTER TABLE challenge ADD COLUMN group_count INTEGER"))
            if "seeding_days" not in ch_cols:
                conn.execute(text(
                    "ALTER TABLE challenge ADD COLUMN seeding_days INTEGER NOT NULL DEFAULT 30"
                ))
            if "groups_json" not in ch_cols:
                conn.execute(text(
                    "ALTER TABLE challenge ADD COLUMN groups_json TEXT NOT NULL DEFAULT '[]'"
                ))
            if "groups_drawn_at" not in ch_cols:
                conn.execute(text("ALTER TABLE challenge ADD COLUMN groups_drawn_at DATETIME"))
```

- [ ] **Step 5: Run the migration tests and the existing challenge tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_migration.py tests/test_challenges_api.py tests/test_challenges_lifecycle.py tests/test_challenges_metrics.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_migration.py
git commit -m "feat(challenges): group challenge columns and migration"
```

---

### Task 2: JSON helpers, `rows_between`, and pure `group_standings`

**Files:**
- Modify: `backend/app/services/challenges.py`
- Test: `backend/tests/test_challenge_groups.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_challenge_groups.py`:

```python
"""Group challenges (spec 2026-09-12): helpers, seeding, draw, editing."""

import json
import random
from datetime import date, timedelta

from app.models import Activity, Challenge, ChallengeParticipant
from app.services import challenges as svc
from tests.conftest import make_category, make_user


def make_team_challenge(session, **kw) -> Challenge:
    heute = date.today()
    daten = dict(
        title="Teams", creator_id=1, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute + timedelta(days=1),
        period_end=heute + timedelta(days=30), status="geplant",
        team_mode=True, group_count=2, seeding_days=30,
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def add_activity(session, user_id, cat_id, tag, km):
    session.add(Activity(user_id=user_id, category_id=cat_id, date=tag, distance_km=km))
    session.commit()


def groups_of(*member_lists):
    return [
        {"id": i + 1, "name": f"Gruppe {chr(65 + i)}", "member_ids": list(m)}
        for i, m in enumerate(member_lists)
    ]


# --- JSON helpers -----------------------------------------------------------

def test_group_helpers_read_and_remove(session):
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2], [3])))
    assert svc.group_member_ids(ch) == [1, 2, 3]
    svc.remove_group_member(ch, 2)
    assert svc.groups(ch) == groups_of([1], [3])
    svc.remove_group_member(ch, 99)  # unknown id is a no-op
    assert svc.group_member_ids(ch) == [1, 3]


# --- group_standings (pure) -------------------------------------------------

def entry(uid, value):
    """One per-person entry as standings() returns it."""
    return {"user_id": uid, "value": value, "rank": 0, "geschafft": False, "nicht_mehr_schaffbar": False}


def test_group_standings_per_head_target(session):
    ch = make_team_challenge(session, target=100.0, groups_json=json.dumps(groups_of([1, 2, 3], [4, 5])))
    e = [entry(1, 150.0), entry(2, 90.0), entry(3, 60.0), entry(4, 100.0), entry(5, 120.0)]
    out = svc.group_standings(ch, e)
    # group B: (100+120)/2 = 110 >= 100, group A: 300/3 = 100 >= 100
    b, a = out
    assert (b["id"], b["sum"], b["value"], b["rank"], b["geschafft"]) == (2, 220.0, 110.0, 1, True)
    assert (a["id"], a["sum"], a["value"], a["rank"], a["geschafft"]) == (1, 300.0, 100.0, 2, True)
    assert [m["user_id"] for m in a["members"]] == [1, 2, 3]  # sorted by value desc
    assert a["size"] == 3 and a["member_ids"] == [1, 2, 3]


def test_group_standings_ranking_mode_ties_and_top_n(session):
    ch = make_team_challenge(
        session, mode="rangliste", top_n=1,
        groups_json=json.dumps(groups_of([1], [2], [3])), group_count=3,
    )
    e = [entry(1, 50.0), entry(2, 50.0), entry(3, 10.0)]
    out = svc.group_standings(ch, e)
    assert [(g["id"], g["rank"], g["geschafft"]) for g in out] == [(1, 1, True), (2, 1, True), (3, 3, False)]


def test_group_standings_ignores_members_missing_from_entries(session):
    # An inactive member is not in the entries (teilnehmer_ids filters them):
    # it drops out of sum and divisor. A group with no scored member is 0.
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([1, 2], [3])))
    out = svc.group_standings(ch, [entry(1, 80.0)])
    a = next(g for g in out if g["id"] == 1)
    b = next(g for g in out if g["id"] == 2)
    assert (a["sum"], a["value"], a["size"], a["member_ids"]) == (80.0, 80.0, 1, [1])
    assert (b["sum"], b["value"], b["size"], b["member_ids"]) == (0.0, 0.0, 0, [])


# --- rows_between -----------------------------------------------------------

def test_rows_between_uses_window_and_category_filter(session):
    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    rad = make_category(session, name="Rad", factor=0.5)
    ch = make_team_challenge(session, category_ids_json=json.dumps([lauf.id]))
    add_activity(session, u.id, lauf.id, date(2026, 8, 1), 10.0)
    add_activity(session, u.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, u.id, rad.id, date(2026, 8, 5), 10.0)
    add_activity(session, u.id, lauf.id, date(2026, 8, 9), 10.0)
    rows = svc.rows_between(session, u.id, ch, date(2026, 8, 2), date(2026, 8, 8))
    assert [a.date for a, _ in rows] == [date(2026, 8, 5)]
```

- [ ] **Step 2: Run, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q`
Expected: FAIL with `AttributeError: module 'app.services.challenges' has no attribute 'group_member_ids'` (and similar).

- [ ] **Step 3: Add helpers and `rows_between` to `services/challenges.py`**

Replace the existing `_rows` function with:

```python
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
    """Aktivitaeten des Users im Challenge-Zeitraum, Kategorie-gefiltert."""
    ende = ch.period_end if bis is None else min(ch.period_end, bis)
    return rows_between(session, user_id, ch, ch.period_start, ende)
```

After `category_ids(ch)` add the group JSON helpers:

```python
def groups(ch: Challenge) -> list[dict]:
    """[{"id": 1, "name": "Gruppe A", "member_ids": [3, 7]}] — empty until drawn."""
    return json.loads(ch.groups_json or "[]")


def set_groups(ch: Challenge, gruppen: list[dict]) -> None:
    ch.groups_json = json.dumps(gruppen)


def group_member_ids(ch: Challenge) -> list[int]:
    return [uid for g in groups(ch) for uid in g["member_ids"]]


def remove_group_member(ch: Challenge, user_id: int) -> None:
    """Used when a person leaves a planned group challenge. No-op if absent."""
    gruppen = groups(ch)
    for g in gruppen:
        g["member_ids"] = [uid for uid in g["member_ids"] if uid != user_id]
    set_groups(ch, gruppen)


def group_of(ch: Challenge, user_id: int) -> dict | None:
    return next((g for g in groups(ch) if user_id in g["member_ids"]), None)
```

After `standings(...)` add the pure aggregation:

```python
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


def group_standings(ch: Challenge, eintraege: list[dict]) -> list[dict]:
    """Aggregate per-person entries (output of standings()) into groups.
    Pure: members missing from eintraege (inactive) drop out of sum and
    divisor. Value is per head; target is per head."""
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
            g["geschafft"] = ch.target is not None and g["value"] >= ch.target
        else:
            g["geschafft"] = g["rank"] <= ch.top_n
    return result
```

Also replace the inline ranking loop inside `standings()` with a call to `_rank(eintraege)` (same behaviour, one implementation):

```python
    eintraege.sort(key=lambda e: (-e["value"], e["user_id"]))
    _rank(eintraege)
```

(`_rank` must be defined above `standings` — place `_rank` right before `standings`, and `group_standings` right after it.)

- [ ] **Step 4: Run the new tests and the existing challenge tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py tests/test_challenges_metrics.py tests/test_challenges_lifecycle.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/tests/test_challenge_groups.py
git commit -m "feat(challenges): group json helpers, rows_between and pure group_standings"
```

---

### Task 3: Seeding and pool (`services/challenge_groups.py`)

**Files:**
- Create: `backend/app/services/challenge_groups.py`
- Test: `backend/tests/test_challenge_groups.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_challenge_groups.py`:

```python
# --- pool and seeding --------------------------------------------------------

def test_pool_auto_is_all_active_users(session):
    from app.services import challenge_groups as cg

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_team_challenge(session, join_mode="auto")
    assert cg.pool(session, ch) == sorted([a.id, b.id])


def test_pool_opt_in_is_joined_active_users(session):
    from app.services import challenge_groups as cg

    a = make_user(session, username="anna")
    make_user(session, username="ben")
    ch = make_team_challenge(session, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.commit()
    assert cg.pool(session, ch) == [a.id]


def test_seeding_window_is_last_n_days_up_to_yesterday(session):
    from app.services import challenge_groups as cg

    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=2.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, seeding_days=7)
    add_activity(session, u.id, lauf.id, heute, 100.0)                      # today: excluded
    add_activity(session, u.id, lauf.id, heute - timedelta(days=1), 10.0)   # in
    add_activity(session, u.id, lauf.id, heute - timedelta(days=7), 10.0)   # in (7 days back)
    add_activity(session, u.id, lauf.id, heute - timedelta(days=8), 10.0)   # out
    assert cg.seeding_value(session, u.id, ch, heute) == 40.0  # 2 × 10 km × factor 2


def test_seeding_uses_category_filter_and_ignores_km_factor(session):
    from app.services import challenge_groups as cg

    u = make_user(session, username="anna")
    u.km_factor = 5.0
    session.add(u)
    session.commit()
    lauf = make_category(session, name="Joggen", factor=1.0)
    rad = make_category(session, name="Rad", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, category_ids_json=json.dumps([lauf.id]))
    add_activity(session, u.id, lauf.id, heute - timedelta(days=2), 10.0)
    add_activity(session, u.id, rad.id, heute - timedelta(days=2), 50.0)
    assert cg.seeding_value(session, u.id, ch, heute) == 10.0


def test_seeding_anzahl_counts_activities(session):
    from app.services import challenge_groups as cg

    u = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session, metric="anzahl")
    add_activity(session, u.id, lauf.id, heute - timedelta(days=2), 1.0)
    add_activity(session, u.id, lauf.id, heute - timedelta(days=3), 1.0)
    assert cg.seeding_value(session, u.id, ch, heute) == 2.0


def test_seeding_sorted_desc_ties_by_user_id(session):
    from app.services import challenge_groups as cg

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date(2026, 9, 12)
    ch = make_team_challenge(session)
    add_activity(session, b.id, lauf.id, heute - timedelta(days=1), 30.0)
    add_activity(session, a.id, lauf.id, heute - timedelta(days=1), 10.0)
    add_activity(session, c.id, lauf.id, heute - timedelta(days=1), 10.0)
    assert cg.seeding(session, ch, heute) == [(b.id, 30.0), (a.id, 10.0), (c.id, 10.0)]
```

- [ ] **Step 2: Run, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q -k "pool or seeding"`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.challenge_groups'`.

- [ ] **Step 3: Create the module**

Create `backend/app/services/challenge_groups.py`:

```python
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

from ..models import Challenge, ChallengeParticipant, User
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


def _joined_ids(session: Session, ch: Challenge) -> set[int]:
    if ch.id is None:
        return set()
    rows = session.exec(
        select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == ch.id)
    ).all()
    return {r.user_id for r in rows}


def pool(session: Session, ch: Challenge) -> list[int]:
    """Who can be drawn: auto = every active user, opt_in = joined and active."""
    aktive = _active_ids(session)
    if ch.join_mode == "auto":
        return sorted(aktive)
    return sorted(uid for uid in _joined_ids(session, ch) if uid in aktive)


def seeding_value(session: Session, user_id: int, ch: Challenge, heute: date_type) -> float:
    """The challenge's own metric over the last seeding_days days up to and
    including yesterday. Never uses User.km_factor."""
    bis = heute - timedelta(days=1)
    von = heute - timedelta(days=ch.seeding_days)
    rows = svc.rows_between(session, user_id, ch, von, bis)
    if ch.metric == "anzahl":
        return float(len(rows))
    resolver = FactorResolver.load(session)
    return round(sum(resolver.mm(a) for a, _ in rows), 2)


def seeding(
    session: Session, ch: Challenge, heute: date_type, user_ids: list[int] | None = None
) -> list[tuple[int, float]]:
    """(user_id, value) sorted by value desc, ties by user_id. Defaults to the pool."""
    ids = pool(session, ch) if user_ids is None else user_ids
    werte = [(uid, seeding_value(session, uid, ch, heute)) for uid in ids]
    werte.sort(key=lambda t: (-t[1], t[0]))
    return werte
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/challenge_groups.py backend/tests/test_challenge_groups.py
git commit -m "feat(challenges): seeding list and draw pool for group challenges"
```

---

### Task 4: The draw

**Files:**
- Modify: `backend/app/services/challenge_groups.py`
- Test: `backend/tests/test_challenge_groups.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_challenge_groups.py`:

```python
# --- draw -------------------------------------------------------------------

def _seeded_users(session, n, heute):
    """n users; user k has k × 10 MM yesterday, so seeding order = reverse creation."""
    lauf = make_category(session, name="Joggen", factor=1.0)
    users = [make_user(session, username=f"u{k}") for k in range(n)]
    for k, u in enumerate(users):
        add_activity(session, u.id, lauf.id, heute - timedelta(days=1), (k + 1) * 10.0)
    return users


def test_draw_spreads_every_pot_over_distinct_groups(session):
    from app.services import challenge_groups as cg

    heute = date(2026, 9, 12)
    users = _seeded_users(session, 9, heute)
    ch = make_team_challenge(session, group_count=3)
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(7))
    assert [g["name"] for g in gruppen] == ["Gruppe A", "Gruppe B", "Gruppe C"]
    assert sorted(uid for g in gruppen for uid in g["member_ids"]) == sorted(u.id for u in users)
    order = [uid for uid, _ in cg.seeding(session, ch, heute)]
    for start in range(0, 9, 3):
        pot = order[start:start + 3]
        gruppen_ids = {next(g["id"] for g in gruppen if uid in g["member_ids"]) for uid in pot}
        assert len(gruppen_ids) == 3, f"pot {pot} not spread"
    assert svc.groups(ch) == gruppen
    assert ch.groups_drawn_at is not None


def test_draw_partial_last_pot_sizes_differ_by_at_most_one(session):
    from app.services import challenge_groups as cg

    heute = date(2026, 9, 12)
    _seeded_users(session, 8, heute)
    ch = make_team_challenge(session, group_count=3)
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(3))
    sizes = sorted(len(g["member_ids"]) for g in gruppen)
    assert sizes == [2, 3, 3]


def test_draw_keeps_existing_names(session):
    from app.services import challenge_groups as cg

    heute = date(2026, 9, 12)
    _seeded_users(session, 4, heute)
    ch = make_team_challenge(session, group_count=2)
    svc.set_groups(ch, [{"id": 1, "name": "Die Flitzer", "member_ids": []},
                        {"id": 2, "name": "Gruppe B", "member_ids": []}])
    gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(1))
    assert [g["name"] for g in gruppen] == ["Die Flitzer", "Gruppe B"]


def test_draw_is_random_inside_a_pot(session):
    from app.services import challenge_groups as cg

    heute = date(2026, 9, 12)
    _seeded_users(session, 6, heute)
    ch = make_team_challenge(session, group_count=2)
    seen = set()
    for seed in range(10):
        gruppen = cg.draw(session, ch, heute, jetzt=None, rng=random.Random(seed))
        seen.add(tuple(gruppen[0]["member_ids"]))
    assert len(seen) > 1


def test_draw_needs_at_least_group_count_people(session):
    import pytest
    from app.services import challenge_groups as cg

    heute = date(2026, 9, 12)
    make_user(session, username="anna")
    ch = make_team_challenge(session, group_count=2)
    with pytest.raises(cg.TooFewPeople):
        cg.draw(session, ch, heute, jetzt=None)
```

- [ ] **Step 2: Run, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q -k draw`
Expected: FAIL with `AttributeError: ... has no attribute 'draw'`.

- [ ] **Step 3: Implement `draw`**

Append to `backend/app/services/challenge_groups.py`:

```python
def draw(
    session: Session,
    ch: Challenge,
    heute: date_type,
    jetzt: datetime | None,
    rng: random.Random | None = None,
) -> list[dict]:
    """Seeded random draw. Pots of group_count by seeding rank; inside a pot
    the assignment to groups is random; the partial last pot goes to random
    distinct groups, so sizes differ by at most one. Existing names are kept
    by group id. Writes groups_json / groups_drawn_at on ch but does NOT
    commit — the caller decides (create wants to validate before commit)."""
    rng = rng or random.Random()
    n = ch.group_count or 0
    order = [uid for uid, _ in seeding(session, ch, heute)]
    if len(order) < n:
        raise TooFewPeople("Weniger Personen als Gruppen")
    namen = {g["id"]: g["name"] for g in svc.groups(ch)}
    result = [
        {"id": i + 1, "name": namen.get(i + 1, default_name(i)), "member_ids": []}
        for i in range(n)
    ]
    for start in range(0, len(order), n):
        pot = order[start:start + n]
        rng.shuffle(pot)
        ziele = list(range(n)) if len(pot) == n else rng.sample(range(n), len(pot))
        for uid, gi in zip(pot, ziele):
            result[gi]["member_ids"].append(uid)
    svc.set_groups(ch, result)
    ch.groups_drawn_at = jetzt or datetime.now(timezone.utc)
    return result
```

Add `timezone` to the datetime import at the top: `from datetime import datetime, timedelta, timezone`.

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/challenge_groups.py backend/tests/test_challenge_groups.py
git commit -m "feat(challenges): seeded random draw into groups"
```

---

### Task 5: Validating and saving edited groups

**Files:**
- Modify: `backend/app/services/challenge_groups.py`
- Test: `backend/tests/test_challenge_groups.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_challenge_groups.py`:

```python
# --- validate_groups / save_groups -------------------------------------------

def test_save_groups_accepts_clean_list_and_trims_names(session):
    from app.services import challenge_groups as cg

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    ch = make_team_challenge(session, group_count=2)
    out = cg.save_groups(session, ch, [
        {"id": 1, "name": "  Flitzer ", "member_ids": [a.id]},
        {"id": 2, "name": "Gruppe B", "member_ids": [b.id]},
    ])
    assert out[0]["name"] == "Flitzer"
    session.refresh(ch)
    assert svc.group_member_ids(ch) == [a.id, b.id]


def test_save_groups_rejects_bad_lists(session):
    import pytest
    from app.services import challenge_groups as cg

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_team_challenge(session, group_count=2)
    ok = {"id": 2, "name": "B", "member_ids": [b.id]}
    cases = [
        ([{"id": 1, "name": "A", "member_ids": [a.id]}], "genau 2 Gruppen"),
        ([{"id": 1, "name": "A", "member_ids": [a.id, b.id]}, ok], "zwei Gruppen"),
        ([{"id": 1, "name": "A", "member_ids": [c.id]}, ok], "inaktive"),
        ([{"id": 1, "name": "A", "member_ids": [999]}, ok], "inaktive"),
        ([{"id": 1, "name": "  ", "member_ids": [a.id]}, ok], "Namen"),
        ([{"id": 1, "name": "A", "member_ids": []}, ok], "leer"),
        ([{"id": 2, "name": "A", "member_ids": [a.id]}, ok], "Gruppen-ID"),
    ]
    for gruppen, text in cases:
        with pytest.raises(cg.InvalidGroups, match=text):
            cg.save_groups(session, ch, gruppen)


def test_save_groups_opt_in_adds_participant_rows(session):
    from sqlmodel import select
    from app.services import challenge_groups as cg

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    ch = make_team_challenge(session, group_count=2, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.commit()
    cg.save_groups(session, ch, [
        {"id": 1, "name": "A", "member_ids": [a.id]},
        {"id": 2, "name": "B", "member_ids": [b.id]},
    ])
    rows = session.exec(
        select(ChallengeParticipant).where(ChallengeParticipant.challenge_id == ch.id)
    ).all()
    assert sorted(r.user_id for r in rows) == sorted([a.id, b.id])
```

- [ ] **Step 2: Run, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q -k save_groups`
Expected: FAIL with `AttributeError: ... has no attribute 'save_groups'`.

- [ ] **Step 3: Implement**

Append to `backend/app/services/challenge_groups.py`:

```python
def validate_groups(session: Session, ch: Challenge, roh: list[dict]) -> list[dict]:
    """Normalise and check an edited group list. Returns the clean list or
    raises InvalidGroups with a German message for the admin."""
    if len(roh) != ch.group_count:
        raise InvalidGroups(f"Es müssen genau {ch.group_count} Gruppen sein")
    aktive = _active_ids(session)
    gesehen_ids: set[int] = set()
    gesehen_user: set[int] = set()
    sauber = []
    for g in roh:
        gid = int(g["id"])
        name = str(g.get("name", "")).strip()
        if gid in gesehen_ids:
            raise InvalidGroups("Doppelte Gruppen-ID")
        gesehen_ids.add(gid)
        if not name:
            raise InvalidGroups("Jede Gruppe braucht einen Namen")
        members = [int(uid) for uid in g.get("member_ids", [])]
        if not members:
            raise InvalidGroups(f"{name} ist leer")
        for uid in members:
            if uid in gesehen_user:
                raise InvalidGroups("Eine Person steht in zwei Gruppen")
            if uid not in aktive:
                raise InvalidGroups("Unbekannte oder inaktive Person")
            gesehen_user.add(uid)
        sauber.append({"id": gid, "name": name, "member_ids": members})
    return sauber


def save_groups(session: Session, ch: Challenge, roh: list[dict]) -> list[dict]:
    """Validate, store, and in opt_in mode make every placed person a
    participant (placing someone counts as joining). Commits."""
    sauber = validate_groups(session, ch, roh)
    svc.set_groups(ch, sauber)
    if ch.join_mode == "opt_in":
        beigetreten = _joined_ids(session, ch)
        for g in sauber:
            for uid in g["member_ids"]:
                if uid not in beigetreten:
                    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=uid))
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return sauber
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/challenge_groups.py backend/tests/test_challenge_groups.py
git commit -m "feat(challenges): validate and save edited groups"
```

---

### Task 6: Lifecycle, freeze and winner in `services/challenges.py`

**Files:**
- Modify: `backend/app/services/challenges.py` (`teilnehmer_ids`, `_einfrieren`, `resolve_due`, `emit_qualified`, `sieger_id`, `setze_sieger`)
- Modify: `backend/app/services/feed.py` (signatures; full behaviour in Task 7)
- Test: `backend/tests/test_challenge_groups.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_challenge_groups.py`:

```python
# --- lifecycle, freeze, sieger ---------------------------------------------

from datetime import datetime, timezone  # noqa: E402

from app.models import Season  # noqa: E402


def _season(session):
    session.add(Season(year=2026, goal_km=1000.0, start_date=date(2026, 7, 20)))
    session.commit()


def test_teilnehmer_of_team_challenge_are_active_group_members(session):
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    make_user(session, username="dora")  # active but not in a group
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_team_challenge(session, groups_json=json.dumps(groups_of([a.id, c.id], [b.id])))
    assert svc.teilnehmer_ids(session, ch) == sorted([a.id, b.id])


def test_team_challenge_without_groups_does_not_start(session):
    _season(session)
    make_user(session, username="anna")
    ch = make_team_challenge(
        session, period_start=date(2026, 8, 1), period_end=date(2026, 8, 31), status="geplant",
    )
    svc.resolve_due(session, datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "geplant"
    svc.set_groups(ch, groups_of([1], [2]))
    session.add(ch)
    session.commit()
    svc.resolve_due(session, datetime(2026, 8, 2, 10, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "laufend"


def test_freeze_writes_groups_and_group_winners(session):
    _season(session)
    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_team_challenge(
        session, target=100.0, period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
        status="laufend", groups_json=json.dumps(groups_of([a.id, b.id], [c.id])),
    )
    add_activity(session, a.id, lauf.id, date(2026, 8, 5), 150.0)
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 70.0)   # A: 220/2 = 110 ✓
    add_activity(session, c.id, lauf.id, date(2026, 8, 5), 90.0)   # B: 90 ✗
    svc.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "beendet"
    ergebnis = json.loads(ch.result_json)
    assert ergebnis["gewinner_group_ids"] == [1]
    assert sorted(ergebnis["gewinner_ids"]) == sorted([a.id, b.id])
    g = ergebnis["groups"]
    assert [(x["id"], x["value"], x["rank"], x["geschafft"]) for x in g] == [(1, 110.0, 1, True), (2, 90.0, 2, False)]
    assert "members" not in g[0]  # only the compact record is frozen
    assert len(ergebnis["entries"]) == 3


def _finished_team(session):
    """Finished target group challenge: group 1 (anna, ben) qualified, group 2 (carla) not."""
    anna = make_user(session, username="anna", is_admin=True)
    ben = make_user(session, username="ben")
    carla = make_user(session, username="carla")
    ch = make_team_challenge(
        session, period_start=date(2026, 8, 1), period_end=date(2026, 8, 31), status="beendet",
        groups_json=json.dumps(groups_of([anna.id, ben.id], [carla.id])),
        result_json=json.dumps({
            "entries": [
                {"user_id": anna.id, "value": 150.0, "rank": 1, "geschafft": True},
                {"user_id": ben.id, "value": 70.0, "rank": 3, "geschafft": False},
                {"user_id": carla.id, "value": 90.0, "rank": 2, "geschafft": False},
            ],
            "groups": [
                {"id": 1, "name": "Gruppe A", "member_ids": [anna.id, ben.id], "sum": 220.0, "value": 110.0, "rank": 1, "geschafft": True},
                {"id": 2, "name": "Gruppe B", "member_ids": [carla.id], "sum": 90.0, "value": 90.0, "rank": 2, "geschafft": False},
            ],
            "gewinner_ids": [anna.id, ben.id],
            "gewinner_group_ids": [1],
        }),
    )
    return ch, anna, ben, carla


def test_sieger_can_be_a_group_or_a_member_of_a_winning_group(session):
    import pytest

    _season(session)
    ch, anna, ben, carla = _finished_team(session)
    jetzt = datetime(2026, 9, 2, tzinfo=timezone.utc)
    svc.setze_sieger(session, ch, jetzt, group_id=1)
    assert svc.sieger_group_id(ch) == 1 and svc.sieger_id(ch) is None
    svc.setze_sieger(session, ch, jetzt, user_id=ben.id)
    assert svc.sieger_id(ch) == ben.id and svc.sieger_group_id(ch) is None
    with pytest.raises(svc.NichtQualifiziert):
        svc.setze_sieger(session, ch, jetzt, user_id=carla.id)
    with pytest.raises(svc.NichtQualifiziert):
        svc.setze_sieger(session, ch, jetzt, group_id=2)


def test_sieger_group_id_rejected_on_non_team_challenge(session):
    import pytest

    _season(session)
    anna = make_user(session, username="anna")
    ch = make_team_challenge(
        session, team_mode=False, group_count=None, status="beendet",
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
        result_json=json.dumps({"entries": [], "gewinner_ids": [anna.id]}),
    )
    with pytest.raises(svc.NichtQualifiziert):
        svc.setze_sieger(session, ch, datetime(2026, 9, 2, tzinfo=timezone.utc), group_id=1)
```

- [ ] **Step 2: Run, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py -q -k "teilnehmer or start or freeze or sieger"`
Expected: FAIL (first: `teilnehmer_ids` returns all active users; `setze_sieger` has no `group_id`).

- [ ] **Step 3: Update `teilnehmer_ids`**

Replace the body of `teilnehmer_ids` in `services/challenges.py`:

```python
def teilnehmer_ids(session: Session, ch: Challenge) -> list[int]:
    """Who is scored. Group challenges: active members of any group. Otherwise
    'auto' = all active users, 'opt_in' = the joined ones. Inactive users drop
    out in every case."""
    aktive = {
        u.id for u in session.exec(select(User).where(User.is_active)).all()
    }
    if ch.team_mode:
        return sorted(uid for uid in group_member_ids(ch) if uid in aktive)
    if ch.join_mode == "auto":
        return sorted(aktive)
    rows = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id
        )
    ).all()
    return sorted(r.user_id for r in rows if r.user_id in aktive)
```

- [ ] **Step 4: Update `_einfrieren` and `resolve_due`**

Replace `_einfrieren`:

```python
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
```

In `resolve_due`, inside the first loop (`geplant` challenges), add the guard before the status change:

```python
        if ch.team_mode and not groups(ch):
            continue  # a group challenge only starts once the groups are drawn
        if heute >= ch.period_start:
```

- [ ] **Step 5: Update `emit_qualified`, `sieger_id`, `setze_sieger`**

Replace `emit_qualified`:

```python
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
```

Replace `sieger_id` and `setze_sieger`:

```python
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
```

- [ ] **Step 6: Extend the feed signatures (minimal, behaviour in Task 7)**

In `backend/app/services/feed.py`:

```python
def challenge_group_qualified_event(session: Session, ch: Challenge, gruppe: dict) -> None:
    """Group challenges: one event per (challenge, group). Idempotent, user_id None."""
    for ev in session.exec(
        select(FeedEvent).where(FeedEvent.type == "challenge_qualified")
    ).all():
        p = json.loads(ev.payload_json or "{}")
        if p.get("challenge_id") == ch.id and p.get("group_id") == gruppe["id"]:
            return
    _emit(
        session,
        type_="challenge_qualified",
        payload={
            "challenge_id": ch.id, "title": ch.title,
            "group_id": gruppe["id"], "group_name": gruppe["name"],
            "member_ids": gruppe["member_ids"],
        },
    )


def challenge_end_event(
    session: Session, ch: Challenge, gewinner_ids: list[int],
    gewinner_gruppen: list[str] | None = None,
) -> None:
    _emit(
        session,
        type_="challenge_end",
        payload={
            "challenge_id": ch.id,
            "title": ch.title,
            "prize": ch.prize,
            "gewinner_ids": gewinner_ids,
            "gewinner_namen": [
                u.display_name
                for u in session.exec(select(User)).all()
                if u.id in gewinner_ids
            ],
            "gewinner_gruppen": gewinner_gruppen or [],
        },
    )


def challenge_sieger_event(
    session: Session, ch: Challenge, user_id: int | None,
    group_id: int | None = None, gruppe: str | None = None,
) -> None:
    """Bei einer Korrektur wird das vorhandene Event umgeschrieben statt ein
    zweites anzulegen — sonst staenden zwei widersprechende Meldungen im Feed."""
    payload = {
        "challenge_id": ch.id,
        "title": ch.title,
        "prize": ch.prize,
        "user_id": user_id,
        "group_id": group_id,
        "gruppe": gruppe,
    }
    for ev in session.exec(
        select(FeedEvent).where(FeedEvent.type == "challenge_sieger")
    ).all():
        if json.loads(ev.payload_json or "{}").get("challenge_id") == ch.id:
            ev.user_id = user_id
            ev.payload_json = json.dumps(payload)
            session.add(ev)
            session.commit()
            return
    _emit(session, type_="challenge_sieger", user_id=user_id, payload=payload)
```

(`challenge_end_event` and `challenge_sieger_event` replace the existing functions; `challenge_group_qualified_event` is new. Also extend `challenge_start_event`'s payload with `"team_mode": ch.team_mode, "group_count": ch.group_count`.)

- [ ] **Step 7: Run all challenge and feed tests**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups.py tests/test_challenges_api.py tests/test_challenges_lifecycle.py tests/test_challenges_metrics.py tests/test_feed.py -q`
Expected: all PASS. The existing router still calls `svc.setze_sieger(session, ch, data.user_id, jetzt)` positionally — that breaks now. Fix the call in `backend/app/routers/challenges.py` to `svc.setze_sieger(session, ch, datetime.now(timezone.utc), user_id=data.user_id)` (the full endpoint rewrite follows in Task 8).

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/challenges.py backend/app/services/feed.py backend/app/routers/challenges.py backend/tests/test_challenge_groups.py
git commit -m "feat(challenges): group-aware participants, freeze, lifecycle and winner"
```

---

### Task 7: Feed tests for group payloads

**Files:**
- Test: `backend/tests/test_feed.py`

- [ ] **Step 1: Write the tests**

Append to `backend/tests/test_feed.py`:

```python
def test_group_challenge_feed_payloads(session):
    import json
    from datetime import date, datetime, timezone

    from sqlmodel import select

    from app.models import Activity, Challenge, FeedEvent, Season
    from app.services import challenges as svc
    from tests.conftest import make_category, make_user

    anna = make_user(session, username="anna")
    ben = make_user(session, username="ben")
    lauf = make_category(session, name="Joggen", factor=1.0)
    session.add(Season(year=2026, goal_km=1000.0, start_date=date(2026, 7, 20)))
    session.commit()
    ch = Challenge(
        title="Teams", creator_id=anna.id, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
        status="geplant", team_mode=True, group_count=2,
        groups_json=json.dumps([
            {"id": 1, "name": "Gruppe A", "member_ids": [anna.id]},
            {"id": 2, "name": "Gruppe B", "member_ids": [ben.id]},
        ]),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)

    svc.resolve_due(session, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))
    start = next(e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_start")
    assert json.loads(start.payload_json)["group_count"] == 2

    session.add(Activity(user_id=anna.id, category_id=lauf.id, date=date(2026, 8, 5), distance_km=120.0))
    session.commit()
    session.refresh(ch)
    eintraege = svc.standings(session, ch, date(2026, 8, 6))
    svc.emit_qualified(session, ch, eintraege)
    svc.emit_qualified(session, ch, eintraege)
    qualifiziert = [e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_qualified"]
    assert len(qualifiziert) == 1
    assert qualifiziert[0].user_id is None
    assert json.loads(qualifiziert[0].payload_json)["group_name"] == "Gruppe A"

    svc.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    ende = next(e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_end")
    assert json.loads(ende.payload_json)["gewinner_gruppen"] == ["Gruppe A"]
    assert json.loads(ende.payload_json)["gewinner_ids"] == [anna.id]

    session.refresh(ch)
    svc.setze_sieger(session, ch, datetime(2026, 9, 2, tzinfo=timezone.utc), group_id=1)
    svc.setze_sieger(session, ch, datetime(2026, 9, 2, tzinfo=timezone.utc), user_id=anna.id)
    sieger = [e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_sieger"]
    assert len(sieger) == 1
    p = json.loads(sieger[0].payload_json)
    assert (p["user_id"], p["group_id"], p["gruppe"]) == (anna.id, 1, "Gruppe A")
    assert sieger[0].user_id == anna.id
```

- [ ] **Step 2: Run**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_feed.py -q`
Expected: all PASS (Task 6 already implemented the behaviour; if anything fails, fix in `feed.py`).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_feed.py
git commit -m "test(feed): group challenge payloads"
```

---

### Task 8: Router — schemas, rules, endpoints, `ChallengeOut`

**Files:**
- Modify: `backend/app/routers/challenges.py`
- Test: `backend/tests/test_challenge_groups_api.py` (new)

- [ ] **Step 1: Write the failing API tests**

Create `backend/tests/test_challenge_groups_api.py`:

```python
"""Group challenge endpoints (spec 2026-09-12)."""

import json
from datetime import date, timedelta

from sqlmodel import select

from app.models import Activity, Challenge
from tests.conftest import login, make_addon, make_category, make_user


def setup(session, n_users=4):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    admin = make_user(session, username="admin", is_admin=True)
    users = [make_user(session, username=f"u{k}") for k in range(n_users)]
    return admin, users


def team_body(**kw):
    heute = date.today()
    body = {
        "title": "Teams", "mode": "ziel", "target": 100, "metric": "mm",
        "join_mode": "auto", "period_start": str(heute + timedelta(days=1)),
        "period_end": str(heute + timedelta(days=30)),
        "team_mode": True, "group_count": 2, "seeding_days": 30,
    }
    body.update(kw)
    return body


def test_create_auto_team_challenge_draws_immediately(session, client):
    setup(session)
    login(client, username="admin")
    r = client.post("/api/challenges", json=team_body())
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["team_mode"] is True and out["group_count"] == 2
    assert out["groups_drawn"] is True
    assert len(out["groups"]) == 2
    assert sorted(len(g["members"]) for g in out["groups"]) == [2, 3]  # admin + 4 users
    assert out["kann_gruppen_bearbeiten"] is True
    assert out["status"] == "geplant"


def test_create_opt_in_team_challenge_waits_for_draw(session, client):
    setup(session)
    login(client, username="admin")
    r = client.post("/api/challenges", json=team_body(join_mode="opt_in"))
    assert r.status_code == 201, r.text
    assert r.json()["groups_drawn"] is False and r.json()["groups"] == []


def test_create_validates_team_rules(session, client):
    setup(session)
    login(client, username="admin")
    assert client.post("/api/challenges", json=team_body(metric="streak")).status_code == 422
    assert client.post("/api/challenges", json=team_body(group_count=1)).status_code == 422
    assert client.post("/api/challenges", json=team_body(group_count=None)).status_code == 422
    assert client.post("/api/challenges", json=team_body(seeding_days=0)).status_code == 422


def test_create_with_too_few_people_is_422(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    make_user(session, username="admin", is_admin=True)
    login(client, username="admin")
    r = client.post("/api/challenges", json=team_body(group_count=3))
    assert r.status_code == 422
    assert session.exec(select(Challenge)).first() is None


def test_draw_and_save_groups_only_while_planned(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 422  # nobody joined
    for u in users:
        login(client, username=u.username)
        client.post(f"/api/challenges/{ch_id}/join")
    login(client, username="admin")
    r = client.post(f"/api/challenges/{ch_id}/draw")
    assert r.status_code == 200, r.text
    gruppen = r.json()["groups"]
    assert sorted(len(g["members"]) for g in gruppen) == [2, 2]

    body = {"groups": [
        {"id": 1, "name": "Flitzer", "member_ids": [users[0].id, users[1].id, users[2].id]},
        {"id": 2, "name": "Gruppe B", "member_ids": [users[3].id]},
    ]}
    r = client.put(f"/api/challenges/{ch_id}/groups", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["groups"][0]["name"] in ("Flitzer", "Gruppe B")
    assert r.json()["unassigned"] == []

    bad = {"groups": [{"id": 1, "name": "A", "member_ids": [users[0].id, users[0].id]}, body["groups"][1]]}
    assert client.put(f"/api/challenges/{ch_id}/groups", json=bad).status_code == 422

    ch = session.get(Challenge, ch_id)
    ch.status = "laufend"
    session.add(ch)
    session.commit()
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 409
    assert client.put(f"/api/challenges/{ch_id}/groups", json=body).status_code == 409


def test_draw_on_non_team_challenge_is_409(session, client):
    setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(team_mode=False, group_count=None)).json()["id"]
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 409
    assert client.get(f"/api/challenges/{ch_id}/seeding").status_code == 409


def test_seeding_lists_every_active_user_with_value(session, client):
    admin, users = setup(session, n_users=2)
    lauf = make_category(session, name="Joggen", factor=1.0)
    session.add(Activity(user_id=users[0].id, category_id=lauf.id, date=date.today() - timedelta(days=1), distance_km=12.0))
    session.commit()
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    r = client.get(f"/api/challenges/{ch_id}/seeding")
    assert r.status_code == 200, r.text
    rows = {e["user_id"]: e for e in r.json()}
    assert set(rows) == {admin.id, users[0].id, users[1].id}
    assert rows[users[0].id]["value"] == 12.0 and rows[users[0].id]["display_name"] == "U0"


def test_seeding_and_draw_need_admin(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body()).json()["id"]
    login(client, username=users[0].username)
    assert client.get(f"/api/challenges/{ch_id}/seeding").status_code == 403
    assert client.post(f"/api/challenges/{ch_id}/draw").status_code == 403
    assert client.put(f"/api/challenges/{ch_id}/groups", json={"groups": []}).status_code == 403


def test_patch_group_count_clears_groups(session, client):
    setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body()).json()["id"]
    r = client.patch(f"/api/challenges/{ch_id}", json={"group_count": 3})
    assert r.status_code == 200, r.text
    assert r.json()["groups_drawn"] is False and r.json()["group_count"] == 3
    r = client.patch(f"/api/challenges/{ch_id}", json={"title": "Neu"})
    assert r.json()["groups_drawn"] is False  # still cleared, no auto redraw


def test_late_joiner_is_unassigned_and_join_blocked_once_running(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    for u in users[:2]:
        login(client, username=u.username)
        client.post(f"/api/challenges/{ch_id}/join")
    login(client, username="admin")
    client.post(f"/api/challenges/{ch_id}/draw")
    login(client, username=users[2].username)
    r = client.post(f"/api/challenges/{ch_id}/join")
    assert r.status_code == 200
    assert r.json()["bin_dabei"] is True
    assert [e["user_id"] for e in r.json()["unassigned"]] == [users[2].id]
    assert r.json()["meine_gruppe_id"] is None

    ch = session.get(Challenge, ch_id)
    ch.status = "laufend"
    session.add(ch)
    session.commit()
    login(client, username=users[3].username)
    assert client.post(f"/api/challenges/{ch_id}/join").status_code == 409
    login(client, username=users[0].username)
    assert client.delete(f"/api/challenges/{ch_id}/join").status_code == 409


def test_leaving_planned_team_challenge_removes_from_group(session, client):
    admin, users = setup(session)
    login(client, username="admin")
    ch_id = client.post("/api/challenges", json=team_body(join_mode="opt_in")).json()["id"]
    for u in users[:2]:
        login(client, username=u.username)
        client.post(f"/api/challenges/{ch_id}/join")
    login(client, username="admin")
    client.post(f"/api/challenges/{ch_id}/draw")
    login(client, username=users[0].username)
    r = client.delete(f"/api/challenges/{ch_id}/join")
    assert r.status_code == 200
    assert users[0].id not in [m["user_id"] for g in r.json()["groups"] for m in g["members"]]
    assert r.json()["bin_dabei"] is False


def test_detail_shows_group_standings_and_my_group(session, client):
    admin, users = setup(session, n_users=2)
    lauf = make_category(session, name="Joggen", factor=1.0)
    heute = date.today()
    ch = Challenge(
        title="Teams", creator_id=admin.id, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute - timedelta(days=5), period_end=heute + timedelta(days=5),
        status="laufend", team_mode=True, group_count=2,
        groups_json=json.dumps([
            {"id": 1, "name": "Gruppe A", "member_ids": [admin.id, users[0].id]},
            {"id": 2, "name": "Gruppe B", "member_ids": [users[1].id]},
        ]),
    )
    session.add(ch)
    session.commit()
    session.add(Activity(user_id=users[0].id, category_id=lauf.id, date=heute, distance_km=240.0))
    session.commit()
    login(client, username="u0")
    out = client.get(f"/api/challenges/{ch.id}").json()
    assert out["meine_gruppe_id"] == 1
    a = next(g for g in out["groups"] if g["id"] == 1)
    assert (a["sum"], a["value"], a["size"], a["rank"], a["geschafft"]) == (240.0, 120.0, 2, 1, True)
    assert a["members"][0]["display_name"] == "U0"
    assert out["mein_stand"]["value"] == 240.0
    assert out["kann_gruppen_bearbeiten"] is False


def test_sieger_endpoint_accepts_group_or_person(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    anna = make_user(session, username="anna", is_admin=True)
    ben = make_user(session, username="ben")
    carla = make_user(session, username="carla")
    heute = date.today()
    ch = Challenge(
        title="Teams", creator_id=anna.id, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
        status="beendet", team_mode=True, group_count=2,
        groups_json=json.dumps([
            {"id": 1, "name": "Gruppe A", "member_ids": [anna.id, ben.id]},
            {"id": 2, "name": "Gruppe B", "member_ids": [carla.id]},
        ]),
        result_json=json.dumps({
            "entries": [
                {"user_id": anna.id, "value": 150.0, "rank": 1, "geschafft": True},
                {"user_id": ben.id, "value": 70.0, "rank": 3, "geschafft": False},
                {"user_id": carla.id, "value": 90.0, "rank": 2, "geschafft": False},
            ],
            "groups": [
                {"id": 1, "name": "Gruppe A", "member_ids": [anna.id, ben.id], "sum": 220.0, "value": 110.0, "rank": 1, "geschafft": True},
                {"id": 2, "name": "Gruppe B", "member_ids": [carla.id], "sum": 90.0, "value": 90.0, "rank": 2, "geschafft": False},
            ],
            "gewinner_ids": [anna.id, ben.id],
            "gewinner_group_ids": [1],
        }),
    )
    session.add(ch)
    session.commit()
    login(client, username="anna")
    assert client.get(f"/api/challenges/{ch.id}").json()["kann_sieger_setzen"] is True
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"group_id": 1})
    assert r.status_code == 200, r.text
    assert r.json()["sieger_group_id"] == 1 and r.json()["sieger_id"] is None
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    assert r.status_code == 200
    assert r.json()["sieger_id"] == ben.id and r.json()["sieger_group_id"] is None
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": carla.id}).status_code == 422
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={"group_id": 2}).status_code == 422
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={}).status_code == 422
    assert client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id, "group_id": 1}).status_code == 422
```

- [ ] **Step 2: Run, expect failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_challenge_groups_api.py -q`
Expected: FAIL (422 on unknown fields is not raised by pydantic by default, so most fail on missing `team_mode` in the response / 404 on `/draw`).

- [ ] **Step 3: Schemas**

In `backend/app/routers/challenges.py`:

Add after `StandingEntryOut`:

```python
class GroupOut(BaseModel):
    id: int
    name: str
    size: int
    sum: float
    value: float  # per head
    rank: int
    geschafft: bool
    members: list[StandingEntryOut]


class GroupIn(BaseModel):
    id: int
    name: str
    member_ids: list[int]


class GroupsIn(BaseModel):
    groups: list[GroupIn]


class SeedingEntryOut(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    value: float
```

Extend `ChallengeOut` (after `kann_sieger_setzen`):

```python
    team_mode: bool
    group_count: int | None
    seeding_days: int
    groups_drawn: bool
    groups: list[GroupOut]
    unassigned: list[StandingEntryOut]  # planned group challenges: pool members without a group
    meine_gruppe_id: int | None
    sieger_group_id: int | None
    kann_gruppen_bearbeiten: bool
```

Extend `ChallengeCreateIn` (after `period_end`):

```python
    team_mode: bool = False
    group_count: int | None = None
    seeding_days: int = 30
```

Extend `ChallengePatchIn`:

```python
    team_mode: bool | None = None
    group_count: int | None = None
    seeding_days: int | None = None
```

Replace `SiegerIn`:

```python
class SiegerIn(BaseModel):
    user_id: int | None = None
    group_id: int | None = None
```

Extend `REGEL_FELDER` with `"team_mode", "group_count", "seeding_days"`.

Add the import `from ..services import challenge_groups as groups_svc` next to the `svc` import, and `from ..models import Category, Challenge, ChallengeParticipant, User` stays.

- [ ] **Step 4: `_challenge_out`**

Replace `_challenge_out` with:

```python
def _challenge_out(
    session: Session, ch: Challenge, me: User, heute: date_type
) -> ChallengeOut:
    users = _users(session)
    teilnehmer = svc.teilnehmer_ids(session, ch)
    if ch.status == "beendet":
        ergebnis = json.loads(ch.result_json or "{}")
        roh = [
            {**e, "nicht_mehr_schaffbar": False} for e in ergebnis.get("entries", [])
        ]
        gewinner = ergebnis.get("gewinner_ids", [])
        gewinner_gruppen = ergebnis.get("gewinner_group_ids", [])
    else:
        roh = svc.standings(session, ch, heute)
        svc.emit_qualified(session, ch, roh)
        gewinner = [e["user_id"] for e in roh if e["geschafft"]]
        gewinner_gruppen = []

    def eintrag(e: dict) -> StandingEntryOut:
        u = users.get(e["user_id"])
        return StandingEntryOut(
            user_id=e["user_id"],
            display_name=u.display_name if u else "?",
            avatar=u.avatar if u else "icon:laufen",
            value=e["value"],
            rank=e.get("rank", 0),
            geschafft=e.get("geschafft", False),
            nicht_mehr_schaffbar=e.get("nicht_mehr_schaffbar", False),
        )

    liste = [eintrag(e) for e in roh]
    gruppen: list[GroupOut] = []
    unassigned: list[StandingEntryOut] = []
    pool: list[int] = []
    if ch.team_mode:
        if ch.status != "beendet":
            gewinner = [uid for g in svc.group_standings(ch, roh) if g["geschafft"] for uid in g["member_ids"]]
            gewinner_gruppen = [g["id"] for g in svc.group_standings(ch, roh) if g["geschafft"]]
        gruppen = [
            GroupOut(
                id=g["id"], name=g["name"], size=g["size"], sum=g["sum"],
                value=g["value"], rank=g["rank"], geschafft=g["geschafft"],
                members=[eintrag(m) for m in g["members"]],
            )
            for g in svc.group_standings(ch, roh)
        ]
        if ch.status == "geplant":
            pool = groups_svc.pool(session, ch)
            zugeordnet = set(svc.group_member_ids(ch))
            unassigned = [
                eintrag({"user_id": uid, "value": 0.0}) for uid in pool if uid not in zugeordnet
            ]
    meine_gruppe = svc.group_of(ch, me.id) if ch.team_mode else None
    bin_dabei = me.id in teilnehmer or (ch.team_mode and ch.status == "geplant" and me.id in pool)
    return ChallengeOut(
        id=ch.id,
        title=ch.title,
        description=ch.description,
        prize=ch.prize,
        creator_id=ch.creator_id,
        mode=ch.mode,
        target=ch.target,
        top_n=ch.top_n,
        metric=ch.metric,
        category_ids=svc.category_ids(ch),
        streak_min_mm=ch.streak_min_mm,
        join_mode=ch.join_mode,
        period_start=ch.period_start,
        period_end=ch.period_end,
        status=ch.status,
        vorlaeufig=svc.ist_vorlaeufig(ch, heute),
        bin_dabei=bin_dabei,
        kann_beitreten=(
            ch.join_mode == "opt_in"
            and not bin_dabei
            and ch.status in ("geplant", "laufend")
            and heute <= ch.period_end
            and (not ch.team_mode or ch.status == "geplant")
        ),
        standings=liste,
        mein_stand=next((e for e in liste if e.user_id == me.id), None),
        gewinner_ids=gewinner,
        sieger_id=svc.sieger_id(ch),
        kann_sieger_setzen=(
            me.is_admin
            and ch.mode == "ziel"
            and ch.status == "beendet"
            and len(gewinner) > 0
        ),
        created_at=ch.created_at,
        resolved_at=ch.resolved_at,
        team_mode=ch.team_mode,
        group_count=ch.group_count,
        seeding_days=ch.seeding_days,
        groups_drawn=len(svc.groups(ch)) > 0,
        groups=gruppen,
        unassigned=unassigned,
        meine_gruppe_id=meine_gruppe["id"] if meine_gruppe else None,
        sieger_group_id=svc.sieger_group_id(ch),
        kann_gruppen_bearbeiten=me.is_admin and ch.team_mode and ch.status == "geplant",
    )
```

Note: `svc.group_standings(ch, roh)` is called up to three times above; compute it once into a local `gruppen_roh = svc.group_standings(ch, roh) if ch.team_mode else []` at the top of the `if ch.team_mode:` block and use that variable in all three places.

- [ ] **Step 5: Join / leave rules**

In `join_challenge`, after the `join_mode` check:

```python
    if ch.team_mode and ch.status != "geplant":
        raise HTTPException(status_code=409, detail="Die Gruppen stehen bereits fest")
```

In `leave_challenge`, replace the status check and add group removal:

```python
    if ch.status not in ("geplant", "laufend") or (ch.team_mode and ch.status != "geplant"):
        raise HTTPException(status_code=409, detail="Die Gruppen stehen bereits fest" if ch.team_mode else "Die Challenge ist vorbei")
    zeile = ...  # unchanged
    if zeile is not None:
        session.delete(zeile)
        if ch.team_mode:
            svc.remove_group_member(ch, me.id)
            session.add(ch)
        session.commit()
```

- [ ] **Step 6: Rules, create, patch**

Extend `_pruefe_regeln` signature with `team_mode: bool, group_count: int | None, seeding_days: int` and add at the end:

```python
    if team_mode:
        if metric not in ("mm", "anzahl"):
            raise HTTPException(status_code=422, detail="Gruppen-Challenges werten nur MM oder Anzahl")
        if group_count is None or group_count < 2:
            raise HTTPException(status_code=422, detail="Mindestens 2 Gruppen")
        if seeding_days < 1:
            raise HTTPException(status_code=422, detail="Setzliste braucht mindestens 1 Tag")
```

In `create_challenge`: pass `team_mode=data.team_mode, group_count=data.group_count, seeding_days=data.seeding_days` to `_pruefe_regeln`; set the three fields on the `Challenge(...)` constructor; and replace the `session.add(ch)` block with:

```python
    if data.team_mode and data.join_mode == "auto":
        try:
            groups_svc.draw(session, ch, date_type.today(), datetime.now(timezone.utc))
        except groups_svc.TooFewPeople as e:
            raise HTTPException(status_code=422, detail=str(e))
    session.add(ch)
    session.commit()
    session.refresh(ch)
    svc.resolve_due(session)
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())
```

In `patch_challenge`: add to `werte`:

```python
        "team_mode": data.team_mode if data.team_mode is not None else ch.team_mode,
        "group_count": data.group_count if "group_count" in gesetzt else ch.group_count,
        "seeding_days": data.seeding_days if data.seeding_days is not None else ch.seeding_days,
```

and after the assignments, before `session.add(ch)`:

```python
    gruppen_neu = werte["group_count"] != ch.group_count or werte["team_mode"] != ch.team_mode
    ch.team_mode = werte["team_mode"]
    ch.group_count = werte["group_count"]
    ch.seeding_days = werte["seeding_days"]
    if gruppen_neu:
        svc.set_groups(ch, [])  # the admin draws again
        ch.groups_drawn_at = None
```

(`gruppen_neu` must be computed before `ch.group_count` is overwritten — place the comparison first, as shown.)

- [ ] **Step 7: New endpoints and the winner endpoint**

Add before `set_sieger`:

```python
def _nur_team_geplant(ch: Challenge) -> None:
    if not ch.team_mode:
        raise HTTPException(status_code=409, detail="Keine Gruppen-Challenge")
    if ch.status != "geplant":
        raise HTTPException(status_code=409, detail="Die Gruppen stehen bereits fest")


@router.post(
    "/{challenge_id}/draw", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def draw_groups(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    _nur_team_geplant(ch)
    try:
        groups_svc.draw(session, ch, date_type.today(), datetime.now(timezone.utc))
    except groups_svc.TooFewPeople as e:
        raise HTTPException(status_code=422, detail=str(e))
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())


@router.put(
    "/{challenge_id}/groups", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def save_groups(
    challenge_id: int,
    data: GroupsIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    _nur_team_geplant(ch)
    try:
        groups_svc.save_groups(session, ch, [g.model_dump() for g in data.groups])
    except groups_svc.InvalidGroups as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _challenge_out(session, ch, me, date_type.today())


@router.get(
    "/{challenge_id}/seeding", response_model=list[SeedingEntryOut],
    dependencies=[Depends(require_admin)],
)
def seeding_list(challenge_id: int, session: Session = Depends(get_session)):
    """Every active user with their seeding value, for the group editor."""
    ch = _geladene_challenge(session, challenge_id)
    if not ch.team_mode:
        raise HTTPException(status_code=409, detail="Keine Gruppen-Challenge")
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    return [
        SeedingEntryOut(
            user_id=uid, display_name=users[uid].display_name,
            avatar=users[uid].avatar, value=wert,
        )
        for uid, wert in groups_svc.seeding(session, ch, date_type.today(), sorted(users))
    ]
```

Replace `set_sieger`:

```python
@router.put(
    "/{challenge_id}/sieger", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def set_sieger(
    challenge_id: int,
    data: SiegerIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if (data.user_id is None) == (data.group_id is None):
        raise HTTPException(status_code=422, detail="Entweder user_id oder group_id")
    ch = _geladene_challenge(session, challenge_id)
    try:
        svc.setze_sieger(
            session, ch, datetime.now(timezone.utc),
            user_id=data.user_id, group_id=data.group_id,
        )
    except svc.NichtQualifiziert as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())
```

- [ ] **Step 8: Run the whole backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: all PASS. Watch `test_challenges_api.py::test_beitreten_und_austreten` and the sieger tests: they must still pass unchanged.

- [ ] **Step 9: Commit**

```bash
git add backend/app/routers/challenges.py backend/tests/test_challenge_groups_api.py
git commit -m "feat(challenges): group endpoints (draw, groups, seeding) and group-aware ChallengeOut"
```

---

### Task 9: Frontend API client types and functions

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/challenges/ChallengeDetail.tsx` (sieger call signature only)
- Modify: `frontend/src/components/challenges/ChallengeDetail.test.tsx` (sieger assertion)

- [ ] **Step 1: Types**

In `frontend/src/api/client.ts`, after `ChallengeStanding`:

```ts
export type ChallengeGroup = {
  id: number
  name: string
  size: number
  sum: number
  value: number // per head
  rank: number
  geschafft: boolean
  members: ChallengeStanding[]
}
export type ChallengeGroupInput = { id: number; name: string; member_ids: number[] }
export type SeedingEntry = { user_id: number; display_name: string; avatar: string; value: number }
export type SiegerWahl = { user_id: number } | { group_id: number }
```

Extend `Challenge` (after `kann_sieger_setzen: boolean`):

```ts
  team_mode: boolean
  group_count: number | null
  seeding_days: number
  groups_drawn: boolean
  groups: ChallengeGroup[]
  unassigned: ChallengeStanding[]
  meine_gruppe_id: number | null
  sieger_group_id: number | null
  kann_gruppen_bearbeiten: boolean
```

Extend `ChallengeInput` (after `period_end: string`):

```ts
  team_mode?: boolean
  group_count?: number | null
  seeding_days?: number
```

Extend the `FeedEvent.payload` type (after `gewinner_namen?: string[]`):

```ts
    gewinner_gruppen?: string[]
    group_id?: number | null
    group_name?: string
    gruppe?: string | null
    group_count?: number | null
```

- [ ] **Step 2: Functions**

Replace `setChallengeSieger` and add the three new calls:

```ts
  setChallengeSieger: (id: number, wahl: SiegerWahl) =>
    request<Challenge>(`/api/challenges/${id}/sieger`, {
      method: 'PUT',
      body: JSON.stringify(wahl),
    }),
  drawChallengeGroups: (id: number) =>
    request<Challenge>(`/api/challenges/${id}/draw`, { method: 'POST' }),
  saveChallengeGroups: (id: number, groups: ChallengeGroupInput[]) =>
    request<Challenge>(`/api/challenges/${id}/groups`, {
      method: 'PUT',
      body: JSON.stringify({ groups }),
    }),
  challengeSeeding: (id: number) =>
    request<SeedingEntry[]>(`/api/challenges/${id}/seeding`),
```

- [ ] **Step 3: Adapt the one caller**

In `ChallengeDetail.tsx`, change the mutation:

```ts
  const siegerSetzen = useMutation({
    mutationFn: (wahl: SiegerWahl) => api.setChallengeSieger(challengeId, wahl),
```

and the button: `onClick={() => wahl !== null && siegerSetzen.mutate({ user_id: wahl })}`. Add `SiegerWahl` to the type import from `../../api/client`.

In `ChallengeDetail.test.tsx` the admin test currently ends with `expect(api.setChallengeSieger).toHaveBeenCalledWith(1, 2)` (line 85). Change it to `toHaveBeenCalledWith(1, { user_id: 2 })`. The `fireEvent.change(..., { target: { value: '2' } })` two lines above stays for now (Task 13 changes it to `'u:2'`).

Test files are excluded from `tsc -b` (`tsconfig.app.json` excludes `*.test.ts(x)`), so the typed fixtures in `wertung.test.ts` (`basis: Challenge`) and `ChallengeRow.test.tsx` (`challenge()`) do not need the new fields to compile. Leave them.

- [ ] **Step 4: Verify**

Run: `cd frontend && npx tsc -b && npx vitest run src/components/challenges`
Expected: tsc clean, tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/challenges/ChallengeDetail.tsx frontend/src/components/challenges/ChallengeDetail.test.tsx
git commit -m "feat(api): group challenge types and endpoints in the client"
```

---

### Task 10: `wertung.ts` group texts

**Files:**
- Modify: `frontend/src/components/challenges/wertung.ts`
- Test: `frontend/src/components/challenges/wertung.test.ts`

- [ ] **Step 1: Write the failing tests**

Append to `wertung.test.ts`. The file already defines `const basis: Challenge = {...}`; reuse it. Change the import line to `import { einheit, fortschritt, meineGruppe, wertungText } from './wertung'`.

```ts
const teamBase = {
  ...basis,
  team_mode: true,
  group_count: 3,
  seeding_days: 30,
  groups_drawn: true,
  groups: [
    { id: 1, name: 'Gruppe A', size: 2, sum: 400, value: 200, rank: 2, geschafft: false, members: [] },
    { id: 2, name: 'Gruppe B', size: 2, sum: 620, value: 310, rank: 1, geschafft: true, members: [] },
  ],
  unassigned: [],
  meine_gruppe_id: 2,
  sieger_group_id: null,
  kann_gruppen_bearbeiten: false,
} as unknown as Challenge

describe('wertungText for group challenges', () => {
  it('names the per-head target and the group count', () => {
    expect(wertungText({ ...teamBase, mode: 'ziel', target: 300, metric: 'mm' }, [])).toBe(
      'Ziel: 300 MM pro Kopf aus allen Sportarten · 3 Gruppen',
    )
  })
  it('describes the ranking per head', () => {
    expect(wertungText({ ...teamBase, mode: 'rangliste', top_n: 1, metric: 'anzahl' }, [])).toBe(
      'Rangliste: meiste Aktivitäten pro Kopf aus allen Sportarten, Top 1 · 3 Gruppen',
    )
  })
})

describe('meineGruppe', () => {
  it('returns the own group or null', () => {
    expect(meineGruppe(teamBase)?.name).toBe('Gruppe B')
    expect(meineGruppe({ ...teamBase, meine_gruppe_id: null })).toBeNull()
  })
})
```

Import `meineGruppe` alongside `wertungText`.

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/components/challenges/wertung.test.ts`
Expected: FAIL (`meineGruppe` not exported; text mismatch).

- [ ] **Step 3: Implement**

In `wertung.ts` replace `wertungText` and add `meineGruppe`:

```ts
/** Menschenlesbare Beschreibung der Wertung, z.B. "Ziel: 300 MM aus allen Sportarten". */
export function wertungText(ch: Challenge, kategorien: KategorieName[]): string {
  const aus = `aus ${kategorienText(ch, kategorien)}`
  const proKopf = ch.team_mode ? ' pro Kopf' : ''
  const gruppen = ch.team_mode ? ` · ${ch.group_count} Gruppen` : ''
  if (ch.mode === 'rangliste') {
    const was =
      ch.metric === 'streak'
        ? 'längste Serie'
        : ch.metric === 'anzahl'
          ? 'meiste Aktivitäten'
          : 'meiste MM'
    return `Rangliste: ${was}${proKopf} ${aus}, Top ${ch.top_n}${gruppen}`
  }
  if (ch.metric === 'streak') {
    return `Ziel: ${ch.target} Tage am Stück mit mindestens ${ch.streak_min_mm} MM ${aus}`
  }
  return `Ziel: ${ch.target} ${einheit(ch.metric)}${proKopf} ${aus}${gruppen}`
}

/** The group the current user is in, or null (not a group challenge, not drawn, not placed). */
export function meineGruppe(ch: Challenge): ChallengeGroup | null {
  if (!ch.team_mode || ch.meine_gruppe_id === null) return null
  return ch.groups.find((g) => g.id === ch.meine_gruppe_id) ?? null
}
```

Import `ChallengeGroup` from `../../api/client`.

- [ ] **Step 4: Run**

Run: `cd frontend && npx vitest run src/components/challenges/wertung.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/challenges/wertung.ts frontend/src/components/challenges/wertung.test.ts
git commit -m "feat(challenges): group-aware wertung text and meineGruppe helper"
```

---

### Task 11: Admin form — group checkbox, fields, editor link

**Files:**
- Modify: `frontend/src/components/admin/ChallengesAdmin.tsx`
- Test: `frontend/src/components/admin/ChallengesAdmin.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/admin/ChallengesAdmin.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ChallengesAdmin from './ChallengesAdmin'

vi.mock('../../api/client', () => ({
  api: {
    challenges: vi.fn().mockResolvedValue([
      { id: 5, title: 'Teams', status: 'geplant', team_mode: true },
      { id: 6, title: 'Solo', status: 'geplant', team_mode: false },
    ]),
    categories: vi.fn().mockResolvedValue([]),
    createChallenge: vi.fn().mockResolvedValue({}),
    cancelChallenge: vi.fn(),
  },
}))
vi.mock('../ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAdmin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ChallengesAdmin />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ChallengesAdmin group fields', () => {
  it('reveals group fields, hides streak and posts the group settings', async () => {
    const { api } = await import('../../api/client')
    renderAdmin()
    expect(screen.queryByLabelText('Anzahl Gruppen')).toBeNull()
    expect(screen.getByRole('option', { name: 'Streak (Tage am Stück)' })).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Gruppen-Challenge'))
    expect(screen.getByLabelText('Anzahl Gruppen')).toHaveValue(3)
    expect(screen.getByLabelText('Setzliste: letzte N Tage')).toHaveValue(30)
    expect(screen.queryByRole('option', { name: 'Streak (Tage am Stück)' })).toBeNull()
    expect(screen.getByLabelText('Ziel pro Kopf')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Anzahl Gruppen'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Titel'), { target: { value: 'Teams' } })
    fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2026-10-01' } })
    fireEvent.change(screen.getByLabelText('Ende'), { target: { value: '2026-10-31' } })
    fireEvent.click(screen.getByText('Challenge anlegen'))
    await waitFor(() => expect(api.createChallenge).toHaveBeenCalled())
    expect(vi.mocked(api.createChallenge).mock.calls[0][0]).toMatchObject({
      team_mode: true, group_count: 4, seeding_days: 30,
    })
  })

  it('links planned group challenges to the editor', async () => {
    renderAdmin()
    await waitFor(() => expect(screen.getByText('Teams')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: 'Gruppen' })
    expect(link).toHaveAttribute('href', '/arena/challenges/5/gruppen')
    expect(screen.getAllByRole('link', { name: 'Gruppen' })).toHaveLength(1)
  })
})
```

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/components/admin/ChallengesAdmin.test.tsx`
Expected: FAIL (no "Gruppen-Challenge" label).

- [ ] **Step 3: Implement**

In `ChallengesAdmin.tsx`:

- Add `import { Link } from 'react-router-dom'`.
- Extend `LEER`: `team_mode: false, group_count: 3, seeding_days: 30,`.
- Insert the checkbox block right after the "Teilnahme" `<Select>`:

```tsx
        <label className="flex items-center gap-2 text-xs font-semibold text-ink">
          <input
            type="checkbox"
            checked={form.team_mode ?? false}
            onChange={(e) => {
              const team = e.target.checked
              setForm((f) => ({
                ...f,
                team_mode: team,
                metric: team && f.metric === 'streak' ? 'mm' : f.metric,
              }))
            }}
          />
          Gruppen-Challenge
        </label>
        {form.team_mode && (
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Anzahl Gruppen"
              type="number"
              min={2}
              value={String(form.group_count ?? 3)}
              onChange={(e) => set('group_count', Number(e.target.value))}
            />
            <Input
              label="Setzliste: letzte N Tage"
              type="number"
              min={1}
              value={String(form.seeding_days ?? 30)}
              onChange={(e) => set('seeding_days', Number(e.target.value))}
            />
          </div>
        )}
```

- In the Wertung `<Select>`, render the streak option only when `!form.team_mode`:

```tsx
            {!form.team_mode && <option value="streak">Streak (Tage am Stück)</option>}
```

- Change the target label: `label={form.team_mode ? 'Ziel pro Kopf' : 'Ziel'}`.
- In the list `<li>`, before the status span:

```tsx
            {ch.team_mode && ch.status === 'geplant' && (
              <Link
                to={`/arena/challenges/${ch.id}/gruppen`}
                className="shrink-0 rounded-full border border-accent px-2 py-0.5 text-[11px] font-bold text-accent"
              >
                Gruppen
              </Link>
            )}
```

Note: `Input` with `type="number"` and a string `value` — `toHaveValue(3)` works because jsdom reports number inputs as numbers.

- [ ] **Step 4: Run**

Run: `cd frontend && npx vitest run src/components/admin/ChallengesAdmin.test.tsx`
Expected: PASS. Also run `npx vitest run src/pages/Admin.test.tsx`: it renders `<Admin />` without a router and does not mock `api.challenges`, so the challenge list stays empty and no `<Link>` is rendered. If it fails on the `Link` nevertheless, wrap that test's render in `<MemoryRouter>`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/ChallengesAdmin.tsx frontend/src/components/admin/ChallengesAdmin.test.tsx
git commit -m "feat(admin): group challenge settings in the challenge form"
```

---

### Task 12: `GroupCard` and the group view in `ChallengeDetail`

**Files:**
- Create: `frontend/src/components/challenges/GroupCard.tsx`
- Modify: `frontend/src/components/challenges/ChallengeDetail.tsx`
- Test: `frontend/src/components/challenges/ChallengeDetail.test.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `ChallengeDetail.test.tsx` inside the `describe`:

```tsx
  const teamDetail = {
    ...detail,
    title: 'Team-Oktober',
    target: 100,
    team_mode: true,
    group_count: 2,
    seeding_days: 30,
    groups_drawn: true,
    meine_gruppe_id: 2,
    sieger_group_id: null,
    kann_gruppen_bearbeiten: false,
    unassigned: [],
    standings: [
      { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 150, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
      { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 70, rank: 3, geschafft: false, nicht_mehr_schaffbar: false },
      { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 90, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
    ],
    mein_stand: { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 90, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
    groups: [
      { id: 1, name: 'Gruppe A', size: 2, sum: 220, value: 110, rank: 1, geschafft: true,
        members: [
          { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 150, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
          { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 70, rank: 3, geschafft: false, nicht_mehr_schaffbar: false },
        ] },
      { id: 2, name: 'Gruppe B', size: 1, sum: 90, value: 90, rank: 2, geschafft: false,
        members: [
          { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 90, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
        ] },
    ],
    gewinner_ids: [1, 2],
  }

  it('shows group cards with the own group first', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue(teamDetail as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Team-Oktober')).toBeInTheDocument())
    const karten = screen.getAllByTestId('group-card')
    expect(karten[0]).toHaveTextContent('Gruppe B')
    expect(karten[0]).toHaveTextContent('noch 10 pro Kopf')
    expect(karten[1]).toHaveTextContent('Gruppe A')
    expect(karten[1]).toHaveTextContent('geschafft')
    expect(karten[1]).toHaveTextContent('220 MM · 110 pro Kopf')
    expect(karten[1]).toHaveTextContent('Rick')
    expect(screen.queryByRole('link', { name: /Gruppen bearbeiten/ })).toBeNull()
  })

  it('tells that groups are not drawn yet and links the admin to the editor', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'geplant', groups_drawn: false, groups: [], meine_gruppe_id: null,
      kann_gruppen_bearbeiten: true,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Gruppen werden noch ausgelost')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /Gruppen bearbeiten/ })).toHaveAttribute(
      'href', '/arena/challenges/1/gruppen',
    )
  })
```

If the file has no `renderDetail()` helper yet, add one at the top of the `describe` that wraps the existing render call (QueryClientProvider + MemoryRouter at `/challenges/1` + Route `/challenges/:id`), and use it in the new tests.

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx`
Expected: FAIL (no `group-card` test ids).

- [ ] **Step 3: Create `GroupCard.tsx`**

```tsx
import type { Challenge, ChallengeGroup } from '../../api/client'
import Avatar from '../ui/Avatar'
import { einheit, fortschritt } from './wertung'

function GroupChip({ ch, g }: { ch: Challenge; g: ChallengeGroup }) {
  if (ch.mode === 'rangliste')
    return (
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
          g.geschafft ? 'bg-accent text-accent-ink' : 'border border-line text-ink-mute'
        }`}
      >
        Platz {g.rank}
      </span>
    )
  if (g.geschafft)
    return (
      <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold text-accent-ink">
        geschafft
      </span>
    )
  const rest = Math.max((ch.target ?? 0) - g.value, 0)
  return (
    <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
      noch {Math.round(rest * 100) / 100} pro Kopf
    </span>
  )
}

// One group in the detail view: header with chip and progress, members below.
// `hoechster` is the leading group's per-head value (ranking mode bars).
export default function GroupCard({
  ch, g, mine, hoechster,
}: { ch: Challenge; g: ChallengeGroup; mine: boolean; hoechster: number }) {
  const pct = ch.mode === 'ziel' ? fortschritt(ch, g.value) * 100 : (g.value / hoechster) * 100
  return (
    <div
      data-testid="group-card"
      className={`rounded-2xl border bg-card p-3 ${mine ? 'border-accent' : 'border-line'}`}
    >
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-extrabold text-ink">
          {g.name}
          {g.id === ch.sieger_group_id && ' 🏆'}
          {mine && <span className="ml-1 text-[10px] font-bold text-accent">du</span>}
        </span>
        <GroupChip ch={ch} g={g} />
      </div>
      <p className="mt-1 text-xs text-ink-soft">
        {g.sum} {einheit(ch.metric)} · {g.value} pro Kopf
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
        <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <ul className="mt-2 space-y-1">
        {g.members.map((m) => (
          <li key={m.user_id} className="flex items-center gap-2 text-xs">
            <Avatar value={m.avatar} size="sm" />
            <span className="min-w-0 flex-1 truncate text-ink">
              {m.display_name}
              {m.user_id === ch.sieger_id && ' 🏆'}
            </span>
            <span className="shrink-0 font-bold text-ink">
              {m.value} {einheit(ch.metric)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: Group view in `ChallengeDetail.tsx`**

Import `GroupCard` and `meineGruppe`. Replace the final `<section className="space-y-1.5">…</section>` (the per-person list) with:

```tsx
      {ch.team_mode ? (
        <GroupSection ch={ch} />
      ) : (
        <section className="space-y-1.5">
          {/* existing per-person list, unchanged */}
        </section>
      )}
```

and add in the same file (above `export default function ChallengeDetail`):

```tsx
function GroupSection({ ch }: { ch: Challenge }) {
  const editorLink = ch.kann_gruppen_bearbeiten && (
    <Link
      to={`/arena/challenges/${ch.id}/gruppen`}
      className="inline-block rounded-full border border-accent px-3 py-1 text-[11px] font-bold text-accent"
    >
      Gruppen bearbeiten
    </Link>
  )
  if (!ch.groups_drawn)
    return (
      <section className="space-y-2 rounded-2xl border border-dashed border-line p-4 text-center">
        <p className="text-sm text-ink-mute">Gruppen werden noch ausgelost</p>
        {editorLink}
      </section>
    )
  const meine = ch.meine_gruppe_id
  const sortiert = [...ch.groups].sort((a, b) => {
    if (a.id === meine) return -1
    if (b.id === meine) return 1
    return a.rank - b.rank || a.id - b.id
  })
  const hoechster = Math.max(...ch.groups.map((g) => g.value), 1)
  return (
    <section className="space-y-2">
      {editorLink && <div className="text-right">{editorLink}</div>}
      {sortiert.map((g) => (
        <GroupCard key={g.id} ch={ch} g={g} mine={g.id === meine} hoechster={hoechster} />
      ))}
    </section>
  )
}
```

Also the "Austreten" button condition: add `&& (!ch.team_mode || ch.status === 'geplant')`.

- [ ] **Step 5: Run**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx && npx tsc -b`
Expected: PASS, tsc clean. (`meineGruppe` may end up unused here; if so, drop the import.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/challenges/GroupCard.tsx frontend/src/components/challenges/ChallengeDetail.tsx frontend/src/components/challenges/ChallengeDetail.test.tsx
git commit -m "feat(challenges): group cards in the challenge detail view"
```

---

### Task 13: Group winner select, row and hero texts

**Files:**
- Modify: `frontend/src/components/challenges/ChallengeDetail.tsx`
- Modify: `frontend/src/components/challenges/ChallengeRow.tsx`
- Modify: `frontend/src/components/challenges/ChallengeHeroCard.tsx`
- Test: `ChallengeDetail.test.tsx`, `ChallengeRow.test.tsx`

- [ ] **Step 1: Write the failing tests**

Append to `ChallengeDetail.test.tsx` inside the `describe`:

```tsx
  it('lets the admin pick a winning group or one of its members', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'beendet', vorlaeufig: false, sieger_id: null, kann_sieger_setzen: true,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByLabelText('Sieger')).toBeInTheDocument())
    const select = screen.getByLabelText('Sieger') as HTMLSelectElement
    const labels = Array.from(select.options).map((o) => o.textContent)
    expect(labels).toEqual(['– bitte wählen –', 'Gruppe A', 'Rick (Gruppe A)', 'Mia (Gruppe A)'])
    fireEvent.change(select, { target: { value: 'g:1' } })
    fireEvent.click(screen.getByText('Sieger eintragen'))
    await waitFor(() => expect(api.setChallengeSieger).toHaveBeenCalledWith(1, { group_id: 1 }))
    fireEvent.change(select, { target: { value: 'u:2' } })
    fireEvent.click(screen.getByText('Sieger eintragen'))
    await waitFor(() => expect(api.setChallengeSieger).toHaveBeenCalledWith(1, { user_id: 2 }))
  })

  it('shows the group winner band', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'beendet', vorlaeufig: false, sieger_group_id: 1, sieger_id: null,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText(/Sieger: Gruppe A/)).toBeInTheDocument())
  })

  it('shows a person winner with their group', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'beendet', vorlaeufig: false, sieger_group_id: null, sieger_id: 2,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText(/Sieger: Mia \(Gruppe A\)/)).toBeInTheDocument())
  })
```

Append to `ChallengeRow.test.tsx`. The file already has `standing(user_id, display_name, rank)`, `challenge(over)` and `renderRow(ch)` helpers; reuse them:

```tsx
describe('ChallengeRow for group challenges', () => {
  const team = challenge({
    status: 'beendet',
    team_mode: true,
    sieger_id: null,
    sieger_group_id: null,
    gewinner_ids: [1, 2],
    standings: [standing(1, 'Rick', 1), standing(2, 'Mia', 2), standing(3, 'Lea', 3)],
    groups: [
      { id: 1, name: 'Gruppe A', size: 2, sum: 220, value: 110, rank: 1, geschafft: true,
        members: [standing(1, 'Rick', 1), standing(2, 'Mia', 2)] },
      { id: 2, name: 'Gruppe B', size: 1, sum: 90, value: 90, rank: 2, geschafft: false,
        members: [standing(3, 'Lea', 3)] },
    ],
  } as Partial<Challenge>)

  it('shows the single winning group', () => {
    renderRow(team)
    expect(screen.getByText('🏆 Gruppe A')).toBeInTheDocument()
  })
  it('shows the entered group winner', () => {
    renderRow({ ...team, sieger_group_id: 1 })
    expect(screen.getByText('🏆 Gruppe A')).toBeInTheDocument()
  })
  it('shows the entered person winner with their group', () => {
    renderRow({ ...team, sieger_id: 2 })
    expect(screen.getByText('🏆 Mia (Gruppe A)')).toBeInTheDocument()
  })
  it('lists several winning groups', () => {
    renderRow({ ...team, groups: team.groups.map((g) => ({ ...g, geschafft: true })) })
    expect(screen.getByText('🏆 Gruppe A, Gruppe B')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx src/components/challenges/ChallengeRow.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Winner band and select in `ChallengeDetail.tsx`**

Change the `wahl` state to a string: `const [wahl, setWahl] = useState<string>('')`. Replace the winner `<section>` (the `ch.status === 'beendet' && ch.mode === 'ziel'` block) with:

```tsx
      {ch.status === 'beendet' && ch.mode === 'ziel' && (
        <section className="rounded-2xl border border-accent bg-card p-3">
          {siegerText(ch) !== null ? (
            <p className="text-sm font-bold text-ink">
              🏆 Sieger: {siegerText(ch)}
              {ch.prize && (
                <span className="font-normal text-ink-mute"> — {ch.prize}</span>
              )}
            </p>
          ) : ch.kann_sieger_setzen ? (
            <div className="flex items-end gap-2">
              <Select
                label="Sieger"
                className="flex-1"
                value={wahl}
                onChange={(e) => setWahl(e.target.value)}
              >
                <option value="">– bitte wählen –</option>
                {siegerOptionen(ch).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
              <button
                onClick={() => wahl && siegerSetzen.mutate(parseWahl(wahl))}
                disabled={!wahl || siegerSetzen.isPending}
                className="shrink-0 rounded-xl border border-accent px-3 py-2 text-xs font-bold text-accent disabled:opacity-50"
              >
                Sieger eintragen
              </button>
            </div>
          ) : (
            <p className="text-sm text-ink-mute">
              {ch.gewinner_ids.length > 0
                ? 'Sieger wird noch ausgelost.'
                : 'Niemand hat das Ziel erreicht.'}
            </p>
          )}
        </section>
      )}
```

Add `gruppeVon` and `siegerText` to `wertung.ts` (shared by the detail view and the row):

```ts
/** The group a person belongs to, by the members list. */
export function gruppeVon(ch: Challenge, userId: number): ChallengeGroup | undefined {
  return ch.groups.find((g) => g.members.some((m) => m.user_id === userId))
}

/** "Gruppe A", "Mia (Gruppe A)" or "Mia"; null while no winner is entered. */
export function siegerText(ch: Challenge): string | null {
  if (ch.sieger_group_id !== null && ch.sieger_group_id !== undefined) {
    return ch.groups.find((g) => g.id === ch.sieger_group_id)?.name ?? 'unbekannt'
  }
  if (ch.sieger_id === null || ch.sieger_id === undefined) return null
  const name = ch.standings.find((s) => s.user_id === ch.sieger_id)?.display_name ?? 'unbekannt'
  const gruppe = ch.team_mode ? gruppeVon(ch, ch.sieger_id) : undefined
  return gruppe ? `${name} (${gruppe.name})` : name
}
```

Add these helpers above the `ChallengeDetail` component (import `siegerText` from `./wertung`):

```tsx
/** Select options: qualified groups first, then their members; plain people otherwise. */
function siegerOptionen(ch: Challenge): { value: string; label: string }[] {
  if (!ch.team_mode) {
    return ch.standings
      .filter((s) => ch.gewinner_ids.includes(s.user_id))
      .map((s) => ({ value: `u:${s.user_id}`, label: s.display_name }))
  }
  const gruppen = ch.groups.filter((g) => g.geschafft)
  return [
    ...gruppen.map((g) => ({ value: `g:${g.id}`, label: g.name })),
    ...gruppen.flatMap((g) =>
      g.members.map((m) => ({ value: `u:${m.user_id}`, label: `${m.display_name} (${g.name})` })),
    ),
  ]
}

function parseWahl(wahl: string): SiegerWahl {
  const [art, id] = wahl.split(':')
  return art === 'g' ? { group_id: Number(id) } : { user_id: Number(id) }
}
```

In the existing (non-team) admin test in `ChallengeDetail.test.tsx`, the select value is now `u:<id>`: change line 83 to `fireEvent.change(screen.getByLabelText('Sieger'), { target: { value: 'u:2' } })`.

- [ ] **Step 4: `ChallengeRow.tsx`**

Replace `winnerName` and `outcome`:

```tsx
import { siegerText } from './wertung'

// The one winner. Entered prize winner first (group or person). Otherwise:
// group challenge → the winning groups' names; target mode → the only
// qualifier when there is exactly one; ranking mode → rank 1. Null while a
// target challenge with several qualifiers still waits for the draw.
function winnerName(ch: Challenge): string | null {
  const entered = siegerText(ch)
  if (entered !== null) return entered
  if (ch.team_mode) {
    const namen = ch.groups.filter((g) => g.geschafft).map((g) => g.name)
    return namen.length > 0 ? namen.join(', ') : null
  }
  const qualified = ch.standings
    .filter((s) => ch.gewinner_ids.includes(s.user_id))
    .sort((a, b) => a.rank - b.rank)
  if (qualified.length === 0) return null
  if (ch.mode === 'rangliste' || qualified.length === 1) return qualified[0].display_name
  return null
}
```

`outcome` stays as is.

- [ ] **Step 5: `ChallengeHeroCard.tsx`**

Import `meineGruppe` from `./wertung`. Inside the component, before `return`:

```tsx
  const gruppe = meineGruppe(ch)
  const wert = gruppe ? gruppe.value : (meins?.value ?? 0)
  const pct = Math.round(fortschritt(ch, wert) * 100)
```

(replace the existing `wert` / `pct` lines). Replace the big number paragraph's suffix so a group challenge shows "pro Kopf", and the rank line:

```tsx
      <p className="mt-1.5 text-2xl font-extrabold text-ink">
        {wert}
        {ch.mode === 'ziel' && ch.target !== null && (
          <span className="text-sm font-semibold text-ink-mute">
            {' '}
            / {ch.target} {einheit(ch.metric)}
            {gruppe && ' pro Kopf'}
          </span>
        )}
      </p>
```

```tsx
      {gruppe ? (
        <p className="mt-1 text-[11px] text-ink-mute">
          {gruppe.name} · Platz {gruppe.rank} von {ch.groups.length}
        </p>
      ) : (
        meins && (
          <p className="mt-1 text-[11px] text-ink-mute">
            Platz {meins.rank} von {ch.standings.length}
          </p>
        )
      )}
```

- [ ] **Step 6: Run**

Run: `cd frontend && npx vitest run src/components/challenges src/pages && npx tsc -b`
Expected: PASS, tsc clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/challenges/ChallengeDetail.tsx frontend/src/components/challenges/ChallengeDetail.test.tsx frontend/src/components/challenges/ChallengeRow.tsx frontend/src/components/challenges/ChallengeRow.test.tsx frontend/src/components/challenges/ChallengeHeroCard.tsx
git commit -m "feat(challenges): group or person as prize winner, group texts in row and hero"
```

---

### Task 14: Group editor page and route

**Files:**
- Create: `frontend/src/components/challenges/GroupEditor.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/components/challenges/GroupEditor.test.tsx` (new)

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/challenges/GroupEditor.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GroupEditor from './GroupEditor'

const member = (user_id: number, display_name: string, value = 0) => ({
  user_id, display_name, avatar: '🦊', value, rank: 0, geschafft: false, nicht_mehr_schaffbar: false,
})

const { detail, seeding } = vi.hoisted(() => ({
  detail: {
    id: 1, title: 'Teams', status: 'geplant', team_mode: true, group_count: 2, seeding_days: 30,
    join_mode: 'opt_in', groups_drawn: true, kann_gruppen_bearbeiten: true,
    mode: 'ziel', target: 100, metric: 'mm', category_ids: [], top_n: 1, streak_min_mm: 5,
    period_start: '2026-10-01', period_end: '2026-10-31', description: '', prize: null,
    creator_id: 1, vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
    standings: [], mein_stand: null, gewinner_ids: [], sieger_id: null, sieger_group_id: null,
    kann_sieger_setzen: false, meine_gruppe_id: 1, created_at: '', resolved_at: null,
    groups: [
      { id: 1, name: 'Gruppe A', size: 2, sum: 0, value: 0, rank: 1, geschafft: false,
        members: [member(1, 'Rick'), member(2, 'Mia')] },
      { id: 2, name: 'Gruppe B', size: 1, sum: 0, value: 0, rank: 2, geschafft: false,
        members: [member(3, 'Lea')] },
    ],
    unassigned: [member(4, 'Tom')],
  },
  seeding: [
    { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 120 },
    { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 80 },
    { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 60 },
    { user_id: 4, display_name: 'Tom', avatar: '🐸', value: 40 },
    { user_id: 5, display_name: 'Uli', avatar: '🐼', value: 10 },
  ],
}))

vi.mock('../../api/client', () => ({
  api: {
    challenge: vi.fn(),
    challengeSeeding: vi.fn(),
    saveChallengeGroups: vi.fn(),
    drawChallengeGroups: vi.fn(),
  },
}))
vi.mock('../ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderEditor() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/arena/challenges/1/gruppen']}>
        <Routes>
          <Route path="/arena/challenges/:id/gruppen" element={<GroupEditor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('GroupEditor', () => {
  beforeEach(async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue(detail as never)
    vi.mocked(api.challengeSeeding).mockResolvedValue(seeding)
    vi.mocked(api.saveChallengeGroups).mockResolvedValue(detail as never)
    vi.mocked(api.drawChallengeGroups).mockResolvedValue(detail as never)
  })

  it('renders groups with seeding values and the unassigned block, pool members first', async () => {
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    const a = screen.getByTestId('editor-group-1')
    expect(a).toHaveTextContent('Rick')
    expect(a).toHaveTextContent('120')
    const frei = screen.getByTestId('editor-unassigned')
    const namen = within(frei).getAllByTestId('person-name').map((n) => n.textContent)
    expect(namen).toEqual(['Tom', 'Uli'])
    expect(screen.queryByText('ungespeichert')).toBeNull()
  })

  it('moves, removes, adds, renames and saves', async () => {
    const { api } = await import('../../api/client')
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())

    // move Mia from A to B
    fireEvent.change(screen.getByLabelText('Mia verschieben'), { target: { value: 'g:2' } })
    // remove Lea from B
    fireEvent.change(screen.getByLabelText('Lea verschieben'), { target: { value: 'remove' } })
    // add Tom to A
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    // rename A
    fireEvent.change(screen.getByDisplayValue('Gruppe A'), { target: { value: 'Flitzer' } })
    expect(screen.getByText('ungespeichert')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Speichern'))
    await waitFor(() => expect(api.saveChallengeGroups).toHaveBeenCalledWith(1, [
      { id: 1, name: 'Flitzer', member_ids: [1, 4] },
      { id: 2, name: 'Gruppe B', member_ids: [2] },
    ]))
    await waitFor(() => expect(screen.queryByText('ungespeichert')).toBeNull())
  })

  it('warns when group sizes differ by more than one', async () => {
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    expect(screen.queryByText(/ungleich groß/)).toBeNull()
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    expect(screen.getByText(/ungleich groß/)).toBeInTheDocument()
  })

  it('asks twice before redrawing over unsaved edits', async () => {
    const { api } = await import('../../api/client')
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    fireEvent.click(screen.getByText('Neu auslosen'))
    expect(api.drawChallengeGroups).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Wirklich neu auslosen?'))
    await waitFor(() => expect(api.drawChallengeGroups).toHaveBeenCalledWith(1))
  })

  it('shows a notice when editing is not allowed', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({ ...detail, kann_gruppen_bearbeiten: false } as never)
    renderEditor()
    await waitFor(() =>
      expect(screen.getByText('Die Gruppen lassen sich hier nicht bearbeiten.')).toBeInTheDocument(),
    )
  })
})
```

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/components/challenges/GroupEditor.test.tsx`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `GroupEditor.tsx`**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Challenge, ChallengeGroupInput, SeedingEntry } from '../../api/client'
import Avatar from '../ui/Avatar'
import Button from '../ui/Button'
import Input from '../ui/Input'
import { useToast } from '../ui/Toast'
import { einheit } from './wertung'

type Person = SeedingEntry

function toInputs(ch: Challenge): ChallengeGroupInput[] {
  return ch.groups.map((g) => ({
    id: g.id,
    name: g.name,
    member_ids: g.members.map((m) => m.user_id),
  }))
}

function sameGroups(a: ChallengeGroupInput[], b: ChallengeGroupInput[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

// Per person: a small select instead of drag and drop, which is unreliable on
// phones. Value "g:<id>" moves into that group, "remove" takes the person out.
function MoveSelect({
  person, current, groups, onMove,
}: {
  person: Person
  current: number | null
  groups: ChallengeGroupInput[]
  onMove: (target: number | null) => void
}) {
  return (
    <select
      aria-label={`${person.display_name} verschieben`}
      value=""
      onChange={(e) => {
        const v = e.target.value
        if (v === 'remove') onMove(null)
        else if (v.startsWith('g:')) onMove(Number(v.slice(2)))
      }}
      className="rounded-lg border border-line bg-surface px-1.5 py-1 text-[11px] text-ink"
    >
      <option value="">{current === null ? '→ Gruppe…' : '…'}</option>
      {groups
        .filter((g) => g.id !== current)
        .map((g) => (
          <option key={g.id} value={`g:${g.id}`}>
            → {g.name}
          </option>
        ))}
      {current !== null && <option value="remove">Entfernen</option>}
    </select>
  )
}

function PersonRow({
  person, ch, current, groups, onMove,
}: {
  person: Person
  ch: Challenge
  current: number | null
  groups: ChallengeGroupInput[]
  onMove: (target: number | null) => void
}) {
  return (
    <li className="flex items-center gap-2 text-xs">
      <Avatar value={person.avatar} size="sm" />
      <span data-testid="person-name" className="min-w-0 flex-1 truncate text-ink">
        {person.display_name}
      </span>
      <span className="shrink-0 text-[10px] text-ink-mute">
        {person.value} {einheit(ch.metric)}
      </span>
      <MoveSelect person={person} current={current} groups={groups} onMove={onMove} />
    </li>
  )
}

export default function GroupEditor() {
  const { id } = useParams()
  const challengeId = Number(id)
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: ch, error } = useQuery({
    queryKey: ['challenge', challengeId],
    queryFn: () => api.challenge(challengeId),
  })
  const { data: seeding = [] } = useQuery({
    queryKey: ['challenge-seeding', challengeId],
    queryFn: () => api.challengeSeeding(challengeId),
    enabled: !!ch?.kann_gruppen_bearbeiten,
  })
  const [groups, setGroups] = useState<ChallengeGroupInput[]>([])
  const [confirmRedraw, setConfirmRedraw] = useState(false)
  useEffect(() => {
    if (ch) setGroups(toInputs(ch))
  }, [ch])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['challenge', challengeId] })
    queryClient.invalidateQueries({ queryKey: ['challenges'] })
  }
  const speichern = useMutation({
    mutationFn: () => api.saveChallengeGroups(challengeId, groups),
    onSuccess: (neu) => {
      queryClient.setQueryData(['challenge', challengeId], neu)
      invalidate()
      toast('Gruppen gespeichert', 'ok')
    },
    onError: (e: Error) => toast(e.message),
  })
  const auslosen = useMutation({
    mutationFn: () => api.drawChallengeGroups(challengeId),
    onSuccess: (neu) => {
      setConfirmRedraw(false)
      queryClient.setQueryData(['challenge', challengeId], neu)
      invalidate()
      toast('Gruppen neu ausgelost', 'ok')
    },
    onError: (e: Error) => toast(e.message),
  })

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (!ch) return <p className="p-8 text-sm text-ink-mute">Lädt…</p>
  if (!ch.kann_gruppen_bearbeiten)
    return (
      <div className="mx-auto max-w-xl space-y-3">
        <p className="text-sm text-ink-mute">Die Gruppen lassen sich hier nicht bearbeiten.</p>
        <Link to={`/arena/challenges/${ch.id}`} className="text-xs font-bold text-accent hover:underline">
          ← zur Challenge
        </Link>
      </div>
    )

  const personen = new Map<number, Person>(seeding.map((p) => [p.user_id, p]))
  // Members that the seeding list has not delivered yet (query still loading).
  const personOf = (userId: number): Person =>
    personen.get(userId) ?? {
      user_id: userId,
      display_name: ch.standings.find((s) => s.user_id === userId)?.display_name ?? `#${userId}`,
      avatar: 'icon:laufen',
      value: 0,
    }
  const zugeordnet = new Set(groups.flatMap((g) => g.member_ids))
  const poolIds = new Set(ch.unassigned.map((u) => u.user_id))
  const frei = seeding
    .filter((p) => !zugeordnet.has(p.user_id))
    .sort((a, b) => Number(poolIds.has(b.user_id)) - Number(poolIds.has(a.user_id)) || b.value - a.value)
  const dirty = !sameGroups(groups, toInputs(ch))
  const sizes = groups.map((g) => g.member_ids.length)
  const ungleich = sizes.length > 0 && Math.max(...sizes) - Math.min(...sizes) > 1

  const move = (userId: number, target: number | null) =>
    setGroups((gs) =>
      gs.map((g) => ({
        ...g,
        member_ids: [
          ...g.member_ids.filter((uid) => uid !== userId),
          ...(g.id === target ? [userId] : []),
        ],
      })),
    )
  const rename = (gid: number, name: string) =>
    setGroups((gs) => gs.map((g) => (g.id === gid ? { ...g, name } : g)))
  const redraw = () => {
    if (dirty && !confirmRedraw) {
      setConfirmRedraw(true)
      return
    }
    auslosen.mutate()
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <Link to={`/arena/challenges/${ch.id}`} className="text-xs font-bold text-accent hover:underline">
        ← {ch.title}
      </Link>
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="flex-1 text-lg font-extrabold text-ink">Gruppen</h1>
        {dirty && (
          <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
            ungespeichert
          </span>
        )}
        <Button variant="ghost" onClick={redraw} disabled={auslosen.isPending}>
          {confirmRedraw ? 'Wirklich neu auslosen?' : 'Neu auslosen'}
        </Button>
        <Button onClick={() => speichern.mutate()} disabled={!dirty || speichern.isPending}>
          Speichern
        </Button>
      </header>
      {ungleich && (
        <p className="rounded-xl border border-accent/40 bg-accent/10 px-3 py-1.5 text-[11px] text-ink">
          Die Gruppen sind ungleich groß (Unterschied mehr als eine Person).
        </p>
      )}

      {groups.map((g) => {
        const summe = g.member_ids.reduce((s, uid) => s + personOf(uid).value, 0)
        const proKopf = g.member_ids.length ? Math.round((summe / g.member_ids.length) * 10) / 10 : 0
        return (
          <section key={g.id} data-testid={`editor-group-${g.id}`} className="rounded-2xl border border-line bg-card p-3">
            <div className="flex items-end gap-2">
              <Input
                label="Name"
                className="flex-1"
                value={g.name}
                onChange={(e) => rename(g.id, e.target.value)}
              />
              <span className="pb-2 text-[11px] text-ink-mute">
                {g.member_ids.length} Pers. · {Math.round(summe)} {einheit(ch.metric)} · {proKopf} pro Kopf
              </span>
            </div>
            <ul className="mt-2 space-y-1">
              {g.member_ids.map((uid) => (
                <PersonRow
                  key={uid}
                  person={personOf(uid)}
                  ch={ch}
                  current={g.id}
                  groups={groups}
                  onMove={(t) => move(uid, t)}
                />
              ))}
              {g.member_ids.length === 0 && (
                <li className="text-xs text-danger">Leer — eine Gruppe braucht mindestens eine Person.</li>
              )}
            </ul>
          </section>
        )
      })}

      <section data-testid="editor-unassigned" className="rounded-2xl border border-dashed border-line p-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-ink-mute">Nicht zugeordnet</h2>
        <ul className="mt-2 space-y-1">
          {frei.map((p) => (
            <PersonRow
              key={p.user_id}
              person={p}
              ch={ch}
              current={null}
              groups={groups}
              onMove={(t) => move(p.user_id, t)}
            />
          ))}
          {frei.length === 0 && <li className="text-xs text-ink-mute">Alle sind zugeordnet.</li>}
        </ul>
      </section>
      <p className="text-[11px] text-ink-mute">
        Setzliste: {ch.metric === 'anzahl' ? 'Aktivitäten' : 'MM'} der letzten {ch.seeding_days} Tage.
      </p>
    </div>
  )
}
```

Note on `move`: appending to the target keeps order stable; the saved `member_ids` for the test are `[1, 4]` (Rick stays, Tom appended) and `[2]` (Lea removed, Mia appended) — matching the expected payload.

- [ ] **Step 4: Route**

In `frontend/src/App.tsx`: `import GroupEditor from './components/challenges/GroupEditor'` and, inside the `/arena` route after `challenges/:id`:

```tsx
          <Route path="challenges/:id/gruppen" element={<GroupEditor />} />
```

- [ ] **Step 5: Run**

Run: `cd frontend && npx vitest run src/components/challenges/GroupEditor.test.tsx src/App.test.tsx && npx tsc -b`
Expected: PASS, tsc clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/challenges/GroupEditor.tsx frontend/src/components/challenges/GroupEditor.test.tsx frontend/src/App.tsx
git commit -m "feat(challenges): admin group editor page"
```

---

### Task 15: Feed rendering for group payloads

**Files:**
- Modify: `frontend/src/components/feed/FeedItem.tsx`
- Test: `frontend/src/components/feed/FeedItem.test.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/feed/FeedItem.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { FeedEvent } from '../../api/client'
import FeedItem from './FeedItem'

vi.mock('./ReactionBar', () => ({ default: () => null }))

function ev(over: Partial<FeedEvent>): FeedEvent {
  return {
    id: 1, type: 'challenge_end', user_id: null, display_name: null,
    avatar: null, created_at: '2026-09-01T06:00:00Z', payload: {}, reactions: [],
    ...over,
  } as unknown as FeedEvent
}

// getByText matches an element's own text nodes, so the regex targets the
// sentence fragment in the wrapping <span>; toHaveTextContent then checks the
// whole sentence including the <b> children.
describe('FeedItem group challenge texts', () => {
  it('qualified group', () => {
    render(<FeedItem ev={ev({ type: 'challenge_qualified', payload: { title: 'Teams', group_name: 'Gruppe A' } })} />)
    expect(screen.getByText(/hat das Ziel geknackt/)).toHaveTextContent('Gruppe A hat das Ziel geknackt')
  })
  it('winning groups at the end', () => {
    render(<FeedItem ev={ev({ payload: { title: 'Teams', prize: 'Kuchen', gewinner_namen: ['Rick', 'Mia'], gewinner_gruppen: ['Gruppe A'] } })} />)
    expect(screen.getByText(/ist vorbei/)).toHaveTextContent('Gruppe A gewinnt: Kuchen')
  })
  it('group as prize winner', () => {
    render(<FeedItem ev={ev({ type: 'challenge_sieger', payload: { title: 'Teams', gruppe: 'Gruppe A', user_id: null } })} />)
    expect(screen.getByText(/gewinnt/)).toHaveTextContent('Gruppe A gewinnt Teams')
  })
  it('person from a group as prize winner', () => {
    render(<FeedItem ev={ev({ type: 'challenge_sieger', display_name: 'Mia', payload: { title: 'Teams', gruppe: 'Gruppe A', user_id: 2 } })} />)
    expect(screen.getByText(/gewinnt/)).toHaveTextContent('Mia (Gruppe A) gewinnt Teams')
  })
})
```

If `FeedEvent` has fields not covered by the `ev` helper, add them to the object with neutral values so `tsc` is happy (the cast keeps vitest running either way).

- [ ] **Step 2: Run, expect failure**

Run: `cd frontend && npx vitest run src/components/feed/FeedItem.test.tsx`
Expected: FAIL on the group texts.

- [ ] **Step 3: Implement**

In `FeedItem.tsx` replace the three challenge blocks:

```tsx
      {ev.type === 'challenge_qualified' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>✅</span>
          <span className="text-ink">
            <b>{ev.payload.group_name ?? ev.display_name}</b> hat das Ziel geknackt —{' '}
            <b className="text-accent">{ev.payload.title}</b>
          </span>
        </div>
      )}
      {ev.type === 'challenge_sieger' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏆</span>
          <span className="text-ink">
            <b>
              {ev.display_name
                ? ev.payload.gruppe
                  ? `${ev.display_name} (${ev.payload.gruppe})`
                  : ev.display_name
                : ev.payload.gruppe}
            </b>{' '}
            gewinnt <b>{ev.payload.title}</b>
            {ev.payload.prize && (
              <span className="text-ink-mute"> · 🎁 {ev.payload.prize}</span>
            )}
          </span>
        </div>
      )}
      {ev.type === 'challenge_end' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏆</span>
          <span className="text-ink">
            <b>{ev.payload.title}</b> ist vorbei —{' '}
            {(ev.payload.gewinner_gruppen?.length ?? 0) > 0 ? (
              <>
                <b>{undListe(ev.payload.gewinner_gruppen ?? [])}</b>
                {ev.payload.prize ? ` gewinnt: ${ev.payload.prize}` : ' vorn'}
              </>
            ) : ev.payload.gewinner_namen && ev.payload.gewinner_namen.length > 0 ? (
              <>
                <b>{undListe(ev.payload.gewinner_namen)}</b>
                {ev.payload.prize ? ` gewinnt: ${ev.payload.prize}` : ' vorn'}
              </>
            ) : (
              'niemand hat es geschafft'
            )}
          </span>
        </div>
      )}
```

- [ ] **Step 4: Run**

Run: `cd frontend && npx vitest run src/components/feed && npx tsc -b`
Expected: PASS, tsc clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/feed/FeedItem.tsx frontend/src/components/feed/FeedItem.test.tsx
git commit -m "feat(feed): group challenge texts"
```

---

### Task 16: Full verification and PR update

**Files:** none new.

- [ ] **Step 1: Backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: all PASS.

- [ ] **Step 2: Frontend lint, tests, build**

Run: `cd frontend && npm run lint; npm test; npm run build`
Expected: tests PASS, build succeeds. Lint may report the pre-existing errors in `Feed.tsx` / `ReactionBar.tsx` only; anything in files touched by this plan must be fixed.

- [ ] **Step 3: Manual smoke test in the browser (if the dev stack runs locally)**

Use the `run` skill to start backend and frontend. As admin: create a group challenge with "Alle automatisch dabei" and 3 groups → groups appear on the detail page; open "Gruppen bearbeiten", move one person, save, redraw; create an opt_in group challenge, join as a second user, draw. Note anything off in the PR description.

- [ ] **Step 4: Push and update PR #40**

```bash
git push
gh pr edit 40 --title "Group challenges with seeded draw" --body-file <updated body>
```

Update the PR body: it now contains spec, plan, and implementation. List the new endpoints, the migration, and the manual smoke-test result. Keep the trailer:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_012KrtS1A3RAQan4QLRcM2we
```

- [ ] **Step 5: Update memory notes**

In `C:\Users\Erik\.claude\projects\C--Users-Erik-Documents-MeterMachen\memory\metermachen-backlog.md`, mark the group challenge item as implemented in PR #40 (pending merge) and note that redesign chunk 2 is next.
