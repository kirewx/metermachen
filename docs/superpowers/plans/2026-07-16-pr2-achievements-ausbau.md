# PR 2: Achievements-Ausbau — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistierte Achievement-Unlocks mit Bronze/Silber/Gold-Stufen, Erster-Bonus, drei Hidden Achievements, Testphasen-Sieger sowie anwählbare Special-Emojis (Leaderboard, Blackboard, Avatar).

**Architecture:** Neue Tabelle `AchievementUnlock` (unique je user+key, „einmal freigeschaltet bleibt freigeschaltet"). Neuer Service `services/achievements.py` hält Definitionen + `check_unlocks(session, user_id)` (insert-or-ignore), aufgerufen nach Aktivitäts-Create/Patch, im Strava-Import und bei `GET /api/achievements`. Der Router liefert erweiterte `AchievementOut`-Einträge (hidden/tier/discipline/emoji/showcased/claimed_by); `PATCH /api/achievements/{key}` toggelt `showcased`. `compute_comparison` liefert pro Nutzer `emojis` (nur showcased). Frontend: gruppierte Stufen-Karten, Einmal-Karten mit Namen, „???"-Karten, Emoji-Toggle, Emojis im Leaderboard/Blackboard, Avatar-Reiter „Erspielt".

**Tech Stack:** FastAPI + SQLModel + SQLite (pytest), React 19 + TanStack Query (vitest).

**Spec:** `docs/superpowers/specs/2026-07-16-regeln-achievements-uhrzeit-blackboard-design.md` (§2)

**Branch:** `feature/achievements-ausbau`, abzweigen von `main` **nachdem PR 1 gemergt ist** (Task 10 fasst die Blackboard-Komponente aus PR 1 an). PR gegen `main`.

**Kommandos** (vom Repo-Root):
- Backend-Tests: `cd backend && python -m pytest -q`
- Frontend: `cd frontend && npm run test` / `npm run lint` / `npm run build`

---

### Task 1: Modell `AchievementUnlock` + Migrations-Test

**Files:**
- Modify: `backend/app/models.py` (ans Ende)
- Test: `backend/tests/test_migration.py`, `backend/tests/test_models.py`

Die Tabelle ist neu — `init_db()` legt sie über `SQLModel.metadata.create_all` an, ein `ALTER` in `migrate()` ist nicht nötig. `showcased` ist von Anfang an Teil des Schemas.

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_migration.py`:

```python
def test_init_erzeugt_achievementunlock_tabelle(tmp_path):
    from sqlmodel import SQLModel

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    # Bestands-DB-Simulation: create_all + migrate = init_db()-Ablauf
    SQLModel.metadata.create_all(engine)
    migrate(engine)
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("achievementunlock")'))]
    assert {"id", "user_id", "key", "unlocked_at", "context_json", "showcased"} <= set(cols)
```

Ans Ende von `backend/tests/test_models.py`:

```python
def test_achievement_unlock_unique_pro_user_und_key(session):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import AchievementUnlock

    session.add(AchievementUnlock(user_id=1, key="stufe_rad_gold"))
    session.commit()
    session.add(AchievementUnlock(user_id=1, key="stufe_rad_gold"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    # gleiche Achievement-Keys für andere Nutzer sind ok
    session.add(AchievementUnlock(user_id=2, key="stufe_rad_gold"))
    session.commit()
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `cd backend && python -m pytest tests/test_migration.py::test_init_erzeugt_achievementunlock_tabelle tests/test_models.py::test_achievement_unlock_unique_pro_user_und_key -q`
Expected: FAIL (ImportError / Tabelle fehlt)

- [ ] **Step 3: Modell implementieren**

Ans Ende von `backend/app/models.py`:

```python
class AchievementUnlock(SQLModel, table=True):
    """Persistierter Achievement-Freischalt-Zeitpunkt. Einmal freigeschaltet
    bleibt freigeschaltet, auch wenn Aktivitäten später geändert werden."""

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_unlock_user_key"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key: str
    unlocked_at: datetime = Field(default_factory=utcnow)
    context_json: str = "{}"  # z. B. {"km": 4003.2} oder {"von": "...", "bis": "..."}
    showcased: bool = True  # Special-Emoji neben dem Namen zeigen (Spec §2.6)
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_migration.py tests/test_models.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_migration.py backend/tests/test_models.py
git commit -m "feat(achievements): Tabelle AchievementUnlock (unique user+key, showcased)"
```

---

### Task 2: Service-Modul — Definitionen + Bucket-Umzug

**Files:**
- Create: `backend/app/services/achievements.py`
- Modify: `backend/app/routers/achievements.py` (Bucket-Logik durch Re-Import ersetzen)
- Test: `backend/tests/test_achievements.py` (Bestand bleibt grün — importiert aus dem Router)

Die Bucket-Zuordnung zieht in den Service (der Service braucht sie, Router re-exportiert für Bestands-Importe).

- [ ] **Step 1: Service-Modul anlegen**

`backend/app/services/achievements.py` (neu):

```python
"""Achievement-Definitionen + persistierte Unlocks (Spec §2).

Fortschritt wird live berechnet; beim ersten Erreichen wird ein
AchievementUnlock gespeichert (insert-or-ignore über den Unique-Constraint).
Einmal freigeschaltet bleibt freigeschaltet.
"""

import json
from collections import defaultdict
from datetime import date as date_type
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import AchievementUnlock, Activity, Category, Season, User

RAD, LAUF, SCHWIMM = "rad", "lauf", "schwimm"

_BUCKET_BY_ICON = {"rad": RAD, "laufen": LAUF, "schwimmen": SCHWIMM}
_BUCKET_BY_STRAVA = {
    "Ride": RAD, "MountainBikeRide": RAD, "GravelRide": RAD, "EBikeRide": RAD,
    "VirtualRide": RAD,
    "Run": LAUF, "TrailRun": LAUF, "VirtualRun": LAUF,
    "Swim": SCHWIMM,
}
_BUCKET_BY_NAME = {RAD: ("rad", "bike"), LAUF: ("lauf", "jogg"), SCHWIMM: ("schwimm",)}


def bucket_for_category(cat: Category) -> str | None:
    if cat.icon in _BUCKET_BY_ICON:
        return _BUCKET_BY_ICON[cat.icon]
    for sport in json.loads(cat.strava_sport_types or "[]"):
        if sport in _BUCKET_BY_STRAVA:
            return _BUCKET_BY_STRAVA[sport]
    name = cat.name.lower()
    for bucket, needles in _BUCKET_BY_NAME.items():
        if any(n in name for n in needles):
            return bucket
    return None


DISZIPLIN_LABEL = {RAD: "Rad", LAUF: "Laufen", SCHWIMM: "Schwimmen"}
DISZIPLIN_ICON = {RAD: "rad", LAUF: "laufen", SCHWIMM: "schwimmen"}
TIERS = ("bronze", "silber", "gold")

# Stufen-Ziele in rohen km (Spec §2.3)
STUFEN_ZIELE: dict[str, dict[str, float]] = {
    RAD: {"bronze": 1000.0, "silber": 2500.0, "gold": 4000.0},
    LAUF: {"bronze": 250.0, "silber": 500.0, "gold": 1000.0},
    SCHWIMM: {"bronze": 100.0, "silber": 250.0, "gold": 400.0},
}


def stufen_key(bucket: str, tier: str) -> str:
    return f"stufe_{bucket}_{tier}"


def erster_key(bucket: str) -> str:
    return f"erster_gold_{bucket}"


# (key, titel, beschreibung, icon) — nur für die eigene Person maskiert, solange
# nicht freigeschaltet (Spec §2.3/§2.4)
HIDDEN_DEFS: list[tuple[str, str, str, str]] = [
    ("kletterkoenig", "Kletterkönig", "1000 Höhenmeter an einem Tag.", "berg"),
    ("hattrick", "Hattrick", "Drei Aktivitäten an einem Tag.", "blitz"),
    ("wochenkoenig", "Wochenkönig",
     "Sieben Tage am Stück alleiniger Platz 1 der Challenge.", "pokal"),
]

# (key, titel, beschreibung, icon) — bekommt genau eine Person (bzw. bei
# Gleichstand im Testphasen-Sieg alle Erstplatzierten)
EINMAL_DEFS: list[tuple[str, str, str, str]] = [
    ("erster_gold_rad", "Erster: Rad Gold",
     "Bekommt nur, wer die Gold-Stufe Rad als erste Person knackt.", "rad"),
    ("erster_gold_lauf", "Erster: Laufen Gold",
     "Bekommt nur, wer die Gold-Stufe Laufen als erste Person knackt.", "laufen"),
    ("erster_gold_schwimm", "Erster: Schwimmen Gold",
     "Bekommt nur, wer die Gold-Stufe Schwimmen als erste Person knackt.", "schwimmen"),
    ("testphasen_sieger", "Testphasen-Sieger",
     "Platz 1 der Warm-up-Phase zum Challenge-Start.", "pokal"),
]

# Special-Emojis (Spec §2.6). Stufen vergeben bewusst KEIN Emoji.
EMOJIS: dict[str, str] = {
    "testphasen_sieger": "🏆",
    "erster_gold_rad": "🚴",
    "erster_gold_lauf": "🏃",
    "erster_gold_schwimm": "🏊",
    "kletterkoenig": "🏔️",
    "hattrick": "🎩",
    "wochenkoenig": "👑",
}
```

(`check_unlocks` kommt in Task 3–5 dazu; `Session`/`select`/`IntegrityError`/`date_type`/`timedelta`/`defaultdict`/`Activity`/`Season`/`User`/`AchievementUnlock` werden dann benutzt — die Imports stehen schon bereit.)

- [ ] **Step 2: Router auf den Service umstellen**

In `backend/app/routers/achievements.py` die Zeilen von `RAD, LAUF, SCHWIMM = ...` bis einschließlich der Funktion `bucket_for_category` **löschen** und durch einen Re-Import ersetzen (hält `from app.routers.achievements import bucket_for_category, RAD, ...` in Bestandstests am Leben):

```python
from ..services.achievements import LAUF, RAD, SCHWIMM, bucket_for_category
```

Dabei den nicht mehr benötigten Import `json` im Router-Kopf entfernen (wird nach dem Umzug nur noch von der Bucket-Logik gebraucht — prüfen: `json` wird im Router sonst nirgends benutzt).

- [ ] **Step 3: Bestandstests laufen lassen**

Run: `cd backend && python -m pytest tests/test_achievements.py -q`
Expected: alle PASS (Re-Import deckt die alten Importpfade)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/achievements.py backend/app/routers/achievements.py
git commit -m "refactor(achievements): Bucket-Logik in Service verschoben, Definitionen ergänzt"
```

---

### Task 3: `check_unlocks` — Stufen + Erster-Bonus

**Files:**
- Modify: `backend/app/services/achievements.py`
- Test: `backend/tests/test_achievement_unlocks.py` (neu)

- [ ] **Step 1: Failing Tests schreiben**

`backend/tests/test_achievement_unlocks.py` (neu):

```python
from datetime import date, timedelta

from sqlmodel import select

from app.models import AchievementUnlock, Activity, Season
from app.services.achievements import check_unlocks
from tests.conftest import make_category, make_user


def add_act(session, user, cat, km, d=date(2026, 8, 1), elevation=None):
    session.add(Activity(
        user_id=user.id, category_id=cat.id, date=d, distance_km=km, elevation_m=elevation
    ))
    session.commit()


def keys_of(session, user):
    return {
        u.key
        for u in session.exec(
            select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
        ).all()
    }


def test_stufen_grenzen(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, user, lauf, 249.9)
    check_unlocks(session, user.id)
    assert keys_of(session, user) == set()
    add_act(session, user, lauf, 0.1)  # exakt 250 → Bronze
    check_unlocks(session, user.id)
    assert keys_of(session, user) == {"stufe_lauf_bronze"}
    add_act(session, user, lauf, 750.0)  # 1000 → Silber UND Gold in einem Lauf
    check_unlocks(session, user.id)
    assert {"stufe_lauf_silber", "stufe_lauf_gold"} <= keys_of(session, user)


def test_check_unlocks_ist_idempotent(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, user, lauf, 300.0)
    check_unlocks(session, user.id)
    check_unlocks(session, user.id)
    unlocks = session.exec(
        select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
    ).all()
    assert len(unlocks) == 1


def test_unlock_bleibt_nach_loeschung(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, user, lauf, 300.0)
    check_unlocks(session, user.id)
    for act in session.exec(select(Activity)).all():
        session.delete(act)
    session.commit()
    check_unlocks(session, user.id)
    assert "stufe_lauf_bronze" in keys_of(session, user)


def test_erster_bonus_reihenfolge_der_persistierung(session):
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen")
    # Lisa erreicht Gold mit ÄLTEREM Aktivitätsdatum, aber Eriks Unlock wird
    # zuerst persistiert → Erik bekommt den Bonus (Zurückdatieren klaut nichts).
    add_act(session, erik, lauf, 1000.0, d=date(2026, 9, 1))
    check_unlocks(session, erik.id)
    add_act(session, lisa, lauf, 1000.0, d=date(2026, 8, 1))
    check_unlocks(session, lisa.id)
    assert "erster_gold_lauf" in keys_of(session, erik)
    assert "erster_gold_lauf" not in keys_of(session, lisa)
    assert "stufe_lauf_gold" in keys_of(session, lisa)
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py -q`
Expected: FAIL (ImportError: `check_unlocks` existiert nicht)

- [ ] **Step 3: Implementieren**

Ans Ende von `backend/app/services/achievements.py`:

```python
def _existing_keys(session: Session, user_id: int) -> set[str]:
    rows = session.exec(
        select(AchievementUnlock.key).where(AchievementUnlock.user_id == user_id)
    ).all()
    return set(rows)


def _unlock(session: Session, user_id: int, key: str, context: dict | None = None) -> bool:
    """Insert-or-ignore: Race (Webhook + Seitenaufruf) fängt der Unique-Constraint ab."""
    session.add(AchievementUnlock(
        user_id=user_id, key=key, context_json=json.dumps(context or {})
    ))
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False


def check_unlocks(session: Session, user_id: int) -> None:
    """Prüft alle Unlock-Bedingungen für einen Nutzer und persistiert Neues.
    Idempotent; bereits vergebene Unlocks werden nie zurückgenommen."""
    have = _existing_keys(session, user_id)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(select(Activity).where(Activity.user_id == user_id)).all()

    # Stufen (rohe km je Bucket) + Erster-Bonus direkt nach dem Gold-Insert
    bucket_km: dict[str, float] = defaultdict(float)
    for act in acts:
        cat = cats.get(act.category_id)
        bucket = bucket_for_category(cat) if cat else None
        if bucket is not None:
            bucket_km[bucket] += act.distance_km
    for bucket, ziele in STUFEN_ZIELE.items():
        for tier in TIERS:
            key = stufen_key(bucket, tier)
            if key in have or bucket_km[bucket] < ziele[tier]:
                continue
            if _unlock(session, user_id, key, {"km": round(bucket_km[bucket], 2)}):
                have.add(key)
                if tier == "gold":
                    schon_vergeben = session.exec(
                        select(AchievementUnlock).where(
                            AchievementUnlock.key == erster_key(bucket)
                        )
                    ).first()
                    if schon_vergeben is None and _unlock(session, user_id, erster_key(bucket)):
                        have.add(erster_key(bucket))
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/achievements.py backend/tests/test_achievement_unlocks.py
git commit -m "feat(achievements): check_unlocks mit Stufen und Erster-Bonus"
```

---

### Task 4: `check_unlocks` — Kletterkönig + Hattrick

**Files:**
- Modify: `backend/app/services/achievements.py` (in `check_unlocks`)
- Test: `backend/tests/test_achievement_unlocks.py`

- [ ] **Step 1: Failing Tests schreiben**

Anhängen an `backend/tests/test_achievement_unlocks.py`:

```python
def test_kletterkoenig_summiert_pro_kalendertag(session):
    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad")
    d = date(2026, 8, 1)
    add_act(session, user, rad, 20.0, d=d, elevation=600.0)
    add_act(session, user, rad, 20.0, d=d + timedelta(days=1), elevation=600.0)
    check_unlocks(session, user.id)
    assert "kletterkoenig" not in keys_of(session, user)  # 600 + 600 an ZWEI Tagen
    add_act(session, user, rad, 20.0, d=d, elevation=400.0)  # Tag 1: 600+400 = 1000
    check_unlocks(session, user.id)
    assert "kletterkoenig" in keys_of(session, user)


def test_hattrick_braucht_drei_eintraege_an_einem_tag(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    d = date(2026, 8, 1)
    add_act(session, user, lauf, 5.0, d=d)
    add_act(session, user, lauf, 5.0, d=d)
    add_act(session, user, lauf, 5.0, d=d + timedelta(days=1))
    check_unlocks(session, user.id)
    assert "hattrick" not in keys_of(session, user)
    add_act(session, user, lauf, 5.0, d=d)
    check_unlocks(session, user.id)
    assert "hattrick" in keys_of(session, user)
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py -q -k "kletterkoenig or hattrick"`
Expected: FAIL

- [ ] **Step 3: Implementieren**

In `check_unlocks` nach dem Stufen-Block anhängen:

```python
    # Hidden: Tagesgrenzen über das Aktivitätsdatum (Kalendertag)
    if "kletterkoenig" not in have:
        hm_pro_tag: dict[date_type, float] = defaultdict(float)
        for act in acts:
            hm_pro_tag[act.date] += act.elevation_m or 0.0
        tag = next((d for d, hm in sorted(hm_pro_tag.items()) if hm >= 1000.0), None)
        if tag is not None and _unlock(
            session, user_id, "kletterkoenig",
            {"datum": tag.isoformat(), "hm": round(hm_pro_tag[tag], 1)},
        ):
            have.add("kletterkoenig")

    if "hattrick" not in have:
        eintraege_pro_tag: dict[date_type, int] = defaultdict(int)
        for act in acts:
            eintraege_pro_tag[act.date] += 1
        tag = next((d for d, n in sorted(eintraege_pro_tag.items()) if n >= 3), None)
        if tag is not None and _unlock(
            session, user_id, "hattrick", {"datum": tag.isoformat()}
        ):
            have.add("hattrick")
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/achievements.py backend/tests/test_achievement_unlocks.py
git commit -m "feat(achievements): Hidden Achievements Kletterkönig und Hattrick"
```

---

### Task 5: `check_unlocks` — Wochenkönig + Testphasen-Sieger

**Files:**
- Modify: `backend/app/services/achievements.py`
- Test: `backend/tests/test_achievement_unlocks.py`

Beide brauchen `Season.start_date` des laufenden Jahres. Wochenkönig rechnet wie der Rennen-Tab (Kategorie-Faktor × `km_factor`), Testphasen-Sieger wie der Warm-up-Vergleich (Kategorie-Faktor, **ohne** `km_factor`).

- [ ] **Step 1: Failing Tests schreiben**

Anhängen an `backend/tests/test_achievement_unlocks.py`:

```python
def make_season(session, start):
    session.add(Season(year=start.year, goal_km=1000.0, start_date=start,
                       milestones_json="[]"))
    session.commit()


def test_wochenkoenig_sieben_tage_allein_vorn(session):
    heute = date.today()
    start = heute - timedelta(days=10)
    make_season(session, start)
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    # Erik führt ab Tag 0 allein, Lisa bleibt dahinter
    add_act(session, erik, lauf, 50.0, d=start)
    add_act(session, lisa, lauf, 10.0, d=start)
    check_unlocks(session, erik.id)
    assert "wochenkoenig" in keys_of(session, erik)
    check_unlocks(session, lisa.id)
    assert "wochenkoenig" not in keys_of(session, lisa)


def test_wochenkoenig_gleichstand_zaehlt_nicht(session):
    heute = date.today()
    start = heute - timedelta(days=10)
    make_season(session, start)
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, erik, lauf, 50.0, d=start)
    add_act(session, lisa, lauf, 50.0, d=start)  # Gleichstand über alle Tage
    check_unlocks(session, erik.id)
    assert "wochenkoenig" not in keys_of(session, erik)


def test_wochenkoenig_erst_ab_challenge_start(session):
    heute = date.today()
    start = heute - timedelta(days=3)  # erst 4 Tage Challenge → kein 7-Tage-Fenster
    make_season(session, start)
    erik = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    add_act(session, erik, lauf, 50.0, d=start)
    check_unlocks(session, erik.id)
    assert "wochenkoenig" not in keys_of(session, erik)


def test_testphasen_sieger_nach_start_gleichstand_alle(session):
    heute = date.today()
    start = heute  # Challenge startet heute → Warm-up abgeschlossen
    make_season(session, start)
    erik = make_user(session)
    lisa = make_user(session, username="lisa")
    tom = make_user(session, username="tom")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=2.0)
    d = start - timedelta(days=2)
    add_act(session, erik, lauf, 50.0, d=d)  # 100 gewertet
    add_act(session, lisa, lauf, 50.0, d=d)  # 100 gewertet — Gleichstand
    add_act(session, tom, lauf, 10.0, d=d)   # 20 gewertet
    for u in (erik, lisa, tom):
        check_unlocks(session, u.id)
    assert "testphasen_sieger" in keys_of(session, erik)
    assert "testphasen_sieger" in keys_of(session, lisa)
    assert "testphasen_sieger" not in keys_of(session, tom)


def test_testphasen_sieger_nicht_vor_start(session):
    heute = date.today()
    make_season(session, heute + timedelta(days=5))  # Challenge noch nicht gestartet
    erik = make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    add_act(session, erik, lauf, 50.0, d=heute - timedelta(days=1))
    check_unlocks(session, erik.id)
    assert keys_of(session, erik) == set()
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py -q -k "wochenkoenig or testphasen"`
Expected: FAIL

- [ ] **Step 3: Implementieren**

Ans Ende von `check_unlocks` anhängen:

```python
    # Saison-abhängige Achievements — brauchen Challenge-Start
    today = date_type.today()
    season = session.exec(select(Season).where(Season.year == today.year)).first()
    start = season.start_date if season else None
    if start is None or today < start:
        return

    if "testphasen_sieger" not in have:
        ctx = _testphasen_platz1(session, user_id, start)
        if ctx is not None and _unlock(session, user_id, "testphasen_sieger", ctx):
            have.add("testphasen_sieger")

    if "wochenkoenig" not in have:
        ctx = _wochenkoenig_fenster(session, user_id, start, today)
        if ctx is not None and _unlock(session, user_id, "wochenkoenig", ctx):
            have.add("wochenkoenig")
```

Und darunter die beiden Helfer:

```python
def _testphasen_platz1(session: Session, user_id: int, start: date_type) -> dict | None:
    """Gewertete km der Warm-up-Phase (Kategorie-Faktor, ohne Handicap) —
    gleiche Rechnung wie GET /api/comparison?phase=warmup. Bei Gleichstand
    bekommen alle Erstplatzierten das Achievement (jeweils in ihrem Lauf)."""
    aktive = {u.id for u in session.exec(select(User).where(User.is_active)).all()}
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    sums: dict[int, float] = defaultdict(float)
    for act in session.exec(select(Activity).where(Activity.date < start)).all():
        if act.user_id not in aktive or act.date.year != start.year:
            continue
        cat = cats.get(act.category_id)
        if cat is None:
            continue
        sums[act.user_id] += act.distance_km * cat.factor
    if not sums:
        return None
    best = round(max(sums.values()), 2)
    if round(sums.get(user_id, 0.0), 2) < best:
        return None
    return {"km": best}


def _wochenkoenig_fenster(
    session: Session, user_id: int, start: date_type, today: date_type
) -> dict | None:
    """Alleiniger Platz 1 der gewerteten km (Kategorie-Faktor × km_factor, wie
    Rennen-Tab) an 7 aufeinanderfolgenden Kalendertagen ab Challenge-Start.
    Geprüft gegen den aktuellen Datenstand (Spec: Randfälle)."""
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    if user_id not in users:
        return None
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    tages_km: dict[date_type, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    acts = session.exec(
        select(Activity).where(Activity.date >= start, Activity.date <= today)
    ).all()
    for act in acts:
        cat, u = cats.get(act.category_id), users.get(act.user_id)
        if cat is None or u is None:
            continue
        tages_km[act.date][act.user_id] += act.distance_km * cat.factor * u.km_factor
    kum: dict[int, float] = defaultdict(float)
    streak = 0
    d = start
    while d <= today:
        for uid, km in tages_km.get(d, {}).items():
            kum[uid] += km
        stand = {uid: round(km, 2) for uid, km in kum.items() if km > 0}
        best = max(stand.values(), default=0.0)
        fuehrende = [uid for uid, km in stand.items() if km == best]
        streak = streak + 1 if fuehrende == [user_id] else 0
        if streak >= 7:
            return {"von": (d - timedelta(days=6)).isoformat(), "bis": d.isoformat()}
        d += timedelta(days=1)
    return None
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/achievements.py backend/tests/test_achievement_unlocks.py
git commit -m "feat(achievements): Wochenkönig und Testphasen-Sieger"
```

---

### Task 6: Router — erweiterte `GET /api/achievements` + `PATCH /{key}`

**Files:**
- Modify: `backend/app/routers/achievements.py`
- Test: `backend/tests/test_achievements.py`

- [ ] **Step 1: Failing Tests schreiben**

Anhängen an `backend/tests/test_achievements.py`:

```python
def test_neue_achievements_in_liste_und_maskierung(client, session):
    make_user(session)
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    # Stufen mit tier/discipline
    assert a["stufe_rad_gold"]["tier"] == "gold"
    assert a["stufe_rad_gold"]["discipline"] == "rad"
    assert a["stufe_rad_gold"]["achieved"] is False
    # Hidden maskiert: Titel ???, keine Parts, kein Fortschritt
    assert a["kletterkoenig"]["hidden"] is True
    assert a["kletterkoenig"]["title"] == "???"
    assert a["kletterkoenig"]["parts"] == []
    assert a["kletterkoenig"]["progress"] == 0.0
    # Einmal-Achievements vorhanden, noch unvergeben
    assert a["erster_gold_rad"]["claimed_by"] is None
    assert a["erster_gold_rad"]["emoji"] == "🚴"
    assert a["testphasen_sieger"]["achieved"] is False
    # Bestands-Achievements unverändert dabei
    assert "ironman" in a


def test_hidden_wird_nach_unlock_aufgedeckt(client, session):
    from app.models import Activity

    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad")
    session.add(Activity(user_id=user.id, category_id=rad.id,
                         date=date(2026, 8, 1), distance_km=30.0, elevation_m=1200.0))
    session.commit()
    login(client)
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["kletterkoenig"]["achieved"] is True
    assert a["kletterkoenig"]["title"] == "Kletterkönig"
    assert a["kletterkoenig"]["emoji"] == "🏔️"
    assert a["kletterkoenig"]["showcased"] is True
    assert a["kletterkoenig"]["unlocked_at"] is not None


def test_claimed_by_zeigt_namen_der_anderen_person(client, session):
    from app.models import Activity
    from app.services.achievements import check_unlocks

    make_user(session)
    lisa = make_user(session, username="lisa")
    rad = make_category(session, name="Radfahren", icon="rad")
    session.add(Activity(user_id=lisa.id, category_id=rad.id,
                         date=date(2026, 8, 1), distance_km=4000.0))
    session.commit()
    check_unlocks(session, lisa.id)
    login(client)  # als erik
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["erster_gold_rad"]["achieved"] is False
    assert a["erster_gold_rad"]["claimed_by"] == "Lisa"


def test_showcase_toggle(client, session):
    from app.models import Activity

    user = make_user(session)
    rad = make_category(session, name="Radfahren", icon="rad")
    session.add(Activity(user_id=user.id, category_id=rad.id,
                         date=date(2026, 8, 1), distance_km=30.0, elevation_m=1200.0))
    session.commit()
    login(client)
    client.get("/api/achievements")  # löst check_unlocks aus
    r = client.patch("/api/achievements/kletterkoenig", json={"showcased": False})
    assert r.status_code == 200
    assert r.json() == {"key": "kletterkoenig", "showcased": False}
    a = {x["key"]: x for x in client.get("/api/achievements").json()}
    assert a["kletterkoenig"]["showcased"] is False
    # fremder/fehlender Unlock → 404
    assert client.patch("/api/achievements/wochenkoenig",
                        json={"showcased": False}).status_code == 404
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `cd backend && python -m pytest tests/test_achievements.py -q`
Expected: neue Tests FAIL (KeyError `stufe_rad_gold`), Bestand PASS

- [ ] **Step 3: Router implementieren**

In `backend/app/routers/achievements.py`:

Imports oben ergänzen/anpassen:

```python
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..models import AchievementUnlock
from ..services.achievements import (
    DISZIPLIN_ICON,
    DISZIPLIN_LABEL,
    EINMAL_DEFS,
    EMOJIS,
    HIDDEN_DEFS,
    LAUF,
    RAD,
    SCHWIMM,
    STUFEN_ZIELE,
    TIERS,
    bucket_for_category,
    check_unlocks,
    stufen_key,
)
```

`AchievementOut` erweitern:

```python
class AchievementOut(BaseModel):
    key: str
    title: str
    description: str
    icon: str
    achieved: bool
    progress: float  # 0..1, min über alle Teile
    parts: list[Part]
    hidden: bool = False
    tier: str | None = None  # "bronze" | "silber" | "gold"
    discipline: str | None = None
    unlocked_at: datetime | None = None
    emoji: str | None = None
    showcased: bool | None = None  # nur beim eigenen Emoji-Unlock gesetzt
    claimed_by: str | None = None  # Einmal-Achievements: wer es schon hat
```

Den `achievements`-Endpoint ersetzen durch:

```python
@router.get("", response_model=list[AchievementOut])
def achievements(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    # „Platz 1 gehalten"/Testphasen-Sieg können ohne eigene Aktivität eintreten —
    # deshalb wird beim Abruf für die anfragende Person geprüft (Spec §2.2).
    check_unlocks(session, user.id)

    cats = {c.id: c for c in session.exec(select(Category)).all()}
    sums: dict[str, float] = defaultdict(float)
    for act in session.exec(select(Activity).where(Activity.user_id == user.id)).all():
        sums["gesamt"] += act.distance_km
        cat = cats.get(act.category_id)
        bucket = bucket_for_category(cat) if cat else None
        if bucket is not None:
            sums[bucket] += act.distance_km

    own = {
        u.key: u
        for u in session.exec(
            select(AchievementUnlock).where(AchievementUnlock.user_id == user.id)
        ).all()
    }
    einmal_keys = [key for key, *_ in EINMAL_DEFS]
    inhaber: dict[str, str] = {}
    rows = session.exec(
        select(AchievementUnlock, User)
        .join(User, AchievementUnlock.user_id == User.id)
        .where(AchievementUnlock.key.in_(einmal_keys))
        .order_by(AchievementUnlock.unlocked_at)
    ).all()
    for ul, u in rows:
        inhaber.setdefault(ul.key, u.display_name)

    _LABELS = {RAD: "Rad", LAUF: "Laufen", SCHWIMM: "Schwimmen", "gesamt": "Gesamt"}
    out = []
    for key, title, description, icon, targets in DEFINITIONS:
        parts = [
            Part(
                label=_LABELS[bucket],
                current_km=round(min(sums[bucket], target), 2),
                target_km=target,
            )
            for bucket, target in targets.items()
        ]
        progress = min(p.current_km / p.target_km for p in parts)
        out.append(
            AchievementOut(
                key=key,
                title=title,
                description=description,
                icon=icon,
                achieved=progress >= 1.0,
                progress=round(min(progress, 1.0), 4),
                parts=parts,
            )
        )

    # Stufen: 9 Einträge, Frontend gruppiert über tier/discipline
    for bucket in (RAD, LAUF, SCHWIMM):
        for tier in TIERS:
            key = stufen_key(bucket, tier)
            ziel = STUFEN_ZIELE[bucket][tier]
            ul = own.get(key)
            out.append(
                AchievementOut(
                    key=key,
                    title=f"{DISZIPLIN_LABEL[bucket]} {tier.capitalize()}",
                    description=f"{int(ziel)} km {DISZIPLIN_LABEL[bucket]} insgesamt.",
                    icon=DISZIPLIN_ICON[bucket],
                    achieved=ul is not None or sums[bucket] >= ziel,
                    progress=round(min(sums[bucket] / ziel, 1.0), 4),
                    parts=[Part(
                        label=DISZIPLIN_LABEL[bucket],
                        current_km=round(min(sums[bucket], ziel), 2),
                        target_km=ziel,
                    )],
                    tier=tier,
                    discipline=bucket,
                    unlocked_at=ul.unlocked_at if ul else None,
                )
            )

    # Einmal-Achievements: Erster-Bonus + Testphasen-Sieger
    for key, title, description, icon in EINMAL_DEFS:
        ul = own.get(key)
        out.append(
            AchievementOut(
                key=key,
                title=title,
                description=description,
                icon=icon,
                achieved=ul is not None,
                progress=1.0 if ul else 0.0,
                parts=[],
                unlocked_at=ul.unlocked_at if ul else None,
                emoji=EMOJIS.get(key),
                showcased=ul.showcased if ul else None,
                claimed_by=inhaber.get(key),
            )
        )

    # Hidden: maskiert, solange nicht freigeschaltet (Spec §2.4)
    for key, title, description, icon in HIDDEN_DEFS:
        ul = own.get(key)
        if ul is None:
            out.append(AchievementOut(
                key=key, title="???", description="", icon="medaille",
                achieved=False, progress=0.0, parts=[], hidden=True,
            ))
        else:
            out.append(AchievementOut(
                key=key, title=title, description=description, icon=icon,
                achieved=True, progress=1.0, parts=[], hidden=True,
                unlocked_at=ul.unlocked_at, emoji=EMOJIS.get(key),
                showcased=ul.showcased,
            ))
    return out
```

Darunter den Showcase-Endpoint ergänzen:

```python
class ShowcasePatch(BaseModel):
    showcased: bool


@router.patch("/{key}")
def patch_showcase(
    key: str,
    data: ShowcasePatch,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ul = session.exec(
        select(AchievementUnlock).where(
            AchievementUnlock.user_id == user.id, AchievementUnlock.key == key
        )
    ).first()
    if ul is None:
        raise HTTPException(status_code=404)
    ul.showcased = data.showcased
    session.add(ul)
    session.commit()
    return {"key": key, "showcased": ul.showcased}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_achievements.py tests/test_achievement_unlocks.py -q`
Expected: alle PASS. Achtung: `test_achievements_empty_user_nothing_achieved` prüft die Key-Menge — dieser Bestandstest muss um die neuen Keys erweitert werden:

```python
    assert {a["key"] for a in body} == {
        "startschuss", "marathon", "aermelkanal", "transalp", "ironman", "tausender",
        "stufe_rad_bronze", "stufe_rad_silber", "stufe_rad_gold",
        "stufe_lauf_bronze", "stufe_lauf_silber", "stufe_lauf_gold",
        "stufe_schwimm_bronze", "stufe_schwimm_silber", "stufe_schwimm_gold",
        "erster_gold_rad", "erster_gold_lauf", "erster_gold_schwimm",
        "testphasen_sieger", "kletterkoenig", "hattrick", "wochenkoenig",
    }
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/achievements.py backend/tests/test_achievements.py
git commit -m "feat(achievements): erweiterte API mit Stufen, Hidden, claimed_by und Showcase-Toggle"
```

---

### Task 7: Hooks — Aktivitäts-Endpoints, Strava-Import, Comparison-Emojis

**Files:**
- Modify: `backend/app/routers/activities.py` (create + patch)
- Modify: `backend/app/services/strava.py` (`import_activity`)
- Modify: `backend/app/routers/comparison.py` + `backend/app/schemas.py` (`ComparisonUser.emojis`)
- Test: `backend/tests/test_achievement_unlocks.py`, `backend/tests/test_comparison.py`

- [ ] **Step 1: Failing Tests schreiben**

Anhängen an `backend/tests/test_achievement_unlocks.py`:

```python
def test_activity_create_loest_unlock_aus(client, session):
    from tests.conftest import login

    make_user(session)
    lauf = make_category(session, name="Laufen", icon="laufen")
    login(client)
    r = client.post("/api/activities", json={
        "category_id": lauf.id, "date": "2026-08-01", "distance_km": 250.0,
    })
    assert r.status_code == 201
    unlocks = session.exec(select(AchievementUnlock)).all()
    assert {u.key for u in unlocks} == {"stufe_lauf_bronze"}


def test_strava_import_loest_unlock_aus(session):
    from app.models import StravaConnection
    from app.services import strava

    user = make_user(session)
    make_category(session, name="Laufen", icon="laufen", strava_sport_types='["Run"]')
    conn = StravaConnection(user_id=user.id, athlete_id=9, access_token="a",
                            refresh_token="r", expires_at=9999999999)
    session.add(conn)
    session.commit()
    data = {"id": 500, "sport_type": "Run", "distance": 250000.0,
            "start_date_local": "2026-08-01T07:00:00Z", "name": "Ultra"}
    assert strava.import_activity(session, conn, data) is True
    assert "stufe_lauf_bronze" in keys_of(session, user)
```

Anhängen an `backend/tests/test_comparison.py` (Imports/Helpers der Datei nutzen — dort existieren `make_user`/`make_category`-Muster, ggf. anpassen):

```python
def test_comparison_liefert_showcased_emojis(client, session):
    from datetime import date

    from app.models import AchievementUnlock, Season
    from tests.conftest import login, make_user

    user = make_user(session)
    session.add(Season(year=date.today().year, goal_km=1000.0, milestones_json="[]"))
    session.add(AchievementUnlock(user_id=user.id, key="kletterkoenig"))
    session.add(AchievementUnlock(user_id=user.id, key="wochenkoenig", showcased=False))
    session.add(AchievementUnlock(user_id=user.id, key="stufe_rad_gold"))  # kein Emoji
    session.commit()
    login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    me = next(u for u in r.json()["users"] if u["user_id"] == user.id)
    assert me["emojis"] == ["🏔️"]  # nur showcased UND mit Emoji
```

- [ ] **Step 2: Tests laufen lassen — müssen scheitern**

Run: `cd backend && python -m pytest tests/test_achievement_unlocks.py tests/test_comparison.py -q`
Expected: neue Tests FAIL

- [ ] **Step 3: Implementieren**

`backend/app/routers/activities.py` — Import ergänzen:

```python
from ..services.achievements import check_unlocks
```

In `create_activity` nach `session.refresh(act)`:

```python
    check_unlocks(session, user.id)
```

In `patch_activity` nach `session.refresh(act)` (vor `cat = session.get(...)`):

```python
    check_unlocks(session, user.id)
```

`backend/app/services/strava.py` — in `import_activity` direkt nach `session.commit()` (vor `return True`):

```python
    from .achievements import check_unlocks

    check_unlocks(session, conn.user_id)
```

(Import in der Funktion, damit Modul-Ladereihenfolge unkritisch bleibt; Webhook und Backfill laufen beide hier durch.)

`backend/app/schemas.py` — `ComparisonUser` ergänzen (nach `km_factor`):

```python
    emojis: list[str] = []
```

`backend/app/routers/comparison.py` — Imports ergänzen:

```python
from ..models import AchievementUnlock
from ..services.achievements import EMOJIS
```

In `compute_comparison` vor der `for user in users:`-Schleife:

```python
    emoji_rows = session.exec(
        select(AchievementUnlock).where(AchievementUnlock.showcased == True)  # noqa: E712
    ).all()
    emojis_by_user: dict[int, list[str]] = defaultdict(list)
    for ul in emoji_rows:
        emoji = EMOJIS.get(ul.key)
        if emoji:
            emojis_by_user[ul.user_id].append(emoji)
```

Und im `ComparisonUser(...)`-Konstruktor (nach `km_factor=user.km_factor,`):

```python
                emojis=emojis_by_user.get(user.id, []),
```

- [ ] **Step 4: Volle Backend-Suite laufen lassen**

Run: `cd backend && python -m pytest -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/activities.py backend/app/services/strava.py backend/app/routers/comparison.py backend/app/schemas.py backend/tests/test_achievement_unlocks.py backend/tests/test_comparison.py
git commit -m "feat(achievements): Unlock-Hooks + showcased-Emojis im Comparison"
```

---

### Task 8: Frontend — Types + Achievements-UI (Stufen-Karten, Einmal, Hidden, Toggle)

**Files:**
- Modify: `frontend/src/api/client.ts` (Achievement-Typ ~127, `patchAchievement`, `ComparisonUser` ~55)
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx` (Achievements-Bereich ab ~179)
- Test: `frontend/src/pages/MeineAktivitaeten.test.tsx`

- [ ] **Step 1: Types + API-Client erweitern**

`client.ts` — Typ `Achievement` ersetzen durch:

```ts
export type Achievement = {
  key: string
  title: string
  description: string
  icon: string
  achieved: boolean
  progress: number
  parts: AchievementPart[]
  hidden: boolean
  tier: 'bronze' | 'silber' | 'gold' | null
  discipline: string | null
  unlocked_at: string | null
  emoji: string | null
  showcased: boolean | null
  claimed_by: string | null
}
```

`ComparisonUser` ergänzen (optional, damit Bestands-Mocks weiterbauen):

```ts
  emojis?: string[]
```

Im `api`-Objekt nach `achievements: ...`:

```ts
  patchAchievement: (key: string, showcased: boolean) =>
    request<{ key: string; showcased: boolean }>(`/api/achievements/${key}`, patch({ showcased })),
```

- [ ] **Step 2: Failing UI-Test schreiben**

In `frontend/src/pages/MeineAktivitaeten.test.tsx` den `achievements`-Mock um neue Felder und Fälle erweitern. Bestehende Mock-Objekte bekommen `hidden: false, tier: null, discipline: null, unlocked_at: null, emoji: null, showcased: null, claimed_by: null` ergänzt; zusätzliche Einträge in die gemockte Liste:

```tsx
      { key: 'stufe_rad_bronze', title: 'Rad Bronze', description: '1000 km Rad insgesamt.', icon: 'rad',
        achieved: true, progress: 1, parts: [{ label: 'Rad', current_km: 1000, target_km: 1000 }],
        hidden: false, tier: 'bronze', discipline: 'rad', unlocked_at: '2026-08-01T10:00:00Z', emoji: null, showcased: null, claimed_by: null },
      { key: 'stufe_rad_silber', title: 'Rad Silber', description: '2500 km Rad insgesamt.', icon: 'rad',
        achieved: false, progress: 0.5, parts: [{ label: 'Rad', current_km: 1250, target_km: 2500 }],
        hidden: false, tier: 'silber', discipline: 'rad', unlocked_at: null, emoji: null, showcased: null, claimed_by: null },
      { key: 'stufe_rad_gold', title: 'Rad Gold', description: '4000 km Rad insgesamt.', icon: 'rad',
        achieved: false, progress: 0.3125, parts: [{ label: 'Rad', current_km: 1250, target_km: 4000 }],
        hidden: false, tier: 'gold', discipline: 'rad', unlocked_at: null, emoji: null, showcased: null, claimed_by: null },
      { key: 'erster_gold_rad', title: 'Erster: Rad Gold', description: 'Bekommt nur, wer die Gold-Stufe Rad als erste Person knackt.', icon: 'rad',
        achieved: false, progress: 0, parts: [], hidden: false, tier: null, discipline: null,
        unlocked_at: null, emoji: '🚴', showcased: null, claimed_by: 'Lisa' },
      { key: 'kletterkoenig', title: '???', description: '', icon: 'medaille',
        achieved: false, progress: 0, parts: [], hidden: true, tier: null, discipline: null,
        unlocked_at: null, emoji: null, showcased: null, claimed_by: null },
      { key: 'hattrick', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.', icon: 'blitz',
        achieved: true, progress: 1, parts: [], hidden: true, tier: null, discipline: null,
        unlocked_at: '2026-08-02T10:00:00Z', emoji: '🎩', showcased: true, claimed_by: null },
```

Neue Tests anhängen (describe-Block der Datei nutzen):

```tsx
  it('gruppiert Stufen zu einer Karte pro Disziplin mit Badges', async () => {
    render(<Wrapper />)
    expect(await screen.findByText('Rad')).toBeInTheDocument()
    expect(screen.getByText('Bronze')).toBeInTheDocument()
    expect(screen.getByText('Silber')).toBeInTheDocument()
    expect(screen.getByText('Gold')).toBeInTheDocument()
    // es gibt KEINE drei einzelnen Stufen-Karten
    expect(screen.queryByText('Rad Silber')).not.toBeInTheDocument()
  })

  it('zeigt vergebene Einmal-Achievements mit Namen', async () => {
    render(<Wrapper />)
    expect(await screen.findByText(/vergeben an Lisa/)).toBeInTheDocument()
  })

  it('zeigt nicht freigeschaltete Hidden als ???-Karte und freigeschaltete voll', async () => {
    render(<Wrapper />)
    expect(await screen.findByText('???')).toBeInTheDocument()
    expect(screen.getByText('Hattrick')).toBeInTheDocument()
    expect(screen.getByText('🎩')).toBeInTheDocument()
  })
```

(`Wrapper` = das Render-Muster, das die Datei bereits für `MeineAktivitaeten` nutzt — bestehende Hilfsfunktion wiederverwenden.)

- [ ] **Step 3: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- MeineAktivitaeten`
Expected: neue Tests FAIL

- [ ] **Step 4: UI implementieren**

In `frontend/src/pages/MeineAktivitaeten.tsx` die Funktionen `Achievements` und `AchievementBadge` ersetzen/ergänzen:

```tsx
const TIER_REIHE = ['bronze', 'silber', 'gold'] as const
const TIER_LABEL = { bronze: 'Bronze', silber: 'Silber', gold: 'Gold' } as const

function Achievements() {
  const queryClient = useQueryClient()
  const { data: achievements = [] } = useQuery({
    queryKey: ['achievements'],
    queryFn: api.achievements,
  })
  const toggle = useMutation({
    mutationFn: ({ key, showcased }: { key: string; showcased: boolean }) =>
      api.patchAchievement(key, showcased),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['achievements'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
  })
  if (achievements.length === 0) return null

  const stufen = achievements.filter((a) => a.tier !== null)
  const disziplinen = [...new Set(stufen.map((a) => a.discipline))] as string[]
  const einmal = achievements.filter((a) => a.emoji !== null && !a.hidden && a.tier === null)
  const hidden = achievements.filter((a) => a.hidden)
  const klassisch = achievements.filter(
    (a) => a.tier === null && !a.hidden && a.emoji === null,
  )

  const onToggle = (a: Achievement) =>
    toggle.mutate({ key: a.key, showcased: !(a.showcased ?? true) })

  return (
    <div>
      <h2 className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
        Achievements
      </h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {klassisch.map((a) => (
          <AchievementBadge key={a.key} a={a} />
        ))}
        {disziplinen.map((d) => (
          <StufenKarte
            key={d}
            stufen={TIER_REIHE.map(
              (t) => stufen.find((s) => s.discipline === d && s.tier === t)!,
            ).filter(Boolean)}
          />
        ))}
        {einmal.map((a) => (
          <EinmalKarte key={a.key} a={a} onToggle={onToggle} />
        ))}
        {hidden.map((a) => (
          <HiddenKarte key={a.key} a={a} onToggle={onToggle} />
        ))}
      </div>
    </div>
  )
}

function EmojiToggle({ a, onToggle }: { a: Achievement; onToggle: (a: Achievement) => void }) {
  if (!a.achieved || !a.emoji) return null
  const an = a.showcased ?? true
  return (
    <button
      type="button"
      onClick={() => onToggle(a)}
      className={`mt-2 flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
        an ? 'border-accent text-accent' : 'border-line text-ink-mute'
      }`}
      title="Emoji neben deinem Namen anzeigen"
    >
      <span className="text-sm">{a.emoji}</span>
      {an ? 'wird getragen' : 'abgelegt'}
    </button>
  )
}

function StufenKarte({ stufen }: { stufen: Achievement[] }) {
  const label = stufen[0]?.parts[0]?.label ?? ''
  const naechste = stufen.find((s) => !s.achieved)
  return (
    <div
      className={`rounded-xl border p-3 ${
        stufen.some((s) => s.achieved) ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon name={stufen[0].icon} size={20} className="text-accent" />
        <span className="text-sm font-bold text-ink">{label}</span>
      </div>
      <div className="mt-2 flex gap-1.5">
        {stufen.map((s) => (
          <span
            key={s.key}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
              s.achieved
                ? s.tier === 'gold'
                  ? 'border-amber-400 text-amber-400'
                  : s.tier === 'silber'
                    ? 'border-slate-300 text-slate-300'
                    : 'border-amber-700 text-amber-700'
                : 'border-line/40 text-ink-mute'
            }`}
          >
            {TIER_LABEL[s.tier as keyof typeof TIER_LABEL]}
          </span>
        ))}
      </div>
      {naechste && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(naechste.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] tabular-nums text-ink-mute">
            {Math.round(naechste.parts[0]?.current_km ?? 0)}/
            {Math.round(naechste.parts[0]?.target_km ?? 0)} km bis{' '}
            {TIER_LABEL[naechste.tier as keyof typeof TIER_LABEL]}
          </p>
        </>
      )}
    </div>
  )
}

function EinmalKarte({ a, onToggle }: { a: Achievement; onToggle: (a: Achievement) => void }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        a.achieved ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className={`text-sm font-bold ${a.achieved ? 'text-accent' : 'text-ink'}`}>
          {a.title}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {!a.achieved && (
        <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-ink-mute">
          {a.claimed_by ? `vergeben an ${a.claimed_by}` : 'bekommt nur die erste Person'}
        </p>
      )}
      <EmojiToggle a={a} onToggle={onToggle} />
    </div>
  )
}

function HiddenKarte({ a, onToggle }: { a: Achievement; onToggle: (a: Achievement) => void }) {
  if (!a.achieved) {
    return (
      <div className="rounded-xl border border-line/40 p-3 opacity-60">
        <div className="flex items-center gap-2">
          <Icon name="medaille" size={20} className="text-ink-mute" />
          <span className="text-sm font-bold text-ink">???</span>
        </div>
        <p className="mt-1 text-xs text-ink-mute">Verstecktes Achievement.</p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-accent p-3 shadow-glow">
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className="text-sm font-bold text-accent">{a.title}</span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {a.unlocked_at && (
        <p className="mt-1 font-mono text-[10px] text-ink-mute">
          freigeschaltet am {new Date(a.unlocked_at).toLocaleDateString('de-DE')}
        </p>
      )}
      <EmojiToggle a={a} onToggle={onToggle} />
    </div>
  )
}
```

Hinweis: `AchievementBadge` bleibt unverändert für die klassischen Achievements bestehen.

- [ ] **Step 5: Tests + Lint laufen lassen**

Run: `cd frontend && npm run test -- MeineAktivitaeten && npm run lint`
Expected: alle PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/MeineAktivitaeten.tsx frontend/src/pages/MeineAktivitaeten.test.tsx
git commit -m "feat(frontend): Achievements-UI mit Stufen-Karten, Einmal-Karten, Hidden und Emoji-Toggle"
```

---

### Task 9: Frontend — Emojis im Leaderboard (RaceBahnen)

**Files:**
- Modify: `frontend/src/components/comparison/RaceBahnen.tsx` (Namenszeile ~97)
- Test: `frontend/src/components/comparison/RaceBahnen.test.tsx`

- [ ] **Step 1: Failing Test schreiben**

In `RaceBahnen.test.tsx` beim gemockten Comparison-User `emojis: ['👑', '🎩']` ergänzen und Test anhängen (Render-Muster der Datei wiederverwenden):

```tsx
  it('zeigt Special-Emojis neben dem Namen', async () => {
    renderRaceBahnen()  // bestehende Render-Hilfsfunktion der Datei
    expect(await screen.findByText('👑 🎩')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- RaceBahnen`
Expected: FAIL

- [ ] **Step 3: Implementieren**

In `RaceBahnen.tsx` in der Namenszeile — innerhalb von `<p className="truncate text-sm font-bold text-ink">` nach `{u.display_name}`:

```tsx
                    {(u.emojis ?? []).length > 0 && (
                      <span className="ml-1.5 text-xs" title="Erspielte Auszeichnungen">
                        {(u.emojis ?? []).join(' ')}
                      </span>
                    )}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd frontend && npm run test -- RaceBahnen`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/RaceBahnen.tsx frontend/src/components/comparison/RaceBahnen.test.tsx
git commit -m "feat(vergleich): Special-Emojis neben dem Namen im Leaderboard"
```

---

### Task 10: Frontend — Emojis im Blackboard

**Files:**
- Modify: `frontend/src/components/bets/BetCard.tsx` (Typ `Spieler`, ~Zeile 38)
- Modify: `frontend/src/pages/Wetten.tsx` (`spieler`-Mapping)
- Modify: `frontend/src/components/bets/Blackboard.tsx` (Namensanzeige)
- Test: `frontend/src/components/bets/Blackboard.test.tsx`

- [ ] **Step 1: Failing Test schreiben**

In `Blackboard.test.tsx` das `spieler`-Array erweitern:

```tsx
const spieler = [
  { user_id: 1, display_name: 'Erik', emojis: ['👑'] },
  { user_id: 2, display_name: 'Lisa' },
]
```

Test anhängen:

```tsx
  it('zeigt Special-Emojis hinter dem Namen', () => {
    render(<Blackboard bets={bets} spieler={spieler} />)
    expect(screen.getByText('Erik 👑 ⚔️ Lisa')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- Blackboard`
Expected: FAIL

- [ ] **Step 3: Implementieren**

`BetCard.tsx` — Typ erweitern:

```tsx
export type Spieler = { user_id: number; display_name: string; emojis?: string[] }
```

`Wetten.tsx` — das `spieler`-Mapping erweitern:

```tsx
  const spieler: Spieler[] =
    vergleich?.users.map((u) => ({
      user_id: u.user_id,
      display_name: u.display_name,
      emojis: u.emojis ?? [],
    })) ?? []
```

`Blackboard.tsx` — die `name`-Hilfsfunktion ersetzen:

```tsx
  const name = (id: number | undefined) => {
    const s = spieler.find((sp) => sp.user_id === id)
    if (!s) return `#${id}`
    const emojis = s.emojis ?? []
    return emojis.length > 0 ? `${s.display_name} ${emojis.join(' ')}` : s.display_name
  }
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd frontend && npm run test -- Blackboard Wetten`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/bets/BetCard.tsx frontend/src/pages/Wetten.tsx frontend/src/components/bets/Blackboard.tsx frontend/src/components/bets/Blackboard.test.tsx
git commit -m "feat(wetten): Special-Emojis im Blackboard"
```

---

### Task 11: Frontend — Avatar-Reiter „Erspielt"

**Files:**
- Modify: `frontend/src/components/ui/AvatarWahl.tsx`
- Modify: `frontend/src/components/ui/ProfilModal.tsx` (Achievements-Query + Prop)
- Test: `frontend/src/components/ui/AvatarWahl.test.tsx`

`User.avatar` ist im Backend ein freies String-Feld — keine Backend-Änderung nötig.

- [ ] **Step 1: Failing Test schreiben**

Anhängen an `AvatarWahl.test.tsx` (Render-Muster der Datei wiederverwenden):

```tsx
  it('zeigt Reiter Erspielt nur mit erspielten Emojis und wählt daraus', async () => {
    const onChange = vi.fn()
    render(<AvatarWahl value="🦊" onChange={onChange} erspielt={['👑']} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Erspielt' }))
    await userEvent.click(screen.getByRole('button', { name: '👑' }))
    expect(onChange).toHaveBeenCalledWith('👑')
  })

  it('versteckt Reiter Erspielt ohne erspielte Emojis', () => {
    render(<AvatarWahl value="🦊" onChange={vi.fn()} />)
    expect(screen.queryByRole('tab', { name: 'Erspielt' })).not.toBeInTheDocument()
  })
```

Falls die Emoji-Buttons der Datei bisher keinen accessible name haben: im Implementierungs-Schritt `aria-label={e}` auf die Emoji-Buttons setzen (bestehende und neue), dann funktioniert `getByRole('button', { name: '👑' })`.

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- AvatarWahl`
Expected: FAIL (Prop/Reiter existiert nicht)

- [ ] **Step 3: Implementieren**

`AvatarWahl.tsx` ersetzen durch:

```tsx
import { useState } from 'react'
import IconPicker from './IconPicker'
import { AVATAR_EMOJIS, AVATAR_PIKTOS } from './icons'

type Props = { value: string; onChange: (v: string) => void; erspielt?: string[] }

const tab = (aktiv: boolean) =>
  `rounded-full px-3 py-1 text-xs font-bold ${
    aktiv ? 'border border-accent text-accent' : 'text-ink-mute'
  }`

function EmojiGrid({
  emojis,
  value,
  onChange,
}: {
  emojis: string[]
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-1">
      {emojis.map((e) => (
        <button
          key={e}
          type="button"
          aria-label={e}
          onClick={() => onChange(e)}
          className={`flex h-9 w-9 items-center justify-center rounded-xl border text-lg ${
            value === e ? 'border-accent shadow-glow' : 'border-line'
          }`}
        >
          {e}
        </button>
      ))}
    </div>
  )
}

export default function AvatarWahl({ value, onChange, erspielt = [] }: Props) {
  const [modus, setModus] = useState<'emoji' | 'pikto' | 'erspielt'>(
    erspielt.includes(value) ? 'erspielt' : value.startsWith('icon:') ? 'pikto' : 'emoji',
  )
  return (
    <div className="space-y-2">
      <div role="tablist" className="flex gap-1">
        <button type="button" role="tab" className={tab(modus === 'emoji')} onClick={() => setModus('emoji')}>
          Emojis
        </button>
        <button type="button" role="tab" className={tab(modus === 'pikto')} onClick={() => setModus('pikto')}>
          Piktogramme
        </button>
        {erspielt.length > 0 && (
          <button type="button" role="tab" className={tab(modus === 'erspielt')} onClick={() => setModus('erspielt')}>
            Erspielt
          </button>
        )}
      </div>
      {modus === 'emoji' && <EmojiGrid emojis={AVATAR_EMOJIS} value={value} onChange={onChange} />}
      {modus === 'erspielt' && <EmojiGrid emojis={erspielt} value={value} onChange={onChange} />}
      {modus === 'pikto' && (
        <IconPicker
          auswahl={AVATAR_PIKTOS}
          value={value.replace('icon:', '')}
          onChange={(name) => onChange(`icon:${name}`)}
        />
      )}
    </div>
  )
}
```

`ProfilModal.tsx` — Achievements-Query ergänzen (bei den anderen Queries):

```tsx
  const { data: achievements = [] } = useQuery({
    queryKey: ['achievements'],
    queryFn: api.achievements,
  })
  const erspielt = achievements
    .filter((a) => a.achieved && a.emoji)
    .map((a) => a.emoji as string)
```

und die `AvatarWahl`-Zeile ersetzen:

```tsx
          <AvatarWahl value={avatar} onChange={setAvatar} erspielt={erspielt} />
```

Prüfen: `ProfilModal.test.tsx` mockt `api` — dort `achievements: vi.fn().mockResolvedValue([])` ergänzen, falls der Mock sonst `undefined` liefert.

- [ ] **Step 4: Tests + Lint + Build laufen lassen**

Run: `cd frontend && npm run test && npm run lint && npm run build`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/AvatarWahl.tsx frontend/src/components/ui/AvatarWahl.test.tsx frontend/src/components/ui/ProfilModal.tsx frontend/src/components/ui/ProfilModal.test.tsx
git commit -m "feat(profil): erspielte Special-Emojis als Avatar wählbar"
```

---

### Task 12: Gesamtverifikation + PR

- [ ] **Step 1: Volle Test-Suiten**

Run: `cd backend && python -m pytest -q`
Expected: alle PASS

Run: `cd frontend && npm run lint && npm run test && npm run build`
Expected: alle PASS

- [ ] **Step 2: End-to-End-Check (verify-Skill nutzen)**

Lokal starten und durchspielen: (1) Aktivität eintragen, die eine Stufe knackt → Stufen-Karte färbt Badge, Unlock überlebt Löschen der Aktivität; (2) Hidden testen (3 Einträge an einem Tag → Hattrick erscheint mit Titel + Emoji, vorher „???"); (3) Emoji-Toggle aus → Emoji verschwindet im Vergleich-Leaderboard; (4) Profil → Avatar-Reiter „Erspielt" zeigt das Emoji und lässt sich setzen; (5) zweiter Test-User: Erster-Bonus-Karte zeigt „vergeben an {Name}".

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feature/achievements-ausbau
gh pr create --title "Achievements-Ausbau: Stufen, Hidden, Testphasen-Sieger, Special-Emojis" --body "Implementiert Spec §2 (docs/superpowers/specs/2026-07-16-...). Persistierte Unlocks (AchievementUnlock), check_unlocks-Service, erweiterte Achievements-API mit Showcase-Toggle, Emojis in Leaderboard/Blackboard/Avatar.

Review-Fokus: Emoji-Zuordnung (Spec §2.6, Vorschlag) und Wochenkönig-Logik."
```
