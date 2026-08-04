# Challenges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zeitlich begrenzte Wettbewerbe (Ziel- und Ranglisten-Modus) als eigener Tab, der die Wetten ablöst — inklusive Feed-Anbindung und Admin-Verwaltung.

**Architecture:** Zwei neue Tabellen (`Challenge`, `ChallengeParticipant`), ein Service `challenges.py` mit Metrik-Registry, der jeden Stand zur Lesezeit aus den Activities berechnet. Persistiert werden nur Beitritte und das am Folgetag um 06:00 deutscher Zeit eingefrorene Endergebnis. Statusübergänge laufen lazy in `resolve_due()` beim GET, kein Cron. Frontend: eigener Tab hinter dem Add-on `challenges`.

**Tech Stack:** FastAPI, SQLModel/SQLite (kein Alembic), pytest · React 19, TanStack Query, Tailwind, Vitest + Testing Library

**Spec:** `docs/superpowers/specs/2026-08-04-challenges-design.md`

**Testbefehle:**
- Backend: `cd backend && uv run pytest`
- Frontend: `cd frontend && npm test`

---

## Wichtige Konventionen dieses Codebase

Lies das, bevor du anfängst — es spart dir mehrere Fehlversuche:

- **Kein Alembic.** Neue Tabellen entstehen durch `SQLModel.metadata.create_all`. Nur Änderungen an *bestehenden* Tabellen brauchen einen Eintrag in `db.py:migrate()`. Dieses Feature legt ausschließlich neue Tabellen an — `migrate()` wird **nicht** angefasst.
- **Zeitzone:** Der Code nutzt durchgängig den festen Offset `_MESZ = timezone(timedelta(hours=2))` statt `zoneinfo`. Siehe `services/feed.py:29`. Übernimm das, weiche nicht ab.
- **MM** = `distance_km × Kategorie-Faktor`. Das Admin-Handicap `User.km_factor` gilt **nur** im Saison-Ranking und wird in Challenges bewusst nicht angewendet.
- **Test-Helfer** stehen in `backend/tests/conftest.py`: `make_user`, `login`, `make_category`, `make_addon`, Fixtures `session` und `client`.
- **Deutsch** in Kommentaren, Docstrings, Commit-Messages und UI-Texten. Commit-Messages ohne Umlaute (siehe git log).
- **Frontend-Tests** mocken `../api/client` komplett per `vi.mock`. Vorlage: `frontend/src/pages/Feed.test.tsx`.

---

## Dateistruktur

**Backend — neu:**

| Datei | Verantwortung |
| --- | --- |
| `backend/app/services/challenges.py` | Metriken, Stand/Rangliste, Streak-Abbruch, Lebenszyklus, Einfrieren |
| `backend/app/routers/challenges.py` | HTTP-Schicht: Schemas, Endpunkte, Validierung |
| `backend/tests/test_challenges_metrics.py` | Metriken + Streak-Abbruch |
| `backend/tests/test_challenges_lifecycle.py` | Statusübergänge, Einfrieren, Standings |
| `backend/tests/test_challenges_api.py` | Endpunkte, Rechte, Fehlercodes, Gating |

**Backend — geändert:** `models.py` (zwei Tabellen), `seed.py` (Add-on), `main.py` (Router), `services/feed.py` (drei Emitter), `services/achievements.py` + `routers/achievements.py` (Texte), `tests/test_feed.py`, `tests/test_seed.py`, `tests/test_models.py`

**Frontend — neu:**

| Datei | Verantwortung |
| --- | --- |
| `frontend/src/components/challenges/wertung.ts` | Reine Formatierhelfer (Wertungstext, Einheit, Fortschritt) |
| `frontend/src/components/challenges/wertung.test.ts` | Deren Tests |
| `frontend/src/components/challenges/ChallengeHeroCard.tsx` | Große Karte für laufende Challenges mit Teilnahme |
| `frontend/src/components/challenges/ChallengeInvite.tsx` | Einladungsblock für offene opt-in-Challenges |
| `frontend/src/components/challenges/ChallengeRow.tsx` | Kompakte Zeile (geplant/beendet) |
| `frontend/src/components/challenges/ChallengeDetail.tsx` | Detailansicht mit Teilnehmerliste |
| `frontend/src/components/admin/ChallengesAdmin.tsx` | Admin-Abschnitt |
| `frontend/src/pages/Challenges.tsx` | Übersichtsseite, vier Abschnitte |
| `frontend/src/pages/Challenges.test.tsx` | Seiten-Test |
| `frontend/src/components/challenges/ChallengeDetail.test.tsx` | Detail-Test |

`ChallengesAdmin.tsx` bekommt bewusst eine eigene Datei: `pages/Admin.tsx` hat bereits 709 Zeilen, ein weiterer Abschnitt inline würde sie unhandlich machen. `Admin.tsx` bekommt nur Import und `<ChallengesAdmin />`.

**Frontend — geändert:** `api/client.ts`, `App.tsx`, `components/ui/tabs.ts`, `components/feed/FeedItem.tsx`, `pages/Admin.tsx`, `pages/Regeln.tsx`, `pages/Datenschutz.tsx`, `components/ui/CountdownBanner.tsx`, `components/comparison/WarmupArchiv.tsx`, `components/ui/tabs.test.ts`, `pages/MeineAktivitaeten.test.tsx`

---

## Task 1: Datenmodell

**Files:**
- Modify: `backend/app/models.py` (ans Dateiende, nach `FeedSeen`)
- Test: `backend/tests/test_models.py`

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_models.py`:

```python
def test_challenge_defaults(session):
    from datetime import date

    from app.models import Challenge

    ch = Challenge(
        title="August bis Stuttgartlauf",
        creator_id=1,
        mode="ziel",
        target=300.0,
        metric="mm",
        join_mode="auto",
        period_start=date(2026, 8, 4),
        period_end=date(2026, 8, 31),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    assert ch.status == "geplant"
    assert ch.category_ids_json == "[]"
    assert ch.streak_min_mm == 5.0
    assert ch.top_n == 1
    assert ch.result_json == "{}"
    assert ch.prize is None
    assert ch.resolved_at is None


def test_challenge_participant_unique(session):
    from datetime import date

    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models import Challenge, ChallengeParticipant

    ch = Challenge(
        title="X", creator_id=1, mode="ziel", target=1.0, metric="mm",
        join_mode="opt_in", period_start=date(2026, 8, 1), period_end=date(2026, 8, 2),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=7))
    session.commit()
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=7))
    with pytest.raises(IntegrityError):
        session.commit()
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_models.py -k challenge -v`
Expected: FAIL — `ImportError: cannot import name 'Challenge' from 'app.models'`

- [x] **Step 3: Write minimal implementation**

Ans Ende von `backend/app/models.py`:

```python
class Challenge(SQLModel, table=True):
    """Zeitlich begrenzter Wettbewerb (Spec 2026-08-04). Der Stand wird zur
    Lesezeit aus den Activities gerechnet; persistiert wird nur das am Ende
    eingefrorene Ergebnis in result_json."""

    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    creator_id: int = Field(foreign_key="user.id", index=True)
    prize: str | None = None  # freier Text, optional

    mode: str  # "ziel" | "rangliste"
    target: float | None = None  # mode="ziel": Schwelle
    top_n: int = 1  # mode="rangliste": gewertete Plaetze

    metric: str  # "mm" | "streak" | "anzahl"
    category_ids_json: str = "[]"  # leer = alle Kategorien
    streak_min_mm: float = 5.0  # nur metric="streak"

    join_mode: str  # "auto" | "opt_in"
    period_start: date_type
    period_end: date_type

    status: str = "geplant"  # "geplant" | "laufend" | "beendet" | "abgebrochen"
    result_json: str = "{}"  # bei Abschluss eingefroren
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


class ChallengeParticipant(SQLModel, table=True):
    """Nur fuer join_mode='opt_in'. Bei 'auto' sind alle aktiven User dabei,
    ohne dass Zeilen entstehen."""

    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_user"),
    )

    id: int | None = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    joined_at: datetime = Field(default_factory=utcnow)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: PASS (alle Tests der Datei)

- [x] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(challenges): Datenmodell Challenge und ChallengeParticipant"
```

---

## Task 2: Add-on `challenges` im Seed

**Files:**
- Modify: `backend/app/seed.py:24` (`KNOWN_ADDONS`)
- Test: `backend/tests/test_seed.py`

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_seed.py`:

```python
def test_seed_legt_challenges_addon_aus_an(session):
    from sqlmodel import select

    from app.models import AddOn
    from app.seed import seed_all

    seed_all(session, admin_user="admin", admin_password="pw123456", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "challenges")).first()
    assert addon is not None
    # Bewusst aus: erst befuellen, dann scharfschalten.
    assert addon.enabled is False
    assert addon.active_from is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_seed.py -k challenges -v`
Expected: FAIL — `assert None is not None`

- [x] **Step 3: Write minimal implementation**

In `backend/app/seed.py`, als weiterer Eintrag in der Liste `KNOWN_ADDONS`:

```python
    {
        "key": "challenges",
        "label": "Challenges",
        "description": "Zeitlich begrenzte Wettbewerbe mit Ziel oder Rangliste.",
        "enabled": False,  # erst befuellen, dann scharfschalten
    },
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_seed.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/app/seed.py backend/tests/test_seed.py
git commit -m "feat(challenges): Add-on challenges im Seed, standardmaessig aus"
```

---

## Task 3: Metrik `mm` mit Kategorie-Filter

**Files:**
- Create: `backend/app/services/challenges.py`
- Test: `backend/tests/test_challenges_metrics.py`

- [x] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_challenges_metrics.py`:

```python
from datetime import date

from app.models import Activity, Challenge
from tests.conftest import make_category, make_user


def make_challenge(session, **kw) -> Challenge:
    daten = dict(
        title="Test",
        creator_id=1,
        mode="ziel",
        target=100.0,
        metric="mm",
        join_mode="auto",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        status="laufend",
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def add_activity(session, user_id, cat_id, tag, km):
    session.add(
        Activity(user_id=user_id, category_id=cat_id, date=tag, distance_km=km)
    )
    session.commit()


def test_mm_summiert_km_mal_kategoriefaktor(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session)
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 6), 5.0)
    assert challenges.metric_value(session, user.id, ch) == 60.0


def test_mm_ignoriert_aktivitaeten_ausserhalb_des_zeitraums(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session)
    add_activity(session, user.id, lauf.id, date(2026, 7, 31), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 9, 1), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 1), 1.0)
    assert challenges.metric_value(session, user.id, ch) == 4.0


def test_mm_mit_kategoriefilter(session):
    import json

    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    rad = make_category(session, name="Rad", factor=1.0)
    ch = make_challenge(session, category_ids_json=json.dumps([lauf.id]))
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, user.id, rad.id, date(2026, 8, 5), 50.0)
    assert challenges.metric_value(session, user.id, ch) == 40.0


def test_mm_ignoriert_km_factor(session):
    from app.services import challenges

    user = make_user(session)
    user.km_factor = 2.0
    session.add(user)
    session.commit()
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session)
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    # Das Admin-Handicap gilt nur im Saison-Ranking, nicht in Challenges.
    assert challenges.metric_value(session, user.id, ch) == 40.0
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.challenges'`

- [x] **Step 3: Write minimal implementation**

Neue Datei `backend/app/services/challenges.py`:

```python
"""Challenges: Metriken, Stand, Lebenszyklus (Spec 2026-08-04).

Der Stand wird zur Lesezeit aus den Activities gerechnet, solange die
Challenge laeuft — genau wie compute_comparison. Dadurch ziehen Strava-
Nachzuegler und Korrekturen automatisch mit und es braucht keinen Cron.
Erst beim Einfrieren wird das Ergebnis in result_json festgeschrieben.

Alle Metriken rechnen ohne User.km_factor: das Admin-Handicap gilt nur im
Saison-Ranking, eine 300-MM-Huerde soll fuer alle dieselbe Huerde sein.
"""

import json
from datetime import date as date_type

from sqlmodel import Session, select

from ..models import Activity, Category, Challenge


def category_ids(ch: Challenge) -> list[int]:
    """Leere Liste = alle Kategorien."""
    return json.loads(ch.category_ids_json or "[]")


def _rows(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> list[tuple[Activity, Category]]:
    """Aktivitaeten des Users im Challenge-Zeitraum, Kategorie-gefiltert."""
    erlaubt = set(category_ids(ch))
    ende = ch.period_end if bis is None else min(ch.period_end, bis)
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    acts = session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= ch.period_start,
            Activity.date <= ende,
        )
    ).all()
    return [
        (a, cats[a.category_id])
        for a in acts
        if a.category_id in cats and (not erlaubt or a.category_id in erlaubt)
    ]


def metric_mm(session: Session, user_id: int, ch: Challenge) -> float:
    return round(sum(a.distance_km * c.factor for a, c in _rows(session, user_id, ch)), 2)


def metric_value(
    session: Session, user_id: int, ch: Challenge, heute: date_type | None = None
) -> float:
    if ch.metric == "mm":
        return metric_mm(session, user_id, ch)
    raise ValueError(f"Unbekannte Metrik: {ch.metric}")
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_metrics.py -v`
Expected: PASS (4 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/tests/test_challenges_metrics.py
git commit -m "feat(challenges): Metrik mm mit Kategorie-Filter"
```

---

## Task 4: Metriken `anzahl` und `streak`

**Files:**
- Modify: `backend/app/services/challenges.py`
- Test: `backend/tests/test_challenges_metrics.py`

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_challenges_metrics.py`:

```python
def test_anzahl_zaehlt_aktivitaeten(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=4.0)
    ch = make_challenge(session, metric="anzahl", target=3.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 10.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 5), 2.0)
    add_activity(session, user.id, lauf.id, date(2026, 7, 5), 2.0)
    assert challenges.metric_value(session, user.id, ch) == 2


def test_streak_laengste_serie_mit_tagesminimum(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, metric="streak", target=3.0, streak_min_mm=5.0)
    # 3.,4.,5. August je 6 MM -> Serie 3; 7. August 2 MM -> zaehlt nicht
    for tag in (3, 4, 5):
        add_activity(session, user.id, lauf.id, date(2026, 8, tag), 6.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 7), 2.0)
    assert challenges.metric_value(session, user.id, ch, date(2026, 8, 10)) == 3


def test_streak_summiert_mehrere_aktivitaeten_pro_tag(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, metric="streak", target=2.0, streak_min_mm=5.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 3), 3.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 3), 3.0)
    add_activity(session, user.id, lauf.id, date(2026, 8, 4), 6.0)
    assert challenges.metric_value(session, user.id, ch, date(2026, 8, 10)) == 2


def test_streak_zaehlt_nur_bis_heute(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, metric="streak", target=3.0, streak_min_mm=5.0)
    for tag in (3, 4, 5):
        add_activity(session, user.id, lauf.id, date(2026, 8, tag), 6.0)
    # Am 4. August ist die Serie erst 2 Tage lang.
    assert challenges.metric_value(session, user.id, ch, date(2026, 8, 4)) == 2
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_metrics.py -k "anzahl or streak" -v`
Expected: FAIL — `ValueError: Unbekannte Metrik: anzahl`

- [x] **Step 3: Write minimal implementation**

In `backend/app/services/challenges.py`: `from collections import defaultdict` und `from datetime import timedelta` oben ergänzen, dann `metric_value` ersetzen und die neuen Funktionen davor einfügen:

```python
def metric_anzahl(session: Session, user_id: int, ch: Challenge) -> int:
    return len(_rows(session, user_id, ch))


def per_day(
    session: Session, user_id: int, ch: Challenge, bis: date_type | None = None
) -> dict[date_type, float]:
    """MM je Kalendertag im Zeitraum (Kategorie-gefiltert)."""
    tage: dict[date_type, float] = defaultdict(float)
    for a, c in _rows(session, user_id, ch, bis):
        tage[a.date] += a.distance_km * c.factor
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_metrics.py -v`
Expected: PASS (8 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/tests/test_challenges_metrics.py
git commit -m "feat(challenges): Metriken anzahl und streak"
```

---

## Task 5: Streak-Abbruch — „nicht mehr schaffbar"

**Files:**
- Modify: `backend/app/services/challenges.py`
- Test: `backend/tests/test_challenges_metrics.py`

Kernregel: `max_erreichbar = max(beste_serie_bisher, serie_bis_gestern + resttage_ab_heute)`. Bewusst `serie_bis_gestern`, weil der heutige Tag noch offen ist und als erreichbar zählt.

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_challenges_metrics.py`:

```python
def test_streak_noch_moeglich_wenn_genug_resttage(session):
    from app.services import challenges

    user = make_user(session)
    make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=10.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    # Am 10. August bleiben 22 Tage — auch ohne jede Aktivitaet erreichbar.
    assert challenges.streak_noch_moeglich(session, user.id, ch, date(2026, 8, 10))


def test_streak_nicht_mehr_moeglich_wenn_resttage_fehlen(session):
    from app.services import challenges

    user = make_user(session)
    make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=10.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    # Am 25. August bleiben 7 Tage, keine laufende Serie -> unmoeglich.
    assert not challenges.streak_noch_moeglich(session, user.id, ch, date(2026, 8, 25))


def test_streak_laufende_serie_rettet_die_rechnung(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=10.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    # 20.-24. August durchgezogen = Serie 5, dazu 7 Resttage ab dem 25. = 12.
    for tag in range(20, 25):
        add_activity(session, user.id, lauf.id, date(2026, 8, tag), 6.0)
    assert challenges.streak_noch_moeglich(session, user.id, ch, date(2026, 8, 25))


def test_streak_heutiger_tag_zaehlt_als_erreichbar(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=3.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 5),
    )
    # Serie bis gestern (3.8.) = 2, heute (4.8.) noch nichts eingetragen,
    # Resttage 4.+5. = 2 -> 2 + 2 = 4 >= 3. Muss moeglich bleiben.
    for tag in (2, 3):
        add_activity(session, user.id, lauf.id, date(2026, 8, tag), 6.0)
    assert challenges.streak_noch_moeglich(session, user.id, ch, date(2026, 8, 4))


def test_streak_bereits_geschafft_bleibt_moeglich(session):
    from app.services import challenges

    user = make_user(session)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=3.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    for tag in (1, 2, 3):
        add_activity(session, user.id, lauf.id, date(2026, 8, tag), 6.0)
    assert challenges.streak_noch_moeglich(session, user.id, ch, date(2026, 8, 30))


def test_abbruchregel_gilt_nicht_fuer_mm_und_rangliste(session):
    from app.services import challenges

    user = make_user(session)
    make_category(session, name="Joggen", factor=1.0)
    mm_ch = make_challenge(session, metric="mm", target=99999.0)
    assert challenges.streak_noch_moeglich(session, user.id, mm_ch, date(2026, 8, 31))
    rang = make_challenge(session, mode="rangliste", metric="streak", target=None, top_n=1)
    assert challenges.streak_noch_moeglich(session, user.id, rang, date(2026, 8, 31))
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_metrics.py -k moeglich -v`
Expected: FAIL — `AttributeError: module 'app.services.challenges' has no attribute 'streak_noch_moeglich'`

- [x] **Step 3: Write minimal implementation**

Ans Ende von `backend/app/services/challenges.py`:

```python
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_metrics.py -v`
Expected: PASS (14 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/tests/test_challenges_metrics.py
git commit -m "feat(challenges): Streak-Abbruch sobald das Ziel unerreichbar ist"
```

---

## Task 6: Teilnehmer und Stand (Rangliste)

**Files:**
- Modify: `backend/app/services/challenges.py`
- Test: `backend/tests/test_challenges_lifecycle.py` (neu)

Ein Standings-Eintrag ist ein Dict mit genau diesen Schlüsseln:
`user_id`, `value`, `rank`, `geschafft`, `nicht_mehr_schaffbar`.

- [x] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_challenges_lifecycle.py`:

```python
from datetime import date

from app.models import Activity, Challenge, ChallengeParticipant
from tests.conftest import make_category, make_user


def make_challenge(session, **kw) -> Challenge:
    daten = dict(
        title="Test", creator_id=1, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31), status="laufend",
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def add_activity(session, user_id, cat_id, tag, km):
    session.add(
        Activity(user_id=user_id, category_id=cat_id, date=tag, distance_km=km)
    )
    session.commit()


def test_teilnehmer_auto_sind_alle_aktiven(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    c.is_active = False
    session.add(c)
    session.commit()
    ch = make_challenge(session, join_mode="auto")
    assert challenges.teilnehmer_ids(session, ch) == sorted([a.id, b.id])


def test_teilnehmer_opt_in_nur_beigetretene(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    make_user(session, username="ben")
    ch = make_challenge(session, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.commit()
    assert challenges.teilnehmer_ids(session, ch) == [a.id]


def test_standings_sortiert_und_markiert_geschafft(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, target=100.0)
    add_activity(session, a.id, lauf.id, date(2026, 8, 5), 120.0)
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 40.0)
    stand = challenges.standings(session, ch, date(2026, 8, 10))
    assert [e["user_id"] for e in stand] == [a.id, b.id]
    assert [e["rank"] for e in stand] == [1, 2]
    assert [e["geschafft"] for e in stand] == [True, False]


def test_standings_gleichstand_teilt_rang_und_ueberspringt(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    c = make_user(session, username="carla")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, mode="rangliste", target=None, top_n=2)
    add_activity(session, a.id, lauf.id, date(2026, 8, 5), 50.0)
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 50.0)
    add_activity(session, c.id, lauf.id, date(2026, 8, 5), 10.0)
    stand = challenges.standings(session, ch, date(2026, 8, 10))
    assert [e["rank"] for e in stand] == [1, 1, 3]
    # Bei Gleichstand duerfen mehr als top_n gewinnen — geteilte Plaetze
    # sind bei einem echten Preis besser als ein Zufalls-Stichentscheid.
    assert [e["geschafft"] for e in stand] == [True, True, False]


def test_standings_uebergeht_inaktive_teilnehmer(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    b = make_user(session, username="ben")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, join_mode="opt_in")
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=a.id))
    session.add(ChallengeParticipant(challenge_id=ch.id, user_id=b.id))
    session.commit()
    add_activity(session, b.id, lauf.id, date(2026, 8, 5), 500.0)
    b.is_active = False
    session.add(b)
    session.commit()
    stand = challenges.standings(session, ch, date(2026, 8, 10))
    assert [e["user_id"] for e in stand] == [a.id]


def test_standings_markiert_nicht_mehr_schaffbar(session):
    from app.services import challenges

    a = make_user(session, username="anna")
    make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(
        session, metric="streak", target=10.0,
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    stand = challenges.standings(session, ch, date(2026, 8, 25))
    assert stand[0]["nicht_mehr_schaffbar"] is True
    assert stand[0]["geschafft"] is False
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_lifecycle.py -v`
Expected: FAIL — `AttributeError: module 'app.services.challenges' has no attribute 'teilnehmer_ids'`

- [x] **Step 3: Write minimal implementation**

In `backend/app/services/challenges.py` den Import um `ChallengeParticipant` und `User` erweitern:

```python
from ..models import Activity, Category, Challenge, ChallengeParticipant, User
```

Dann ans Dateiende:

```python
def teilnehmer_ids(session: Session, ch: Challenge) -> list[int]:
    """Bei 'auto' alle aktiven User, bei 'opt_in' die Beigetretenen.
    Inaktive User fallen in beiden Faellen raus."""
    aktive = {
        u.id for u in session.exec(select(User).where(User.is_active)).all()
    }
    if ch.join_mode == "auto":
        return sorted(aktive)
    rows = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id
        )
    ).all()
    return sorted(r.user_id for r in rows if r.user_id in aktive)


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

    letzter_wert = None
    letzter_rang = 0
    for i, e in enumerate(eintraege, start=1):
        if letzter_wert is not None and e["value"] == letzter_wert:
            e["rank"] = letzter_rang
        else:
            e["rank"] = i
            letzter_rang = i
            letzter_wert = e["value"]

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
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_lifecycle.py -v`
Expected: PASS (6 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/tests/test_challenges_lifecycle.py
git commit -m "feat(challenges): Teilnehmer-Ermittlung und Rangliste mit geteilten Raengen"
```

---

## Task 7: Lebenszyklus und Einfrieren

**Files:**
- Modify: `backend/app/services/challenges.py`
- Test: `backend/tests/test_challenges_lifecycle.py`

Einfrierzeitpunkt: Folgetag von `period_end`, 06:00 deutscher Zeit. Feed-Events kommen erst in Task 11 dazu — hier bleibt `resolve_due` noch ohne Feed.

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_challenges_lifecycle.py`:

```python
def test_freeze_at_ist_folgetag_sechs_uhr_deutscher_zeit(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(session, period_end=date(2026, 8, 31))
    # 01.09.2026 06:00 MESZ == 04:00 UTC
    assert challenges.freeze_at(ch) == datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)


def test_resolve_due_startet_geplante_challenge(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(
        session, status="geplant",
        period_start=date(2026, 8, 1), period_end=date(2026, 8, 31),
    )
    challenges.resolve_due(session, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "laufend"


def test_resolve_due_laesst_zukuenftige_challenge_geplant(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(
        session, status="geplant",
        period_start=date(2026, 9, 1), period_end=date(2026, 9, 30),
    )
    challenges.resolve_due(session, datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "geplant"


def test_resolve_due_friert_erst_nach_der_karenz_ein(session):
    from datetime import datetime, timezone

    from app.services import challenges

    make_user(session, username="anna")
    make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, period_end=date(2026, 8, 31))
    # 01.09. 03:00 UTC = 05:00 MESZ, noch vor der Karenzgrenze
    challenges.resolve_due(session, datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "laufend"
    challenges.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "beendet"


def test_eingefrorenes_ergebnis_aendert_sich_nicht_mehr(session):
    import json
    from datetime import datetime, timezone

    from app.services import challenges

    anna = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session, target=100.0, period_end=date(2026, 8, 31))
    add_activity(session, anna.id, lauf.id, date(2026, 8, 5), 120.0)
    challenges.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    ergebnis = json.loads(ch.result_json)
    assert ergebnis["gewinner_ids"] == [anna.id]
    assert ergebnis["entries"][0]["value"] == 120.0
    assert set(ergebnis["entries"][0]) == {"user_id", "value", "rank", "geschafft"}
    assert ch.resolved_at is not None

    # Nachtraeglich eingetragene Aktivitaet darf nichts mehr aendern.
    add_activity(session, anna.id, lauf.id, date(2026, 8, 6), 500.0)
    challenges.resolve_due(session, datetime(2026, 9, 5, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert json.loads(ch.result_json)["entries"][0]["value"] == 120.0


def test_resolve_due_ignoriert_abgebrochene(session):
    from datetime import datetime, timezone

    from app.services import challenges

    ch = make_challenge(session, status="abgebrochen", period_end=date(2026, 8, 31))
    challenges.resolve_due(session, datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc))
    session.refresh(ch)
    assert ch.status == "abgebrochen"
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_lifecycle.py -k "freeze or resolve or eingefroren" -v`
Expected: FAIL — `AttributeError: module 'app.services.challenges' has no attribute 'freeze_at'`

- [x] **Step 3: Write minimal implementation**

In `backend/app/services/challenges.py` die Imports oben ergänzen:

```python
from datetime import datetime, timedelta, timezone
from datetime import time as time_type
```

Direkt unter den bestehenden Modul-Konstanten:

```python
# Karenz nach Challenge-Ende: Einfrieren erst am Folgetag um 06:00 deutscher
# Zeit. Deckt einen ausstehenden Strava-Sync und eine Aktivitaet kurz vor
# Mitternacht ab, die erst am naechsten Morgen eingetragen wird.
KARENZ_STUNDE = 6
# Fester Sommerzeit-Offset wie in services/feed.py und services/achievements.py.
_MESZ = timezone(timedelta(hours=2))
```

Ans Dateiende:

```python
def freeze_at(ch: Challenge) -> datetime:
    """UTC-Zeitpunkt, ab dem das Ergebnis feststeht."""
    tag = ch.period_end + timedelta(days=1)
    return datetime.combine(
        tag, time_type(KARENZ_STUNDE, 0), tzinfo=_MESZ
    ).astimezone(timezone.utc)


def ist_vorlaeufig(ch: Challenge, heute: date_type) -> bool:
    """Zeitraum vorbei, Ergebnis aber noch nicht eingefroren."""
    return ch.status == "laufend" and heute > ch.period_end


def _einfrieren(session: Session, ch: Challenge, jetzt: datetime, heute: date_type) -> None:
    eintraege = standings(session, ch, heute)
    ch.result_json = json.dumps(
        {
            "entries": [
                {k: e[k] for k in ("user_id", "value", "rank", "geschafft")}
                for e in eintraege
            ],
            "gewinner_ids": [e["user_id"] for e in eintraege if e["geschafft"]],
        }
    )
    ch.status = "beendet"
    ch.resolved_at = jetzt
    session.add(ch)
    session.commit()


def resolve_due(session: Session, jetzt: datetime | None = None) -> None:
    """Faellige Statusuebergaenge, lazy beim Request — kein Cron.
    Gleiches Muster wie bets.resolve_due."""
    jetzt = jetzt or datetime.now(timezone.utc)
    heute = jetzt.astimezone(_MESZ).date()

    for ch in session.exec(
        select(Challenge).where(Challenge.status == "geplant").order_by(Challenge.id)
    ).all():
        if heute >= ch.period_start:
            ch.status = "laufend"
            session.add(ch)
            session.commit()

    for ch in session.exec(
        select(Challenge).where(Challenge.status == "laufend").order_by(Challenge.id)
    ).all():
        if jetzt >= freeze_at(ch):
            _einfrieren(session, ch, jetzt, heute)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_lifecycle.py -v`
Expected: PASS (12 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/tests/test_challenges_lifecycle.py
git commit -m "feat(challenges): Lebenszyklus und Einfrieren nach Karenz"
```

---

## Task 8: Router — Liste und Detail

**Files:**
- Create: `backend/app/routers/challenges.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_challenges_api.py` (neu)

- [x] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_challenges_api.py`:

```python
from datetime import date, timedelta

from app.models import Challenge
from tests.conftest import login, make_addon, make_category, make_user


def make_challenge(session, **kw) -> Challenge:
    heute = date.today()
    daten = dict(
        title="Test", creator_id=1, mode="ziel", target=100.0, metric="mm",
        join_mode="auto", period_start=heute - timedelta(days=5),
        period_end=heute + timedelta(days=5), status="laufend",
    )
    daten.update(kw)
    ch = Challenge(**daten)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def test_liste_braucht_aktives_addon(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=False)
    login(client)
    assert client.get("/api/challenges").status_code == 404


def test_liste_liefert_stand(session, client):
    from app.models import Activity

    user = make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    lauf = make_category(session, name="Joggen", factor=1.0)
    ch = make_challenge(session)
    session.add(
        Activity(
            user_id=user.id, category_id=lauf.id,
            date=date.today(), distance_km=120.0,
        )
    )
    session.commit()
    login(client)
    r = client.get("/api/challenges")
    assert r.status_code == 200, r.text
    eintrag = next(c for c in r.json() if c["id"] == ch.id)
    assert eintrag["bin_dabei"] is True
    assert eintrag["standings"][0]["value"] == 120.0
    assert eintrag["standings"][0]["geschafft"] is True
    assert eintrag["standings"][0]["display_name"] == "Erik"
    assert eintrag["mein_stand"]["value"] == 120.0
    assert eintrag["vorlaeufig"] is False


def test_liste_verschweigt_abgebrochene(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    make_challenge(session, status="abgebrochen")
    login(client)
    assert client.get("/api/challenges").json() == []


def test_detail_liefert_einzelne_challenge(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, title="Radler-Monat")
    login(client)
    r = client.get(f"/api/challenges/{ch.id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Radler-Monat"


def test_detail_404_bei_unbekannter_id(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    login(client)
    assert client.get("/api/challenges/999").status_code == 404
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -v`
Expected: FAIL — alle Requests liefern 404 (Route existiert nicht)

- [x] **Step 3: Write minimal implementation**

Neue Datei `backend/app/routers/challenges.py`:

```python
"""API fuer Challenges (Spec 2026-08-04).

Jeder GET loest zuerst faellige Statusuebergaenge auf (lazy, kein Cron) —
gleiches Muster wie bets_router.
"""

import json
from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from ..deps import get_current_user, get_session, require_addon
from ..models import Challenge, User
from ..services import challenges as svc

router = APIRouter(
    prefix="/api/challenges",
    tags=["challenges"],
    dependencies=[Depends(require_addon("challenges"))],
)


class StandingEntryOut(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    value: float
    rank: int
    geschafft: bool
    nicht_mehr_schaffbar: bool


class ChallengeOut(BaseModel):
    id: int
    title: str
    description: str
    prize: str | None
    creator_id: int
    mode: str
    target: float | None
    top_n: int
    metric: str
    category_ids: list[int]
    streak_min_mm: float
    join_mode: str
    period_start: date_type
    period_end: date_type
    status: str
    vorlaeufig: bool
    bin_dabei: bool
    kann_beitreten: bool
    standings: list[StandingEntryOut]
    mein_stand: StandingEntryOut | None  # eigener Eintrag, fuer die Hero-Karte
    gewinner_ids: list[int]
    created_at: datetime
    resolved_at: datetime | None


def _users(session: Session) -> dict[int, User]:
    return {u.id: u for u in session.exec(select(User)).all()}


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
    else:
        roh = svc.standings(session, ch, heute)
        gewinner = [e["user_id"] for e in roh if e["geschafft"]]

    def eintrag(e: dict) -> StandingEntryOut:
        u = users.get(e["user_id"])
        return StandingEntryOut(
            user_id=e["user_id"],
            display_name=u.display_name if u else "?",
            avatar=u.avatar if u else "icon:laufen",
            value=e["value"],
            rank=e["rank"],
            geschafft=e["geschafft"],
            nicht_mehr_schaffbar=e["nicht_mehr_schaffbar"],
        )

    liste = [eintrag(e) for e in roh]
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
        bin_dabei=me.id in teilnehmer,
        kann_beitreten=(
            ch.join_mode == "opt_in"
            and me.id not in teilnehmer
            and ch.status in ("geplant", "laufend")
            and heute <= ch.period_end
        ),
        standings=liste,
        mein_stand=next((e for e in liste if e.user_id == me.id), None),
        gewinner_ids=gewinner,
        created_at=ch.created_at,
        resolved_at=ch.resolved_at,
    )


@router.get("", response_model=list[ChallengeOut])
def list_challenges(
    me: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    svc.resolve_due(session)
    heute = date_type.today()
    alle = session.exec(
        select(Challenge)
        .where(Challenge.status != "abgebrochen")
        .order_by(Challenge.period_end, Challenge.id)
    ).all()
    return [_challenge_out(session, ch, me, heute) for ch in alle]


@router.get("/{challenge_id}", response_model=ChallengeOut)
def get_challenge(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    svc.resolve_due(session)
    ch = session.get(Challenge, challenge_id)
    if ch is None or ch.status == "abgebrochen":
        raise HTTPException(status_code=404, detail="Challenge nicht gefunden")
    return _challenge_out(session, ch, me, date_type.today())
```

In `backend/app/main.py` den Import erweitern und den Router registrieren — `challenges` alphabetisch nach `categories` einsortieren:

```python
from .routers import (
    achievements,
    activities,
    addons,
    auth_router,
    bets_router,
    categories,
    challenges,
    comparison,
    feed,
    invites,
    seasons,
    strava_router,
    users,
)
```

und bei den `include_router`-Aufrufen nach `categories.router`:

```python
app.include_router(challenges.router)
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -v`
Expected: PASS (5 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/challenges.py backend/app/main.py backend/tests/test_challenges_api.py
git commit -m "feat(challenges): API-Endpunkte fuer Liste und Detail"
```

---

## Task 9: Router — Beitreten und Austreten

**Files:**
- Modify: `backend/app/routers/challenges.py`
- Test: `backend/tests/test_challenges_api.py`

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_challenges_api.py`:

```python
def test_beitreten_und_austreten(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, join_mode="opt_in")
    login(client)
    assert client.get(f"/api/challenges/{ch.id}").json()["bin_dabei"] is False
    r = client.post(f"/api/challenges/{ch.id}/join")
    assert r.status_code == 200, r.text
    assert r.json()["bin_dabei"] is True
    r = client.delete(f"/api/challenges/{ch.id}/join")
    assert r.status_code == 200
    assert r.json()["bin_dabei"] is False


def test_beitreten_ist_idempotent(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, join_mode="opt_in")
    login(client)
    client.post(f"/api/challenges/{ch.id}/join")
    r = client.post(f"/api/challenges/{ch.id}/join")
    assert r.status_code == 200
    assert r.json()["bin_dabei"] is True


def test_beitreten_zu_auto_challenge_ist_409(session, client):
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, join_mode="auto")
    login(client)
    assert client.post(f"/api/challenges/{ch.id}/join").status_code == 409


def test_beitreten_nach_ende_ist_409(session, client):
    heute = date.today()
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, join_mode="opt_in", status="beendet",
        period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
    )
    login(client)
    assert client.post(f"/api/challenges/{ch.id}/join").status_code == 409


def test_beitreten_zu_geplanter_challenge_erlaubt(session, client):
    heute = date.today()
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, join_mode="opt_in", status="geplant",
        period_start=heute + timedelta(days=5), period_end=heute + timedelta(days=20),
    )
    login(client)
    assert client.post(f"/api/challenges/{ch.id}/join").status_code == 200


def test_austreten_aus_beendeter_challenge_ist_409(session, client):
    heute = date.today()
    make_user(session)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, join_mode="opt_in", status="beendet",
        period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
    )
    login(client)
    assert client.delete(f"/api/challenges/{ch.id}/join").status_code == 409
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -k "beitreten or austreten" -v`
Expected: FAIL — 405 Method Not Allowed (Route fehlt)

- [x] **Step 3: Write minimal implementation**

In `backend/app/routers/challenges.py` den Model-Import erweitern:

```python
from ..models import Challenge, ChallengeParticipant, User
```

Ans Dateiende:

```python
def _geladene_challenge(session: Session, challenge_id: int) -> Challenge:
    ch = session.get(Challenge, challenge_id)
    if ch is None or ch.status == "abgebrochen":
        raise HTTPException(status_code=404, detail="Challenge nicht gefunden")
    return ch


@router.post("/{challenge_id}/join", response_model=ChallengeOut)
def join_challenge(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    svc.resolve_due(session)
    ch = _geladene_challenge(session, challenge_id)
    heute = date_type.today()
    if ch.join_mode != "opt_in":
        raise HTTPException(status_code=409, detail="Hier sind alle automatisch dabei")
    if heute > ch.period_end or ch.status == "beendet":
        raise HTTPException(status_code=409, detail="Die Challenge ist vorbei")
    vorhanden = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id,
            ChallengeParticipant.user_id == me.id,
        )
    ).first()
    if vorhanden is None:  # idempotent: zweiter Beitritt ist kein Fehler
        session.add(ChallengeParticipant(challenge_id=ch.id, user_id=me.id))
        session.commit()
    return _challenge_out(session, ch, me, heute)


@router.delete("/{challenge_id}/join", response_model=ChallengeOut)
def leave_challenge(
    challenge_id: int,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    svc.resolve_due(session)
    ch = _geladene_challenge(session, challenge_id)
    if ch.status not in ("geplant", "laufend"):
        raise HTTPException(status_code=409, detail="Die Challenge ist vorbei")
    zeile = session.exec(
        select(ChallengeParticipant).where(
            ChallengeParticipant.challenge_id == ch.id,
            ChallengeParticipant.user_id == me.id,
        )
    ).first()
    if zeile is not None:
        session.delete(zeile)
        session.commit()
    return _challenge_out(session, ch, me, date_type.today())
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -v`
Expected: PASS (11 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/challenges.py backend/tests/test_challenges_api.py
git commit -m "feat(challenges): Beitreten und Austreten"
```

---

## Task 10: Router — Admin-CRUD und Validierung

**Files:**
- Modify: `backend/app/routers/challenges.py`
- Test: `backend/tests/test_challenges_api.py`

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_challenges_api.py`:

```python
def _basis(**kw) -> dict:
    heute = date.today()
    daten = {
        "title": "August bis Stuttgartlauf",
        "mode": "ziel",
        "target": 300.0,
        "metric": "mm",
        "join_mode": "auto",
        "period_start": (heute + timedelta(days=1)).isoformat(),
        "period_end": (heute + timedelta(days=20)).isoformat(),
    }
    daten.update(kw)
    return daten


def test_anlegen_nur_als_admin(session, client):
    make_user(session, username="erik")
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    login(client)
    assert client.post("/api/challenges", json=_basis()).status_code == 403


def test_admin_legt_challenge_an(session, client):
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    login(client)
    r = client.post("/api/challenges", json=_basis(prize="Startplatz"))
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "geplant"
    assert r.json()["prize"] == "Startplatz"


def test_anlegen_validiert(session, client):
    heute = date.today()
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    lauf = make_category(session, name="Joggen", factor=1.0)
    login(client)

    faelle = [
        _basis(period_start=(heute + timedelta(days=9)).isoformat(),
               period_end=(heute + timedelta(days=2)).isoformat()),
        _basis(period_start=(heute - timedelta(days=9)).isoformat(),
               period_end=(heute - timedelta(days=2)).isoformat()),
        _basis(mode="ziel", target=None),
        _basis(mode="rangliste", target=None, top_n=0),
        _basis(metric="quatsch"),
        _basis(metric="streak", streak_min_mm=0.0),
        _basis(category_ids=[lauf.id, 9999]),
        _basis(mode="quatsch"),
        _basis(join_mode="quatsch"),
    ]
    for daten in faelle:
        assert client.post("/api/challenges", json=daten).status_code == 422, daten


def test_patch_aendert_titel_immer_regeln_nur_geplant(session, client):
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session, status="laufend")
    login(client)
    r = client.patch(f"/api/challenges/{ch.id}", json={"title": "Neuer Titel"})
    assert r.status_code == 200
    assert r.json()["title"] == "Neuer Titel"
    r = client.patch(f"/api/challenges/{ch.id}", json={"target": 50.0})
    assert r.status_code == 409


def test_patch_regeln_bei_geplanter_challenge_erlaubt(session, client):
    heute = date.today()
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(
        session, status="geplant",
        period_start=heute + timedelta(days=3), period_end=heute + timedelta(days=9),
    )
    login(client)
    r = client.patch(f"/api/challenges/{ch.id}", json={"target": 50.0})
    assert r.status_code == 200
    assert r.json()["target"] == 50.0


def test_delete_bricht_ab_statt_zu_loeschen(session, client):
    make_user(session, username="erik", is_admin=True)
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch = make_challenge(session)
    login(client)
    assert client.delete(f"/api/challenges/{ch.id}").status_code == 204
    session.expire_all()
    assert session.get(Challenge, ch.id).status == "abgebrochen"
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -k "anlegen or patch or delete" -v`
Expected: FAIL — 405 Method Not Allowed

- [x] **Step 3: Write minimal implementation**

In `backend/app/routers/challenges.py` den deps-Import um `require_admin` erweitern:

```python
from ..deps import get_current_user, get_session, require_addon, require_admin
```

und den Model-Import um `Category`:

```python
from ..models import Category, Challenge, ChallengeParticipant, User
```

Dann bei den Schemas (nach `ChallengeOut`) ergänzen:

```python
class ChallengeCreateIn(BaseModel):
    title: str
    description: str = ""
    prize: str | None = None
    mode: str = "ziel"
    target: float | None = None
    top_n: int = 1
    metric: str = "mm"
    category_ids: list[int] = []
    streak_min_mm: float = 5.0
    join_mode: str = "auto"
    period_start: date_type
    period_end: date_type


class ChallengePatchIn(BaseModel):
    title: str | None = None
    description: str | None = None
    prize: str | None = None
    mode: str | None = None
    target: float | None = None
    top_n: int | None = None
    metric: str | None = None
    category_ids: list[int] | None = None
    streak_min_mm: float | None = None
    join_mode: str | None = None
    period_start: date_type | None = None
    period_end: date_type | None = None


# Felder, die nur solange status="geplant" geaendert werden duerfen —
# Spielregeln mitten im Lauf zu aendern waere unfair.
REGEL_FELDER = {
    "mode", "target", "top_n", "metric", "category_ids",
    "streak_min_mm", "join_mode", "period_start", "period_end",
}
```

Ans Dateiende:

```python
def _pruefe_regeln(
    session: Session,
    *,
    mode: str,
    target: float | None,
    top_n: int,
    metric: str,
    category_ids: list[int],
    streak_min_mm: float,
    join_mode: str,
    period_start: date_type,
    period_end: date_type,
    neu: bool,
) -> None:
    if mode not in ("ziel", "rangliste"):
        raise HTTPException(status_code=422, detail="Unbekannter Modus")
    if metric not in ("mm", "streak", "anzahl"):
        raise HTTPException(status_code=422, detail="Unbekannte Metrik")
    if join_mode not in ("auto", "opt_in"):
        raise HTTPException(status_code=422, detail="Unbekannte Teilnahme-Art")
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Ende liegt vor dem Start")
    if neu and period_end < date_type.today():
        raise HTTPException(status_code=422, detail="Das Ende liegt in der Vergangenheit")
    if mode == "ziel" and target is None:
        raise HTTPException(status_code=422, detail="Ziel-Challenge braucht ein Ziel")
    if mode == "rangliste" and top_n < 1:
        raise HTTPException(status_code=422, detail="top_n muss mindestens 1 sein")
    if metric == "streak" and streak_min_mm <= 0:
        raise HTTPException(status_code=422, detail="Tages-Minimum muss groesser 0 sein")
    if category_ids:
        bekannt = {c.id for c in session.exec(select(Category)).all()}
        if not set(category_ids) <= bekannt:
            raise HTTPException(status_code=422, detail="Unbekannte Kategorie")


@router.post(
    "", response_model=ChallengeOut, status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_challenge(
    data: ChallengeCreateIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _pruefe_regeln(
        session,
        mode=data.mode, target=data.target, top_n=data.top_n, metric=data.metric,
        category_ids=data.category_ids, streak_min_mm=data.streak_min_mm,
        join_mode=data.join_mode, period_start=data.period_start,
        period_end=data.period_end, neu=True,
    )
    ch = Challenge(
        title=data.title,
        description=data.description,
        prize=data.prize,
        creator_id=me.id,
        mode=data.mode,
        target=data.target,
        top_n=data.top_n,
        metric=data.metric,
        category_ids_json=json.dumps(data.category_ids),
        streak_min_mm=data.streak_min_mm,
        join_mode=data.join_mode,
        period_start=data.period_start,
        period_end=data.period_end,
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    svc.resolve_due(session)
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())


@router.patch(
    "/{challenge_id}", response_model=ChallengeOut,
    dependencies=[Depends(require_admin)],
)
def patch_challenge(
    challenge_id: int,
    data: ChallengePatchIn,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    ch = _geladene_challenge(session, challenge_id)
    gesetzt = data.model_fields_set
    if gesetzt & REGEL_FELDER and ch.status != "geplant":
        raise HTTPException(
            status_code=409, detail="Wertungsregeln sind nach dem Start fest"
        )
    werte = {
        "mode": data.mode if data.mode is not None else ch.mode,
        "target": data.target if "target" in gesetzt else ch.target,
        "top_n": data.top_n if data.top_n is not None else ch.top_n,
        "metric": data.metric if data.metric is not None else ch.metric,
        "category_ids": data.category_ids
        if data.category_ids is not None
        else svc.category_ids(ch),
        "streak_min_mm": data.streak_min_mm
        if data.streak_min_mm is not None
        else ch.streak_min_mm,
        "join_mode": data.join_mode if data.join_mode is not None else ch.join_mode,
        "period_start": data.period_start or ch.period_start,
        "period_end": data.period_end or ch.period_end,
    }
    _pruefe_regeln(session, neu=False, **werte)

    if data.title is not None:
        ch.title = data.title
    if data.description is not None:
        ch.description = data.description
    if "prize" in gesetzt:
        ch.prize = data.prize
    ch.mode = werte["mode"]
    ch.target = werte["target"]
    ch.top_n = werte["top_n"]
    ch.metric = werte["metric"]
    ch.category_ids_json = json.dumps(werte["category_ids"])
    ch.streak_min_mm = werte["streak_min_mm"]
    ch.join_mode = werte["join_mode"]
    ch.period_start = werte["period_start"]
    ch.period_end = werte["period_end"]
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())


@router.delete(
    "/{challenge_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def cancel_challenge(challenge_id: int, session: Session = Depends(get_session)):
    ch = session.get(Challenge, challenge_id)
    if ch is not None:
        ch.status = "abgebrochen"  # nie loeschen, Historie bleibt
        session.add(ch)
        session.commit()
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -v`
Expected: PASS (17 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/routers/challenges.py backend/tests/test_challenges_api.py
git commit -m "feat(challenges): Admin-CRUD mit Validierung der Wertungsregeln"
```

---

## Task 11: Feed-Events

**Files:**
- Modify: `backend/app/services/feed.py`, `backend/app/services/challenges.py`, `backend/app/routers/challenges.py`
- Test: `backend/tests/test_feed.py`

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_feed.py`:

```python
def test_challenge_events_start_qualifiziert_ende(session):
    import json
    from datetime import date, datetime, timedelta, timezone

    from sqlmodel import select

    from app.models import Activity, Challenge, FeedEvent, Season
    from app.services import challenges as svc
    from tests.conftest import make_category, make_user

    anna = make_user(session, username="anna")
    lauf = make_category(session, name="Joggen", factor=1.0)
    session.add(Season(year=2026, goal_km=1000.0, start_date=date(2026, 7, 20)))
    session.commit()

    ch = Challenge(
        title="August-Ziel", creator_id=anna.id, mode="ziel", target=100.0,
        metric="mm", join_mode="auto", period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31), status="geplant",
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)

    svc.resolve_due(session, datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc))
    typen = [e.type for e in session.exec(select(FeedEvent)).all()]
    assert "challenge_start" in typen

    session.add(
        Activity(
            user_id=anna.id, category_id=lauf.id,
            date=date(2026, 8, 5), distance_km=120.0,
        )
    )
    session.commit()
    session.refresh(ch)
    eintraege = svc.standings(session, ch, date(2026, 8, 6))
    svc.emit_qualified(session, ch, eintraege)
    svc.emit_qualified(session, ch, eintraege)  # zweiter Aufruf darf nichts anlegen
    qualifiziert = [
        e for e in session.exec(select(FeedEvent)).all()
        if e.type == "challenge_qualified"
    ]
    assert len(qualifiziert) == 1
    assert json.loads(qualifiziert[0].payload_json)["challenge_id"] == ch.id

    svc.resolve_due(session, datetime(2026, 9, 1, 5, 0, tzinfo=timezone.utc))
    ende = [
        e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_end"
    ]
    assert len(ende) == 1
    assert json.loads(ende[0].payload_json)["gewinner_ids"] == [anna.id]

    assert timedelta(0) == timedelta(0)  # Import bleibt genutzt
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_feed.py -k challenge_events -v`
Expected: FAIL — `assert 'challenge_start' in []`

- [x] **Step 3: Write minimal implementation**

In `backend/app/services/feed.py` den Model-Import um `Challenge` erweitern:

```python
from ..models import (
    AchievementUnlock,
    Activity,
    Category,
    Challenge,
    FeedEvent,
    FeedReaction,
    User,
)
```

Ans Dateiende von `feed.py`:

```python
def challenge_start_event(session: Session, ch: Challenge) -> None:
    _emit(
        session,
        type_="challenge_start",
        payload={"challenge_id": ch.id, "title": ch.title, "prize": ch.prize},
    )


def challenge_qualified_event(session: Session, ch: Challenge, user_id: int) -> None:
    """Entsteht in einer Lesefunktion und muss deshalb idempotent sein:
    pro (Challenge, User) hoechstens ein Event."""
    for ev in session.exec(
        select(FeedEvent).where(
            FeedEvent.type == "challenge_qualified", FeedEvent.user_id == user_id
        )
    ).all():
        if json.loads(ev.payload_json or "{}").get("challenge_id") == ch.id:
            return
    _emit(
        session,
        type_="challenge_qualified",
        user_id=user_id,
        payload={"challenge_id": ch.id, "title": ch.title},
    )


def challenge_end_event(session: Session, ch: Challenge, gewinner_ids: list[int]) -> None:
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
        },
    )
```

In `backend/app/services/challenges.py` unten den Feed-Import ergänzen (bewusst am Dateiende der Imports, `feed.py` importiert `challenges` nicht — kein Zyklus):

```python
from . import feed
```

Dann in `resolve_due` das Starten und in `_einfrieren` das Ende um die Events ergänzen:

```python
def _einfrieren(session: Session, ch: Challenge, jetzt: datetime, heute: date_type) -> None:
    eintraege = standings(session, ch, heute)
    gewinner = [e["user_id"] for e in eintraege if e["geschafft"]]
    ch.result_json = json.dumps(
        {
            "entries": [
                {k: e[k] for k in ("user_id", "value", "rank", "geschafft")}
                for e in eintraege
            ],
            "gewinner_ids": gewinner,
        }
    )
    ch.status = "beendet"
    ch.resolved_at = jetzt
    session.add(ch)
    session.commit()
    feed.challenge_end_event(session, ch, gewinner)
```

und in `resolve_due` nach dem Start-Commit:

```python
        if heute >= ch.period_start:
            ch.status = "laufend"
            session.add(ch)
            session.commit()
            feed.challenge_start_event(session, ch)
```

Ans Dateiende von `challenges.py`:

```python
def emit_qualified(session: Session, ch: Challenge, eintraege: list[dict]) -> None:
    """Feed-Event fuer alle, die das Ziel geknackt haben. Idempotent."""
    if ch.mode != "ziel" or ch.status != "laufend":
        return
    for e in eintraege:
        if e["geschafft"]:
            feed.challenge_qualified_event(session, ch, e["user_id"])
```

In `backend/app/routers/challenges.py` in `_challenge_out` direkt nach dem Berechnen von `roh` im else-Zweig:

```python
    else:
        roh = svc.standings(session, ch, heute)
        svc.emit_qualified(session, ch, roh)
        gewinner = [e["user_id"] for e in roh if e["geschafft"]]
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_feed.py tests/test_challenges_lifecycle.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/app/services/feed.py backend/app/services/challenges.py backend/app/routers/challenges.py backend/tests/test_feed.py
git commit -m "feat(challenges): Feed-Events fuer Start, Qualifikation und Ende"
```

---

## Task 11a: Sieger eintragen

**Files:**
- Modify: `backend/app/services/challenges.py`, `backend/app/services/feed.py`, `backend/app/routers/challenges.py`
- Test: `backend/tests/test_challenges_api.py`

Die Auslosung passiert **außerhalb der App** (Glücksrad, Los). Der Admin trägt danach nur ein, wer gewonnen hat. Deshalb kein Zufall im Code — und der Eintrag ist korrigierbar, weil ein Vertipper sich beheben lassen muss.

- [x] **Step 1: Write the failing test**

Ans Ende von `backend/tests/test_challenges_api.py`:

```python
def _beendete_mit_qualifizierten(session):
    """Beendete Ziel-Challenge, in der anna qualifiziert ist und ben nicht."""
    import json

    from app.models import Challenge

    heute = date.today()
    anna = make_user(session, username="anna", is_admin=True)
    ben = make_user(session, username="ben")
    ch = Challenge(
        title="August-Ziel", creator_id=anna.id, mode="ziel", target=100.0,
        metric="mm", join_mode="auto",
        period_start=heute - timedelta(days=20), period_end=heute - timedelta(days=10),
        status="beendet",
        result_json=json.dumps(
            {
                "entries": [
                    {"user_id": anna.id, "value": 120.0, "rank": 1, "geschafft": True},
                    {"user_id": ben.id, "value": 40.0, "rank": 2, "geschafft": False},
                ],
                "gewinner_ids": [anna.id],
            }
        ),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch, anna, ben


def test_sieger_eintragen_und_korrigieren(session, client):
    import json

    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, ben = _beendete_mit_qualifizierten(session)
    login(client, username="anna")

    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 200, r.text
    assert r.json()["sieger_id"] == anna.id

    # Korrektur ist erlaubt — ein Eintrag ist eine Tatsache, keine Ziehung.
    ch.result_json = json.dumps(
        {**json.loads(ch.result_json), "gewinner_ids": [anna.id, ben.id]}
    )
    session.add(ch)
    session.commit()
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    assert r.status_code == 200
    assert r.json()["sieger_id"] == ben.id


def test_sieger_nur_aus_den_qualifizierten(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, _anna, ben = _beendete_mit_qualifizierten(session)
    login(client, username="anna")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    assert r.status_code == 422


def test_sieger_nur_als_admin(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, _ben = _beendete_mit_qualifizierten(session)
    login(client, username="ben")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 403


def test_sieger_erst_nach_dem_einfrieren(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, _ben = _beendete_mit_qualifizierten(session)
    ch.status = "laufend"
    session.add(ch)
    session.commit()
    login(client, username="anna")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 409


def test_sieger_nicht_bei_rangliste(session, client):
    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, _ben = _beendete_mit_qualifizierten(session)
    ch.mode = "rangliste"
    session.add(ch)
    session.commit()
    login(client, username="anna")
    r = client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    assert r.status_code == 409


def test_sieger_korrektur_erzeugt_kein_zweites_feed_event(session, client):
    import json

    from sqlmodel import select

    from app.models import FeedEvent, Season

    make_addon(session, key="challenges", label="Challenges", enabled=True)
    ch, anna, ben = _beendete_mit_qualifizierten(session)
    session.add(Season(year=date.today().year, goal_km=1000.0, start_date=date.today()))
    ch.result_json = json.dumps(
        {**json.loads(ch.result_json), "gewinner_ids": [anna.id, ben.id]}
    )
    session.add(ch)
    session.commit()
    login(client, username="anna")

    client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": anna.id})
    client.put(f"/api/challenges/{ch.id}/sieger", json={"user_id": ben.id})
    events = [
        e for e in session.exec(select(FeedEvent)).all() if e.type == "challenge_sieger"
    ]
    assert len(events) == 1
    assert events[0].user_id == ben.id
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -k sieger -v`
Expected: FAIL — 405 Method Not Allowed (Route fehlt)

- [x] **Step 3: Write minimal implementation**

In `backend/app/services/challenges.py` ans Dateiende:

```python
class NichtQualifiziert(ValueError):
    """Sieger steht nicht auf der Liste der Qualifizierten — 422, nicht 409."""


def sieger_id(ch: Challenge) -> int | None:
    return json.loads(ch.result_json or "{}").get("sieger", {}).get("user_id")


def setze_sieger(
    session: Session, ch: Challenge, user_id: int, jetzt: datetime
) -> None:
    """Traegt den offline ermittelten Preistraeger ein. Ueberschreibbar —
    anders als eine Auslosung ist das ein festgehaltener Fakt, und ein
    Vertipper muss sich korrigieren lassen."""
    if ch.mode != "ziel":
        raise ValueError("Ranglisten haben ihren Sieger bereits")
    if ch.status != "beendet":
        raise ValueError("Erst nach dem Ende der Challenge")
    ergebnis = json.loads(ch.result_json or "{}")
    if user_id not in ergebnis.get("gewinner_ids", []):
        raise NichtQualifiziert("Diese Person hat das Ziel nicht erreicht")
    ergebnis["sieger"] = {"user_id": user_id, "gesetzt_am": jetzt.isoformat()}
    ch.result_json = json.dumps(ergebnis)
    session.add(ch)
    session.commit()
    feed.challenge_sieger_event(session, ch, user_id)
```

In `backend/app/services/feed.py` ans Dateiende:

```python
def challenge_sieger_event(session: Session, ch: Challenge, user_id: int) -> None:
    """Bei einer Korrektur wird das vorhandene Event umgeschrieben statt ein
    zweites anzulegen — sonst staenden zwei widersprechende Meldungen im Feed."""
    payload = {
        "challenge_id": ch.id,
        "title": ch.title,
        "prize": ch.prize,
        "user_id": user_id,
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

In `backend/app/routers/challenges.py` bei den Schemas ergänzen:

```python
class SiegerIn(BaseModel):
    user_id: int
```

In `ChallengeOut` zwei Felder ergänzen (nach `gewinner_ids`):

```python
    sieger_id: int | None
    kann_sieger_setzen: bool
```

In `_challenge_out` beim Konstruktoraufruf nach `gewinner_ids=gewinner,`:

```python
        sieger_id=svc.sieger_id(ch),
        kann_sieger_setzen=(
            me.is_admin
            and ch.mode == "ziel"
            and ch.status == "beendet"
            and len(gewinner) > 0
        ),
```

Ans Dateiende von `routers/challenges.py`:

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
    ch = _geladene_challenge(session, challenge_id)
    try:
        svc.setze_sieger(session, ch, data.user_id, datetime.now(timezone.utc))
    except svc.NichtQualifiziert as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    session.refresh(ch)
    return _challenge_out(session, ch, me, date_type.today())
```

Dafür oben in `routers/challenges.py` den Import erweitern:

```python
from datetime import datetime, timezone
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_challenges_api.py -v`
Expected: PASS (23 Tests)

- [x] **Step 5: Commit**

```bash
git add backend/app/services/challenges.py backend/app/services/feed.py backend/app/routers/challenges.py backend/tests/test_challenges_api.py
git commit -m "feat(challenges): Sieger eintragen und korrigieren"
```

---

## Task 12: Backend-Gesamtlauf

**Files:** keine

- [x] **Step 1: Alle Backend-Tests laufen lassen**

Run: `cd backend && uv run pytest`
Expected: PASS — keine Regression in bestehenden Tests. Falls `test_migration.py` fehlschlägt, prüfe, dass du `db.py:migrate()` **nicht** angefasst hast (neue Tabellen brauchen dort nichts).

- [ ] **Step 2: Commit (nur falls Fixes nötig waren)**

```bash
git add -A backend
git commit -m "fix(challenges): Regressionen aus dem Gesamtlauf behoben"
```

---

## Task 13: Frontend-API-Client

**Files:**
- Modify: `frontend/src/api/client.ts`

Reiner Typ- und Methoden-Zuwachs, kein eigener Test — die Nutzung wird in Task 16/17 getestet.

- [x] **Step 1: Typen ergänzen**

In `frontend/src/api/client.ts` vor `export class ApiError` einfügen:

```ts
export type ChallengeStanding = {
  user_id: number
  display_name: string
  avatar: string
  value: number
  rank: number
  geschafft: boolean
  nicht_mehr_schaffbar: boolean
}
export type Challenge = {
  id: number
  title: string
  description: string
  prize: string | null
  creator_id: number
  mode: 'ziel' | 'rangliste'
  target: number | null
  top_n: number
  metric: 'mm' | 'streak' | 'anzahl'
  category_ids: number[]
  streak_min_mm: number
  join_mode: 'auto' | 'opt_in'
  period_start: string
  period_end: string
  status: 'geplant' | 'laufend' | 'beendet' | 'abgebrochen'
  vorlaeufig: boolean
  bin_dabei: boolean
  kann_beitreten: boolean
  standings: ChallengeStanding[]
  mein_stand: ChallengeStanding | null
  gewinner_ids: number[]
  sieger_id: number | null
  kann_sieger_setzen: boolean
  created_at: string
  resolved_at: string | null
}
export type ChallengeInput = {
  title: string
  description?: string
  prize?: string | null
  mode: Challenge['mode']
  target?: number | null
  top_n?: number
  metric: Challenge['metric']
  category_ids?: number[]
  streak_min_mm?: number
  join_mode: Challenge['join_mode']
  period_start: string
  period_end: string
}
```

Den `FeedEvent`-Typ erweitern: `type` um die drei neuen Werte, `payload` um vier Felder.

```ts
  type:
    | 'activity'
    | 'rank_change'
    | 'achievement'
    | 'milestone'
    | 'recap_week'
    | 'recap_month'
    | 'challenge_start'
    | 'challenge_qualified'
    | 'challenge_end'
    | 'challenge_sieger'
```

und im `payload`-Objekt ergänzen:

```ts
    challenge_id?: number
    prize?: string | null
    gewinner_ids?: number[]
    gewinner_namen?: string[]
```

- [x] **Step 2: API-Methoden ergänzen**

Im `api`-Objekt nach `betAchievements:` einfügen:

```ts
  challenges: () => request<Challenge[]>('/api/challenges'),
  challenge: (id: number) => request<Challenge>(`/api/challenges/${id}`),
  joinChallenge: (id: number) =>
    request<Challenge>(`/api/challenges/${id}/join`, { method: 'POST' }),
  leaveChallenge: (id: number) =>
    request<Challenge>(`/api/challenges/${id}/join`, { method: 'DELETE' }),
  createChallenge: (b: ChallengeInput) => request<Challenge>('/api/challenges', post(b)),
  patchChallenge: (id: number, b: Partial<ChallengeInput>) =>
    request<Challenge>(`/api/challenges/${id}`, patch(b)),
  cancelChallenge: (id: number) =>
    request<void>(`/api/challenges/${id}`, { method: 'DELETE' }),
  setChallengeSieger: (id: number, userId: number) =>
    request<Challenge>(`/api/challenges/${id}/sieger`, {
      method: 'PUT',
      body: JSON.stringify({ user_id: userId }),
    }),
```

- [x] **Step 3: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: keine Fehler

- [x] **Step 4: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(challenges): API-Typen und -Methoden im Frontend-Client"
```

---

## Task 14: Formatierhelfer `wertung.ts`

**Files:**
- Create: `frontend/src/components/challenges/wertung.ts`
- Test: `frontend/src/components/challenges/wertung.test.ts`

- [x] **Step 1: Write the failing test**

Neue Datei `frontend/src/components/challenges/wertung.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Challenge } from '../../api/client'
import { einheit, fortschritt, wertungText } from './wertung'

const basis: Challenge = {
  id: 1, title: 'T', description: '', prize: null, creator_id: 1,
  mode: 'ziel', target: 300, top_n: 1, metric: 'mm', category_ids: [],
  streak_min_mm: 5, join_mode: 'auto',
  period_start: '2026-08-04', period_end: '2026-08-31',
  status: 'laufend', vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
  standings: [], mein_stand: null, gewinner_ids: [],
  sieger_id: null, kann_sieger_setzen: false,
  created_at: '2026-08-01T10:00:00Z', resolved_at: null,
}

describe('wertung', () => {
  it('benennt die Einheit je Metrik', () => {
    expect(einheit('mm')).toBe('MM')
    expect(einheit('streak')).toBe('Tage')
    expect(einheit('anzahl')).toBe('Aktivitäten')
  })

  it('beschreibt eine Ziel-Challenge im Klartext', () => {
    expect(wertungText(basis, [])).toBe('Ziel: 300 MM aus allen Sportarten')
  })

  it('nennt die gefilterten Kategorien', () => {
    const ch = { ...basis, category_ids: [2] }
    expect(wertungText(ch, [{ id: 2, name: 'Joggen' }])).toBe('Ziel: 300 MM aus Joggen')
  })

  it('beschreibt eine Streak-Challenge mit Tagesminimum', () => {
    const ch: Challenge = { ...basis, metric: 'streak', target: 10, streak_min_mm: 6 }
    expect(wertungText(ch, [])).toBe(
      'Ziel: 10 Tage am Stück mit mindestens 6 MM aus allen Sportarten',
    )
  })

  it('beschreibt eine Rangliste', () => {
    const ch: Challenge = { ...basis, mode: 'rangliste', target: null, top_n: 3 }
    expect(wertungText(ch, [])).toBe('Rangliste: meiste MM aus allen Sportarten, Top 3')
  })

  it('rechnet den Fortschritt und deckelt bei 1', () => {
    expect(fortschritt(basis, 150)).toBeCloseTo(0.5)
    expect(fortschritt(basis, 600)).toBe(1)
    expect(fortschritt({ ...basis, mode: 'rangliste', target: null }, 42)).toBe(0)
  })
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/challenges/wertung.test.ts`
Expected: FAIL — `Failed to resolve import "./wertung"`

- [x] **Step 3: Write minimal implementation**

Neue Datei `frontend/src/components/challenges/wertung.ts`:

```ts
import type { Challenge } from '../../api/client'

export type KategorieName = { id: number; name: string }

export function einheit(metric: Challenge['metric']): string {
  if (metric === 'streak') return 'Tage'
  if (metric === 'anzahl') return 'Aktivitäten'
  return 'MM'
}

function kategorienText(ch: Challenge, kategorien: KategorieName[]): string {
  if (ch.category_ids.length === 0) return 'allen Sportarten'
  const namen = ch.category_ids
    .map((id) => kategorien.find((k) => k.id === id)?.name)
    .filter((n): n is string => !!n)
  return namen.length > 0 ? namen.join(' und ') : 'ausgewählten Sportarten'
}

/** Menschenlesbare Beschreibung der Wertung, z.B. "Ziel: 300 MM aus allen Sportarten". */
export function wertungText(ch: Challenge, kategorien: KategorieName[]): string {
  const aus = `aus ${kategorienText(ch, kategorien)}`
  if (ch.mode === 'rangliste') {
    const was =
      ch.metric === 'streak'
        ? 'längste Serie'
        : ch.metric === 'anzahl'
          ? 'meiste Aktivitäten'
          : 'meiste MM'
    return `Rangliste: ${was} ${aus}, Top ${ch.top_n}`
  }
  if (ch.metric === 'streak') {
    return `Ziel: ${ch.target} Tage am Stück mit mindestens ${ch.streak_min_mm} MM ${aus}`
  }
  return `Ziel: ${ch.target} ${einheit(ch.metric)} ${aus}`
}

/** 0..1 für den Fortschrittsbalken. Ranglisten haben keine Schwelle → 0. */
export function fortschritt(ch: Challenge, wert: number): number {
  if (ch.mode !== 'ziel' || !ch.target) return 0
  return Math.min(wert / ch.target, 1)
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/challenges/wertung.test.ts`
Expected: PASS (6 Tests)

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/challenges/wertung.ts frontend/src/components/challenges/wertung.test.ts
git commit -m "feat(challenges): Formatierhelfer fuer Wertungstext und Fortschritt"
```

---

## Task 15: Tab und Route

**Files:**
- Modify: `frontend/src/components/ui/tabs.ts`, `frontend/src/App.tsx`
- Test: `frontend/src/components/ui/tabs.test.ts`

Die Seite `pages/Challenges.tsx` entsteht erst in Task 16 — lege in diesem Task einen minimalen Platzhalter an, damit der Build durchläuft, und fülle ihn dort.

- [x] **Step 1: Write the failing test**

Ans Ende von `frontend/src/components/ui/tabs.test.ts` (innerhalb des bestehenden `describe`-Blocks):

```ts
  it('zeigt den Challenges-Tab nur bei aktivem Add-on', () => {
    const ohne = sichtbareTabs(TABS, {
      isAdmin: false, gestartet: true, aktiveAddons: new Set<string>(),
    })
    expect(ohne.find((t) => t.to === '/challenges')).toBeUndefined()
    const mit = sichtbareTabs(TABS, {
      isAdmin: false, gestartet: true, aktiveAddons: new Set(['challenges']),
    })
    expect(mit.find((t) => t.to === '/challenges')?.label).toBe('Challenges')
  })
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/ui/tabs.test.ts`
Expected: FAIL — `expected undefined to be 'Challenges'`

- [x] **Step 3: Write minimal implementation**

In `frontend/src/components/ui/tabs.ts` einen Eintrag in `TABS` einfügen, direkt vor dem Wetten-Eintrag:

```ts
  { to: '/challenges', label: 'Challenges', icon: 'pokal', end: false, adminOnly: false, abStart: false, addon: 'challenges' },
```

Neue Datei `frontend/src/pages/Challenges.tsx` (Platzhalter, wird in Task 16 gefüllt):

```tsx
export default function Challenges() {
  return <div className="mx-auto max-w-xl" />
}
```

In `frontend/src/App.tsx` den Import ergänzen (nach `import Admin from './pages/Admin'`):

```tsx
import Challenges from './pages/Challenges'
```

und im eingeloggten `<Routes>`-Block nach der `/aktivitaeten`-Route:

```tsx
        <Route path="/challenges" element={<Challenges />} />
```

- [x] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/ui/tabs.test.ts && npx tsc -b`
Expected: PASS und keine Typfehler

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/ui/tabs.ts frontend/src/components/ui/tabs.test.ts frontend/src/App.tsx frontend/src/pages/Challenges.tsx
git commit -m "feat(challenges): Tab und Route hinter dem Add-on challenges"
```

---

## Task 16: Übersichtsseite

**Files:**
- Create: `frontend/src/components/challenges/ChallengeHeroCard.tsx`, `ChallengeInvite.tsx`, `ChallengeRow.tsx`
- Modify: `frontend/src/pages/Challenges.tsx`
- Test: `frontend/src/pages/Challenges.test.tsx`

Vier Abschnitte in dieser Reihenfolge: „Du bist dabei" (wischbare Hero-Karten, nach `period_end` aufsteigend), „Mitmachen?" (gestrichelter Einladungsblock), „Geplant", „Beendet".

- [ ] **Step 1: Write the failing test**

Neue Datei `frontend/src/pages/Challenges.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Challenges from './Challenges'

const { challenges, joinChallenge } = vi.hoisted(() => ({
  joinChallenge: vi.fn().mockResolvedValue({}),
  challenges: [
    {
      id: 1, title: 'August bis Stuttgartlauf', description: '', prize: 'Startplatz',
      creator_id: 1, mode: 'ziel', target: 300, top_n: 1, metric: 'mm',
      category_ids: [], streak_min_mm: 5, join_mode: 'auto',
      period_start: '2026-08-04', period_end: '2026-08-31', status: 'laufend',
      vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
      standings: [
        { user_id: 1, display_name: 'Anna', avatar: '🦊', value: 187, rank: 1, geschafft: false, nicht_mehr_schaffbar: false },
      ],
      mein_stand: { user_id: 1, display_name: 'Anna', avatar: '🦊', value: 187, rank: 1, geschafft: false, nicht_mehr_schaffbar: false },
      gewinner_ids: [], created_at: '2026-08-01T10:00:00Z', resolved_at: null,
    },
    {
      id: 2, title: 'Radler-Monat', description: '', prize: 'Kuchen',
      creator_id: 1, mode: 'ziel', target: 200, top_n: 1, metric: 'mm',
      category_ids: [], streak_min_mm: 5, join_mode: 'opt_in',
      period_start: '2026-08-04', period_end: '2026-08-31', status: 'laufend',
      vorlaeufig: false, bin_dabei: false, kann_beitreten: true,
      standings: [], mein_stand: null, gewinner_ids: [],
      created_at: '2026-08-01T10:00:00Z', resolved_at: null,
    },
    {
      id: 3, title: 'Juli-Sprint', description: '', prize: null,
      creator_id: 1, mode: 'ziel', target: 100, top_n: 1, metric: 'mm',
      category_ids: [], streak_min_mm: 5, join_mode: 'auto',
      period_start: '2026-07-01', period_end: '2026-07-31', status: 'beendet',
      vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
      standings: [
        { user_id: 2, display_name: 'Ben', avatar: '🐻', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
      ],
      mein_stand: null,
      gewinner_ids: [2], created_at: '2026-07-01T10:00:00Z',
      resolved_at: '2026-08-01T04:00:00Z',
    },
  ],
}))

vi.mock('../api/client', () => ({
  api: {
    challenges: vi.fn().mockResolvedValue(challenges),
    categories: vi.fn().mockResolvedValue([]),
    joinChallenge,
    leaveChallenge: vi.fn(),
  },
}))

function renderSeite() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Challenges />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Challenges', () => {
  it('trennt Teilnahme, Einladung und Beendetes', async () => {
    renderSeite()
    await waitFor(() =>
      expect(screen.getByText('August bis Stuttgartlauf')).toBeInTheDocument(),
    )
    expect(screen.getByText('Du bist dabei')).toBeInTheDocument()
    expect(screen.getByText('Mitmachen?')).toBeInTheDocument()
    expect(screen.getByText('Beendet')).toBeInTheDocument()
    expect(screen.getByText(/187/)).toBeInTheDocument()
    expect(screen.getByText(/Startplatz/)).toBeInTheDocument()
    // Gewinner der beendeten Challenge
    expect(screen.getByText(/Ben/)).toBeInTheDocument()
  })

  it('tritt einer offenen Challenge bei', async () => {
    renderSeite()
    await waitFor(() => expect(screen.getByText('Radler-Monat')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Beitreten' }))
    await waitFor(() => expect(joinChallenge).toHaveBeenCalledWith(2))
  })

  it('zeigt einen Hinweis, wenn es nichts gibt', async () => {
    const { api } = await import('../api/client')
    vi.mocked(api.challenges).mockResolvedValueOnce([])
    renderSeite()
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Challenges/)).toBeInTheDocument(),
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Challenges.test.tsx`
Expected: FAIL — `Unable to find an element with the text: August bis Stuttgartlauf`

- [ ] **Step 3: Write minimal implementation**

Neue Datei `frontend/src/components/challenges/ChallengeHeroCard.tsx`:

```tsx
import { Link } from 'react-router-dom'
import type { Challenge } from '../../api/client'
import { einheit, fortschritt } from './wertung'

function restTage(bis: string): number {
  const ende = new Date(`${bis}T23:59:59`)
  return Math.max(Math.ceil((ende.getTime() - Date.now()) / 86_400_000), 0)
}

export default function ChallengeHeroCard({ ch }: { ch: Challenge }) {
  const meins = ch.mein_stand
  const wert = meins?.value ?? 0
  const pct = Math.round(fortschritt(ch, wert) * 100)
  return (
    <Link
      to={`/challenges/${ch.id}`}
      className="block min-w-[86%] shrink-0 snap-start rounded-2xl border-2 border-accent bg-card p-4"
    >
      <p className="text-[10px] font-bold uppercase tracking-widest text-accent">
        {ch.vorlaeufig ? 'Endstand vorläufig' : `noch ${restTage(ch.period_end)} Tage`}
      </p>
      <h3 className="mt-1 text-lg font-extrabold text-ink">{ch.title}</h3>
      <p className="mt-1.5 text-2xl font-extrabold text-ink">
        {wert}
        {ch.mode === 'ziel' && ch.target !== null && (
          <span className="text-sm font-semibold text-ink-mute">
            {' '}
            / {ch.target} {einheit(ch.metric)}
          </span>
        )}
      </p>
      {ch.mode === 'ziel' && (
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-line">
          <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
        </div>
      )}
      {meins && (
        <p className="mt-1 text-[11px] text-ink-mute">
          Platz {meins.rank} von {ch.standings.length}
        </p>
      )}
      {ch.prize && (
        <p className="mt-2 inline-block rounded-full bg-line px-2 py-0.5 text-[11px] font-semibold text-ink">
          🎁 {ch.prize}
        </p>
      )}
    </Link>
  )
}
```

Neue Datei `frontend/src/components/challenges/ChallengeInvite.tsx`:

```tsx
import type { Challenge } from '../../api/client'

export default function ChallengeInvite({
  ch,
  onJoin,
  busy,
}: {
  ch: Challenge
  onJoin: () => void
  busy: boolean
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-dashed border-accent bg-card p-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-ink">{ch.title}</p>
        <p className="mt-0.5 text-[11px] text-ink-mute">
          {ch.prize ? `🎁 ${ch.prize} · ` : ''}
          bis {new Date(ch.period_end).toLocaleDateString('de-DE')}
        </p>
      </div>
      <button
        onClick={onJoin}
        disabled={busy}
        className="shrink-0 rounded-full border border-accent px-3 py-1 text-[11px] font-bold text-accent disabled:opacity-50"
      >
        Beitreten
      </button>
    </div>
  )
}
```

Neue Datei `frontend/src/components/challenges/ChallengeRow.tsx`:

```tsx
import { Link } from 'react-router-dom'
import type { Challenge } from '../../api/client'

export default function ChallengeRow({ ch }: { ch: Challenge }) {
  const gewinner = ch.standings
    .filter((s) => ch.gewinner_ids.includes(s.user_id))
    .map((s) => s.display_name)
  return (
    <Link
      to={`/challenges/${ch.id}`}
      className="flex items-center gap-2 border-b border-line px-3 py-2.5 text-sm last:border-b-0"
    >
      <span className="min-w-0 flex-1 truncate text-ink">{ch.title}</span>
      <span className="shrink-0 font-bold text-ink-mute">
        {ch.status === 'beendet'
          ? gewinner.length > 0
            ? `${gewinner.join(', ')} 🏆`
            : 'niemand'
          : new Date(ch.period_start).toLocaleDateString('de-DE')}
      </span>
    </Link>
  )
}
```

`frontend/src/pages/Challenges.tsx` ersetzen:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Challenge } from '../api/client'
import ChallengeHeroCard from '../components/challenges/ChallengeHeroCard'
import ChallengeInvite from '../components/challenges/ChallengeInvite'
import ChallengeRow from '../components/challenges/ChallengeRow'

function Abschnitt({ titel, children }: { titel: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="px-1 text-[11px] font-bold uppercase tracking-wider text-ink-mute">
        {titel}
      </h2>
      {children}
    </section>
  )
}

export default function Challenges() {
  const queryClient = useQueryClient()
  const { data: alle = [], error } = useQuery({
    queryKey: ['challenges'],
    queryFn: api.challenges,
  })
  const join = useMutation({
    mutationFn: (id: number) => api.joinChallenge(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['challenges'] }),
  })

  const nachEnde = (a: Challenge, b: Challenge) =>
    a.period_end.localeCompare(b.period_end)
  const dabei = alle.filter((c) => c.status === 'laufend' && c.bin_dabei).sort(nachEnde)
  const offen = alle.filter((c) => c.kann_beitreten && c.status === 'laufend')
  const geplant = alle.filter((c) => c.status === 'geplant').sort(nachEnde)
  const beendet = alle
    .filter((c) => c.status === 'beendet')
    .sort((a, b) => b.period_end.localeCompare(a.period_end))

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (alle.length === 0)
    return (
      <p className="p-8 text-center text-sm text-ink-mute">
        Noch keine Challenges — der Admin legt die erste an.
      </p>
    )

  return (
    <div className="mx-auto max-w-xl space-y-5">
      {dabei.length > 0 && (
        <Abschnitt titel="Du bist dabei">
          <div className="flex snap-x snap-mandatory gap-2 overflow-x-auto pb-1">
            {dabei.map((ch) => (
              <ChallengeHeroCard key={ch.id} ch={ch} />
            ))}
          </div>
        </Abschnitt>
      )}
      {offen.length > 0 && (
        <Abschnitt titel="Mitmachen?">
          {offen.map((ch) => (
            <ChallengeInvite
              key={ch.id}
              ch={ch}
              busy={join.isPending}
              onJoin={() => join.mutate(ch.id)}
            />
          ))}
        </Abschnitt>
      )}
      {geplant.length > 0 && (
        <Abschnitt titel="Geplant">
          <div className="rounded-2xl border border-line bg-card">
            {geplant.map((ch) => (
              <ChallengeRow key={ch.id} ch={ch} />
            ))}
          </div>
        </Abschnitt>
      )}
      {beendet.length > 0 && (
        <Abschnitt titel="Beendet">
          <div className="rounded-2xl border border-line bg-card opacity-70">
            {beendet.map((ch) => (
              <ChallengeRow key={ch.id} ch={ch} />
            ))}
          </div>
        </Abschnitt>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Challenges.test.tsx`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Challenges.tsx frontend/src/pages/Challenges.test.tsx frontend/src/components/challenges
git commit -m "feat(challenges): Uebersichtsseite mit Hero-Karten und Einladungen"
```

---

## Task 17: Detailansicht

**Files:**
- Create: `frontend/src/components/challenges/ChallengeDetail.tsx`, `ChallengeDetail.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the failing test**

Neue Datei `frontend/src/components/challenges/ChallengeDetail.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ChallengeDetail from './ChallengeDetail'

const { detail } = vi.hoisted(() => ({
  detail: {
    id: 1, title: 'August bis Stuttgartlauf', description: '', prize: 'Startplatz',
    creator_id: 1, mode: 'ziel', target: 300, top_n: 1, metric: 'mm',
    category_ids: [], streak_min_mm: 5, join_mode: 'auto',
    period_start: '2026-08-04', period_end: '2026-08-31', status: 'laufend',
    vorlaeufig: true, bin_dabei: true, kann_beitreten: false,
    standings: [
      { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
      { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 187, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
      { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 14, rank: 3, geschafft: false, nicht_mehr_schaffbar: true },
    ],
    mein_stand: { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
    gewinner_ids: [1], created_at: '2026-08-01T10:00:00Z', resolved_at: null,
  },
}))

vi.mock('../../api/client', () => ({
  api: {
    challenge: vi.fn().mockResolvedValue(detail),
    categories: vi.fn().mockResolvedValue([]),
    joinChallenge: vi.fn(),
    leaveChallenge: vi.fn(),
  },
}))

describe('ChallengeDetail', () => {
  it('zeigt Wertung, Vorlaeufig-Hinweis und alle drei Zustaende', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/challenges/1']}>
          <Routes>
            <Route path="/challenges/:id" element={<ChallengeDetail />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.getByText('August bis Stuttgartlauf')).toBeInTheDocument(),
    )
    expect(screen.getByText('Ziel: 300 MM aus allen Sportarten')).toBeInTheDocument()
    expect(screen.getByText(/vorläufig/i)).toBeInTheDocument()
    expect(screen.getByText('geschafft')).toBeInTheDocument()
    expect(screen.getByText('noch 113')).toBeInTheDocument()
    expect(screen.getByText('nicht mehr')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx`
Expected: FAIL — `Failed to resolve import "./ChallengeDetail"`

- [ ] **Step 3: Write minimal implementation**

Neue Datei `frontend/src/components/challenges/ChallengeDetail.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Challenge, ChallengeStanding } from '../../api/client'
import Avatar from '../ui/Avatar'
import { einheit, fortschritt, wertungText } from './wertung'

function Chip({ ch, s }: { ch: Challenge; s: ChallengeStanding }) {
  // Das Theme hat keine Erfolgsfarbe (nur accent/danger/line) — "geschafft"
  // wird deshalb ueber die gefuellte Akzentflaeche markiert, nicht ueber Gruen.
  if (ch.mode === 'rangliste')
    return (
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
          s.geschafft
            ? 'bg-accent text-accent-ink'
            : 'border border-line text-ink-mute'
        }`}
      >
        Platz {s.rank}
      </span>
    )
  if (s.geschafft)
    return (
      <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold text-accent-ink">
        geschafft
      </span>
    )
  if (s.nicht_mehr_schaffbar)
    return (
      <span className="shrink-0 rounded-full border border-danger px-2 py-0.5 text-[10px] font-bold text-danger">
        nicht mehr
      </span>
    )
  const rest = Math.max((ch.target ?? 0) - s.value, 0)
  return (
    <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
      noch {Math.round(rest * 100) / 100}
    </span>
  )
}

export default function ChallengeDetail() {
  const { id } = useParams()
  const challengeId = Number(id)
  const queryClient = useQueryClient()
  const { data: ch, error } = useQuery({
    queryKey: ['challenge', challengeId],
    queryFn: () => api.challenge(challengeId),
  })
  const { data: kategorien = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: api.categories,
  })
  const austreten = useMutation({
    mutationFn: () => api.leaveChallenge(challengeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenge', challengeId] })
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
  })

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (!ch) return <p className="p-8 text-sm text-ink-mute">Lädt…</p>

  const hoechster = Math.max(...ch.standings.map((s) => s.value), 1)
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <header className="rounded-2xl border border-line bg-card p-4">
        <h1 className="text-lg font-extrabold text-ink">{ch.title}</h1>
        <p className="mt-1 text-[11px] text-ink-mute">
          {new Date(ch.period_start).toLocaleDateString('de-DE')} –{' '}
          {new Date(ch.period_end).toLocaleDateString('de-DE')} ·{' '}
          {ch.join_mode === 'auto' ? 'alle automatisch dabei' : 'Beitritt nötig'}
        </p>
        <p className="mt-1 text-xs text-ink-soft">{wertungText(ch, kategorien)}</p>
        {ch.description && (
          <p className="mt-2 text-xs text-ink-soft">{ch.description}</p>
        )}
        {ch.prize && (
          <p className="mt-2 inline-block rounded-full bg-line px-2 py-0.5 text-[11px] font-semibold text-ink">
            🎁 {ch.prize}
          </p>
        )}
        {ch.vorlaeufig && (
          <p className="mt-2 rounded-xl border border-accent/40 bg-accent/10 px-3 py-1.5 text-[11px] text-ink">
            ⏱ Zeitraum vorbei — vorläufiges Ergebnis, Nachzügler zählen noch bis
            morgen früh.
          </p>
        )}
        {ch.bin_dabei && ch.join_mode === 'opt_in' && ch.status !== 'beendet' && (
          <button
            onClick={() => austreten.mutate()}
            disabled={austreten.isPending}
            className="mt-3 rounded-full border border-line px-3 py-1 text-[11px] font-bold text-ink-mute disabled:opacity-50"
          >
            Austreten
          </button>
        )}
      </header>

      <section className="space-y-1.5">
        {ch.standings.map((s) => (
          <div
            key={s.user_id}
            className={`rounded-xl border border-line bg-card p-2.5 ${
              s.nicht_mehr_schaffbar ? 'opacity-60' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              <Avatar value={s.avatar} size="sm" />
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
                {s.display_name}
              </span>
              <Chip ch={ch} s={s} />
              <span className="shrink-0 text-xs font-extrabold text-ink">
                {s.value} {einheit(ch.metric)}
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className={`h-full ${
                  s.nicht_mehr_schaffbar ? 'bg-ink-mute' : 'bg-accent'
                }`}
                style={{
                  width: `${
                    ch.mode === 'ziel'
                      ? fortschritt(ch, s.value) * 100
                      : (s.value / hoechster) * 100
                  }%`,
                }}
              />
            </div>
          </div>
        ))}
        {ch.standings.length === 0 && (
          <p className="p-6 text-center text-sm text-ink-mute">
            Noch niemand dabei.
          </p>
        )}
      </section>
    </div>
  )
}
```

In `frontend/src/App.tsx` den Import ergänzen:

```tsx
import ChallengeDetail from './components/challenges/ChallengeDetail'
```

und die Route direkt nach `/challenges`:

```tsx
        <Route path="/challenges/:id" element={<ChallengeDetail />} />
```

Verfügbare Theme-Farben laut `frontend/src/index.css`: `surface`, `card`, `line`, `accent`, `accent-ink`, `ink`, `ink-soft`, `ink-mute`, `ink-tech`, `danger`. Es gibt **keine** Erfolgsfarbe — erfinde keine, der Code oben nutzt bewusst nur diese.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/challenges/ChallengeDetail.tsx frontend/src/components/challenges/ChallengeDetail.test.tsx frontend/src/App.tsx
git commit -m "feat(challenges): Detailansicht mit Teilnehmerliste und Zustands-Chips"
```

---

## Task 17a: Siegerband in der Detailansicht

**Files:**
- Modify: `frontend/src/components/challenges/ChallengeDetail.tsx`
- Test: `frontend/src/components/challenges/ChallengeDetail.test.tsx`

- [ ] **Step 1: Write the failing test**

Ans Ende von `frontend/src/components/challenges/ChallengeDetail.test.tsx`, und den `vi.mock`-Block oben um `setChallengeSieger: vi.fn().mockResolvedValue({})` erweitern:

```tsx
  it('laesst den Admin den Sieger eintragen', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...detail,
      status: 'beendet',
      vorlaeufig: false,
      gewinner_ids: [1, 2],
      sieger_id: null,
      kann_sieger_setzen: true,
      standings: [
        { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
        { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 320, rank: 2, geschafft: true, nicht_mehr_schaffbar: false },
      ],
    })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/challenges/1']}>
          <Routes>
            <Route path="/challenges/:id" element={<ChallengeDetail />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Sieger eintragen' })).toBeInTheDocument(),
    )
    fireEvent.change(screen.getByLabelText('Sieger'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sieger eintragen' }))
    await waitFor(() => expect(api.setChallengeSieger).toHaveBeenCalledWith(1, 2))
  })

  it('zeigt den eingetragenen Sieger allen', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...detail,
      status: 'beendet',
      vorlaeufig: false,
      gewinner_ids: [1],
      sieger_id: 1,
      kann_sieger_setzen: false,
    })
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/challenges/1']}>
          <Routes>
            <Route path="/challenges/:id" element={<ChallengeDetail />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByText(/Sieger: Rick/)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Sieger eintragen' })).toBeNull()
  })
```

Der Import in der Testdatei muss `fireEvent` mit aufnehmen:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "button" and name "Sieger eintragen"`

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/challenges/ChallengeDetail.tsx` den Import von `useState` und `Select` ergänzen:

```tsx
import { useState } from 'react'
import Select from '../ui/Select'
```

Im Komponentenrumpf nach der `austreten`-Mutation einfügen:

```tsx
  const [wahl, setWahl] = useState<number | null>(null)
  const siegerSetzen = useMutation({
    mutationFn: (userId: number) => api.setChallengeSieger(challengeId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenge', challengeId] })
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
  })
```

Direkt nach dem `</header>` einfügen:

```tsx
      {ch.status === 'beendet' && ch.mode === 'ziel' && (
        <section className="rounded-2xl border border-accent bg-card p-3">
          {ch.sieger_id !== null ? (
            <p className="text-sm font-bold text-ink">
              🏆 Sieger:{' '}
              {ch.standings.find((s) => s.user_id === ch.sieger_id)?.display_name ??
                'unbekannt'}
              {ch.prize && (
                <span className="font-normal text-ink-mute"> — {ch.prize}</span>
              )}
            </p>
          ) : ch.kann_sieger_setzen ? (
            <div className="flex items-end gap-2">
              <Select
                label="Sieger"
                className="flex-1"
                value={wahl === null ? '' : String(wahl)}
                onChange={(e) => setWahl(Number(e.target.value))}
              >
                <option value="">– bitte wählen –</option>
                {ch.standings
                  .filter((s) => ch.gewinner_ids.includes(s.user_id))
                  .map((s) => (
                    <option key={s.user_id} value={s.user_id}>
                      {s.display_name}
                    </option>
                  ))}
              </Select>
              <button
                onClick={() => wahl !== null && siegerSetzen.mutate(wahl)}
                disabled={wahl === null || siegerSetzen.isPending}
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

Und in der Teilnehmerliste den Namen um die Markierung erweitern — ersetze

```tsx
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
                {s.display_name}
              </span>
```

durch

```tsx
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
                {s.display_name}
                {s.user_id === ch.sieger_id && ' 🏆'}
              </span>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/challenges/ChallengeDetail.test.tsx`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/challenges/ChallengeDetail.tsx frontend/src/components/challenges/ChallengeDetail.test.tsx
git commit -m "feat(challenges): Sieger im Detail eintragen und anzeigen"
```

---

## Task 18: Feed-Darstellung der neuen Events

**Files:**
- Modify: `frontend/src/components/feed/FeedItem.tsx`
- Test: `frontend/src/pages/Feed.test.tsx`

- [ ] **Step 1: Write the failing test**

In `frontend/src/pages/Feed.test.tsx` die `events`-Liste im `vi.hoisted`-Block um drei Einträge erweitern (vor dem schließenden `]`):

```tsx
    {
      id: 6, type: 'challenge_start', user_id: null, display_name: null, avatar: null,
      created_at: new Date().toISOString(),
      payload: { challenge_id: 1, title: 'August bis Stuttgartlauf', prize: 'Startplatz' },
      reactions: [],
    },
    {
      id: 5, type: 'challenge_qualified', user_id: 1, display_name: 'Anna', avatar: '🦊',
      created_at: new Date().toISOString(),
      payload: { challenge_id: 1, title: 'August bis Stuttgartlauf' },
      reactions: [],
    },
    {
      id: 7, type: 'challenge_sieger', user_id: 2, display_name: 'Ben', avatar: '🐻',
      created_at: new Date().toISOString(),
      payload: { challenge_id: 1, title: 'August bis Stuttgartlauf', prize: 'Startplatz', user_id: 2 },
      reactions: [],
    },
    {
      id: 4, type: 'challenge_end', user_id: null, display_name: null, avatar: null,
      created_at: new Date().toISOString(),
      payload: {
        challenge_id: 1, title: 'Juli-Sprint', prize: 'Kuchen',
        gewinner_ids: [2], gewinner_namen: ['Ben'],
      },
      reactions: [],
    },
```

Und ans Ende des `describe`-Blocks:

```tsx
  it('zeigt die vier Challenge-Ereignisse', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <Feed />
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.getByText(/Neue Challenge/)).toBeInTheDocument(),
    )
    expect(screen.getByText(/hat das Ziel geknackt/)).toBeInTheDocument()
    expect(screen.getByText(/Juli-Sprint ist vorbei/)).toBeInTheDocument()
    expect(screen.getByText(/gewinnt/)).toBeInTheDocument()
    expect(screen.getAllByText(/Ben/).length).toBeGreaterThan(0)
  })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/Feed.test.tsx`
Expected: FAIL — `Unable to find an element with the text: /Neue Challenge/`

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/components/feed/FeedItem.tsx` das `TYP_FARBE`-Objekt erweitern:

```tsx
const TYP_FARBE: Record<string, string> = {
  rank_change: '#c084fc',
  achievement: '#fbbf24',
  milestone: '#fbbf24',
  recap_week: '#fbbf24',
  recap_month: '#fbbf24',
  challenge_start: '#34d399',
  challenge_qualified: '#34d399',
  challenge_end: '#34d399',
  challenge_sieger: '#fbbf24',
}
```

Und direkt vor `{(ev.type === 'recap_week' || ev.type === 'recap_month') && <RecapCard ev={ev} />}` einfügen:

```tsx
      {ev.type === 'challenge_start' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏁</span>
          <span className="text-ink">
            Neue Challenge: <b>{ev.payload.title}</b>
            {ev.payload.prize && (
              <span className="text-ink-mute"> · 🎁 {ev.payload.prize}</span>
            )}
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {ev.type === 'challenge_qualified' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>✅</span>
          <span className="text-ink">
            <b>{ev.display_name}</b> hat das Ziel geknackt —{' '}
            <b className="text-accent">{ev.payload.title}</b>
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {ev.type === 'challenge_sieger' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏆</span>
          <span className="text-ink">
            <b>{ev.display_name}</b> gewinnt <b>{ev.payload.title}</b>
            {ev.payload.prize && (
              <span className="text-ink-mute"> · 🎁 {ev.payload.prize}</span>
            )}
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {ev.type === 'challenge_end' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏆</span>
          <span className="text-ink">
            <b>{ev.payload.title}</b> ist vorbei —{' '}
            {ev.payload.gewinner_namen && ev.payload.gewinner_namen.length > 0 ? (
              <>
                <b>{undListe(ev.payload.gewinner_namen)}</b>
                {ev.payload.prize ? ` gewinnt: ${ev.payload.prize}` : ' vorn'}
              </>
            ) : (
              'niemand hat es geschafft'
            )}
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/pages/Feed.test.tsx`
Expected: PASS (3 Tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/feed/FeedItem.tsx frontend/src/pages/Feed.test.tsx
git commit -m "feat(challenges): Feed-Darstellung fuer Start, Qualifikation und Ende"
```

---

## Task 19: Admin-Bereich

**Files:**
- Create: `frontend/src/components/admin/ChallengesAdmin.tsx`
- Modify: `frontend/src/pages/Admin.tsx`

`Admin.tsx` hat bereits 709 Zeilen — der Abschnitt bekommt deshalb eine eigene Datei, `Admin.tsx` nur Import und Aufruf.

- [ ] **Step 1: Komponente anlegen**

Neue Datei `frontend/src/components/admin/ChallengesAdmin.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { Challenge, ChallengeInput } from '../../api/client'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Input from '../ui/Input'
import Select from '../ui/Select'
import { useToast } from '../ui/Toast'

const LEER: ChallengeInput = {
  title: '',
  description: '',
  prize: '',
  mode: 'ziel',
  target: 300,
  top_n: 1,
  metric: 'mm',
  category_ids: [],
  streak_min_mm: 5,
  join_mode: 'auto',
  period_start: '',
  period_end: '',
}

export default function ChallengesAdmin() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState<ChallengeInput>(LEER)
  const { data: alle = [] } = useQuery({
    queryKey: ['challenges'],
    queryFn: api.challenges,
  })
  const { data: kategorien = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: api.categories,
  })
  const anlegen = useMutation({
    mutationFn: (b: ChallengeInput) => api.createChallenge(b),
    onSuccess: () => {
      setForm(LEER)
      toast('Challenge angelegt', 'ok')
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
    onError: (e: Error) => toast(e.message),
  })
  const abbrechen = useMutation({
    mutationFn: (id: number) => api.cancelChallenge(id),
    onSuccess: () => {
      toast('Challenge abgebrochen', 'ok')
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
    onError: (e: Error) => toast(e.message),
  })

  const set = <K extends keyof ChallengeInput>(k: K, v: ChallengeInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  return (
    <Card>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-ink-mute">
        Challenges
      </h2>

      <div className="space-y-2">
        <Input
          label="Titel"
          value={form.title}
          onChange={(e) => set('title', e.target.value)}
        />
        <Input
          label="Beschreibung"
          value={form.description ?? ''}
          onChange={(e) => set('description', e.target.value)}
        />
        <Input
          label="Preis (optional)"
          value={form.prize ?? ''}
          onChange={(e) => set('prize', e.target.value)}
        />
        <div className="grid grid-cols-2 gap-2">
          <Select
            label="Modus"
            value={form.mode}
            onChange={(e) => set('mode', e.target.value as Challenge['mode'])}
          >
            <option value="ziel">Ziel erreichen</option>
            <option value="rangliste">Rangliste</option>
          </Select>
          <Select
            label="Wertung"
            value={form.metric}
            onChange={(e) => set('metric', e.target.value as Challenge['metric'])}
          >
            <option value="mm">MM</option>
            <option value="streak">Streak (Tage am Stück)</option>
            <option value="anzahl">Anzahl Aktivitäten</option>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {form.mode === 'ziel' ? (
            <Input
              label="Ziel"
              type="number"
              value={String(form.target ?? '')}
              onChange={(e) => set('target', Number(e.target.value))}
            />
          ) : (
            <Input
              label="Gewertete Plätze"
              type="number"
              value={String(form.top_n ?? 1)}
              onChange={(e) => set('top_n', Number(e.target.value))}
            />
          )}
          {form.metric === 'streak' && (
            <Input
              label="Tages-Minimum (MM)"
              type="number"
              value={String(form.streak_min_mm ?? 5)}
              onChange={(e) => set('streak_min_mm', Number(e.target.value))}
            />
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Input
            label="Start"
            type="date"
            value={form.period_start}
            onChange={(e) => set('period_start', e.target.value)}
          />
          <Input
            label="Ende"
            type="date"
            value={form.period_end}
            onChange={(e) => set('period_end', e.target.value)}
          />
        </div>
        <Select
          label="Teilnahme"
          value={form.join_mode}
          onChange={(e) => set('join_mode', e.target.value as Challenge['join_mode'])}
        >
          <option value="auto">Alle automatisch dabei</option>
          <option value="opt_in">Beitritt nötig</option>
        </Select>

        <fieldset className="rounded-xl border border-line p-2">
          <legend className="px-1 text-[11px] text-ink-mute">
            Kategorien (keine = alle)
          </legend>
          <div className="flex flex-wrap gap-2">
            {kategorien.map((k) => (
              <label key={k.id} className="flex items-center gap-1 text-xs text-ink">
                <input
                  type="checkbox"
                  checked={(form.category_ids ?? []).includes(k.id)}
                  onChange={(e) =>
                    set(
                      'category_ids',
                      e.target.checked
                        ? [...(form.category_ids ?? []), k.id]
                        : (form.category_ids ?? []).filter((id) => id !== k.id),
                    )
                  }
                />
                {k.name}
              </label>
            ))}
          </div>
        </fieldset>

        <Button
          onClick={() =>
            anlegen.mutate({ ...form, prize: form.prize || null })
          }
          disabled={anlegen.isPending || !form.title || !form.period_start || !form.period_end}
        >
          Challenge anlegen
        </Button>
      </div>

      <ul className="mt-4 space-y-1.5">
        {alle.map((ch) => (
          <li
            key={ch.id}
            className="flex items-center gap-2 rounded-xl border border-line p-2 text-sm"
          >
            <span className="min-w-0 flex-1 truncate text-ink">{ch.title}</span>
            <span className="shrink-0 text-[11px] text-ink-mute">{ch.status}</span>
            {ch.status !== 'beendet' && (
              <button
                onClick={() => abbrechen.mutate(ch.id)}
                className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-mute"
              >
                Abbrechen
              </button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
```

Die verwendeten Signaturen (verifiziert in `frontend/src/components/ui/`):

- `Input`: `React.InputHTMLAttributes<HTMLInputElement> & { label: string }` — `label` ist Pflicht.
- `Select`: `React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }`, Optionen als Children.
- `Button`: `React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' | 'danger' }`.
- `useToast()` liefert **eine Funktion** `(text: string, kind?: 'fehler' | 'ok') => void`. Ohne zweites Argument gilt `'fehler'` — bei Erfolgsmeldungen also `'ok'` mitgeben.

- [ ] **Step 2: In Admin.tsx einhängen**

In `frontend/src/pages/Admin.tsx` den Import ergänzen:

```tsx
import ChallengesAdmin from '../components/admin/ChallengesAdmin'
```

und in der `Admin`-Komponente nach `<AddOns />`:

```tsx
      <ChallengesAdmin />
```

- [ ] **Step 3: Typecheck und Testlauf**

Run: `cd frontend && npx tsc -b && npm test`
Expected: keine Typfehler, alle Tests grün

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/admin/ChallengesAdmin.tsx frontend/src/pages/Admin.tsx
git commit -m "feat(challenges): Admin-Bereich zum Anlegen und Abbrechen"
```

---

## Task 20: Saison-Umbenennung in den Anzeigetexten

**Files:**
- Modify: `frontend/src/pages/Regeln.tsx:25,39,95`, `frontend/src/pages/Datenschutz.tsx:14,49`, `frontend/src/components/ui/CountdownBanner.tsx:20`, `frontend/src/components/comparison/WarmupArchiv.tsx:31`, `frontend/src/pages/Admin.tsx:395,402`
- Modify: `backend/app/services/achievements.py:73,103,116`, `backend/app/routers/achievements.py:339`
- Test: `frontend/src/pages/MeineAktivitaeten.test.tsx:48,51`, `frontend/src/components/ui/tabs.test.ts:26,31,46`

**Code-Bezeichner bleiben unverändert** (`phase="challenge"`, `points.challenge_start()`, `SIDEBETS_START`). Nur deutsche Anzeigetexte werden angefasst.

- [ ] **Step 1: Frontend-Texte ersetzen**

| Datei:Zeile | Alt | Neu |
| --- | --- | --- |
| `pages/Regeln.tsx:25` | „unsere gemeinsame Jahres-Challenge" | „unsere gemeinsame Saison" |
| `pages/Regeln.tsx:39` | „Die Challenge startet am" | „Die Saison startet am" |
| `pages/Regeln.tsx:95` | „seit Challenge-Start" | „seit Saison-Start" |
| `pages/Datenschutz.tsx:14` | „private Fitness-Challenge im Freundeskreis" | „private Fitness-Saison im Freundeskreis" |
| `pages/Datenschutz.tsx:49` | „für die Challenge abzurufen" | „für die Saison abzurufen" |
| `components/ui/CountdownBanner.tsx:20` | „Challenge startet in" | „Saison startet in" |
| `components/comparison/WarmupArchiv.tsx:31` | „nicht für die Challenge" | „nicht für die Saison" |
| `pages/Admin.tsx:395` | `label="Challenge-Start"` | `label="Saison-Start"` |
| `pages/Admin.tsx:402` | `label="Challenge-Ende (leer = offen)"` | `label="Saison-Ende (leer = offen)"` |

- [ ] **Step 2: Backend-Texte ersetzen**

| Datei:Zeile | Alt | Neu |
| --- | --- | --- |
| `services/achievements.py:73` | „alleiniger Platz 1 der Challenge." | „alleiniger Platz 1 der Saison." |
| `services/achievements.py:103` | „am ersten Tag der Challenge eine Aktivität" | „am ersten Tag der Saison eine Aktivität" |
| `services/achievements.py:116` | „Warm-up-Phase zum Challenge-Start." | „Warm-up-Phase zum Saison-Start." |
| `routers/achievements.py:339` | „alleiniger Platz 1 der Challenge." | „alleiniger Platz 1 der Saison." |

- [ ] **Step 3: Klarstellende Kommentare setzen**

Über `def compute_comparison` in `backend/app/routers/comparison.py:35`:

```python
# Hinweis: "challenge" meint hier die SAISON (Jahreswertung), nicht das
# Challenges-Feature aus Spec 2026-08-04. Bezeichner bleiben aus
# Kompatibilitaetsgruenden unveraendert, nur die Anzeigetexte heissen "Saison".
```

Über `def challenge_start` in `backend/app/services/points.py:42` derselbe Kommentar.

- [ ] **Step 4: Tests nachziehen**

In `frontend/src/pages/MeineAktivitaeten.test.tsx:48,51` die erwarteten Beschreibungstexte auf „Saison" anpassen. In `frontend/src/components/ui/tabs.test.ts:26,31,46` die Testnamen von „Challenge-Start" auf „Saison-Start" ändern (nur Namen, keine Logik).

- [ ] **Step 5: Prüfen, dass nichts übersehen wurde**

Run: `grep -rn "Challenge" frontend/src backend/app --include=*.tsx --include=*.ts --include=*.py | grep -v "challenges" | grep -v "Challenges"`
Expected: nur noch Code-Kommentare und Bezeichner (`phase="challenge"`, `challenge_start`, `SIDEBETS_START`), keine Anzeigetexte mehr.

- [ ] **Step 6: Gesamtlauf**

Run: `cd backend && uv run pytest && cd ../frontend && npm test && npx tsc -b`
Expected: alles grün

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(saison): Anzeigetexte von Challenge auf Saison umbenannt"
```

---

## Task 21: Abschluss

**Files:** keine

- [ ] **Step 1: Vollständiger Lauf**

```bash
cd backend && uv run pytest
cd ../frontend && npm test && npx tsc -b && npm run lint
```
Expected: alles grün

- [ ] **Step 2: Manuelle Sichtprüfung**

Backend starten, im Admin das Add-on `challenges` einschalten, die August-Challenge anlegen:

- Titel „August bis Stuttgartlauf"
- Modus „Ziel erreichen", Ziel `300`, Wertung „MM", keine Kategorie ausgewählt
- Teilnahme „Alle automatisch dabei"
- Zeitraum 04.08.2026 – 31.08.2026
- Preis „Verlosung eines Startplatzes"

Prüfen: Tab erscheint, Hero-Karte zeigt den eigenen Stand, Detailansicht listet alle Mitglieder, Feed zeigt „Neue Challenge".

Den Sieger-Eintrag kannst du erst nach dem Ende einer Challenge testen. Zum Durchspielen eine Wegwerf-Challenge mit `period_end` von gestern anlegen ist **nicht** möglich (422) — setze stattdessen bei einer bestehenden das `period_end` in der DB zurück, oder verlasse dich auf `test_sieger_eintragen_und_korrigieren` aus Task 11a.

- [ ] **Step 3: Push und PR**

```bash
git push -u origin feature/challenges
gh pr create --title "feat: Challenges" --body "Setzt docs/superpowers/specs/2026-08-04-challenges-design.md um.

Zeitlich begrenzte Wettbewerbe mit Ziel- und Ranglisten-Modus, Metriken
MM/Streak/Anzahl mit Kategorie-Filter, auto- und opt-in-Teilnahme.
Stand wird zur Lesezeit gerechnet, Ergebnis friert am Folgetag um 06:00
deutscher Zeit ein. Bei Ziel-Challenges traegt der Admin den offline
ermittelten Sieger ein. Feed-Anbindung, Admin-Verwaltung,
Saison-Umbenennung in den Anzeigetexten.

Nach dem Merge: Add-on 'sidebets' im Admin ausschalten, Add-on
'challenges' einschalten, August-Challenge anlegen.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

---

## Nach dem Merge

1. VPS: `git pull` (niemals lokal auf dem Server committen — bricht `git pull --ff-only`)
2. Im Admin: Add-on **`sidebets` ausschalten**, Add-on **`challenges` einschalten**
3. August-Challenge anlegen (Werte siehe Task 21, Step 2)
