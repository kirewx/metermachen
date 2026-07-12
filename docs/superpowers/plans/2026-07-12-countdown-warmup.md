# Countdown & Warm-up-Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Challenge-Start am 20.07.2026 mit Countdown-Banner; Warm-up-KM wandern ab Start ins Archiv (mit Warm-up-Achievements), Admin kann pro Mitglied einen KM-Faktor setzen.

**Architektur:** `Season.start_date` steuert alles datumsbasiert (kein Cron, kein Statusfeld): Vergleich filtert ab Start auf `date >= start_date`, Archiv-Endpoint filtert auf `< start_date`. `User.km_factor` wird nur im Vergleich multipliziert. Frontend: Banner in `Layout`, neue Archiv-Route.

**Tech Stack:** FastAPI + SQLModel + SQLite (Migrations handgerollt in `db.py`), React + TanStack Query + Tailwind, pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-07-12-countdown-warmup-sidebets-design.md`

**Auslieferung:** Direkt auf `main` committen; Push erst am Ende (Auto-Deploy!).

**Arbeitsverzeichnis Backend-Tests:** `cd backend` dann `.venv\Scripts\python -m pytest tests/ -v` (Windows).

---

### Task 1: `Season.start_date` (Model, Migration, Schemas, Router)

**Files:**
- Modify: `backend/app/models.py` (Season, Zeile ~60)
- Modify: `backend/app/db.py` (migrate())
- Modify: `backend/app/schemas.py` (SeasonCreate/Patch/Out)
- Modify: `backend/app/routers/seasons.py`
- Test: `backend/tests/test_seasons.py`, `backend/tests/test_migration.py`

- [ ] **Step 1: Failing Tests schreiben**

In `backend/tests/test_seasons.py` ergänzen:

```python
def test_season_start_date_roundtrip(client, session):
    from tests.conftest import make_user, login
    make_user(session, is_admin=True)
    login(client)
    r = client.post("/api/seasons", json={
        "year": 2031, "goal_km": 1000, "start_date": "2031-07-20",
    })
    assert r.status_code == 201
    assert r.json()["start_date"] == "2031-07-20"
    sid = r.json()["id"]
    r = client.patch(f"/api/seasons/{sid}", json={"start_date": None})
    assert r.json()["start_date"] is None
```

In `backend/tests/test_migration.py` ergänzen (bestehendes Muster der Datei übernehmen — Alt-Schema anlegen, `migrate()` laufen lassen):

```python
def test_migration_adds_season_start_date_and_backfills_2026(tmp_path):
    from sqlalchemy import text
    from sqlmodel import create_engine
    from app.db import migrate

    engine = create_engine(f"sqlite:///{tmp_path/'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE season (id INTEGER PRIMARY KEY, year INTEGER, "
            "goal_km FLOAT, milestones_json TEXT)"
        ))
        conn.execute(text(
            "INSERT INTO season (year, goal_km, milestones_json) VALUES (2026, 1000, '[]')"
        ))
    migrate(engine)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT start_date FROM season WHERE year=2026")).fetchone()
    assert row[0] == "2026-07-20"
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd backend && .venv\Scripts\python -m pytest tests/test_seasons.py tests/test_migration.py -v`
Expected: FAIL (unbekanntes Feld `start_date` / Spalte fehlt)

- [ ] **Step 3: Implementieren**

`models.py`, Season ergänzen:

```python
class Season(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    year: int = Field(unique=True)
    goal_km: float
    milestones_json: str = "[]"
    start_date: date_type | None = None  # Challenge-Start; None = ab 1.1.
```

`db.py`, in `migrate()` nach dem Season-Milestones-Block:

```python
        if _table_exists(conn, "season"):
            season_cols = _columns(conn, "season")
            if "start_date" not in season_cols:
                conn.execute(text("ALTER TABLE season ADD COLUMN start_date DATE"))
                # Einmaliger Backfill: Challenge 2026 startet am 20.07.
                conn.execute(text(
                    "UPDATE season SET start_date = '2026-07-20' WHERE year = 2026"
                ))
```

`schemas.py`: `SeasonCreate` + `SeasonPatch` + `SeasonOut` bekommen `start_date: date_type | None = None`; in `SeasonOut.from_season` `start_date=season.start_date` ergänzen. Achtung bei `SeasonPatch`: `None` heißt hier auch „löschen" — dafür `model_fields_set` prüfen:

```python
# seasons.py, patch_season:
    if "start_date" in data.model_fields_set:
        season.start_date = data.start_date
```

`seasons.py`, `create_season`: `start_date=data.start_date` mitgeben.

- [ ] **Step 4: Tests grün**

Run: `cd backend && .venv\Scripts\python -m pytest tests/ -v`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat: Season.start_date mit Migration und 2026-Backfill"
```

---

### Task 2: `User.km_factor` (Model, Migration, Admin-API)

**Files:**
- Modify: `backend/app/models.py` (User)
- Modify: `backend/app/db.py`
- Modify: `backend/app/routers/users.py` (UserAdminOut, UserAdminPatch, patch_user)
- Test: `backend/tests/test_users.py`

- [ ] **Step 1: Failing Test**

```python
def test_admin_sets_km_factor(client, session):
    from tests.conftest import make_user, login
    make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client)
    r = client.patch(f"/api/users/{lisa.id}", json={"km_factor": 3.0})
    assert r.status_code == 200
    assert r.json()["km_factor"] == 3.0

def test_km_factor_must_be_positive(client, session):
    from tests.conftest import make_user, login
    make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    login(client)
    assert client.patch(f"/api/users/{lisa.id}", json={"km_factor": 0}).status_code == 422
```

- [ ] **Step 2: Rot laufen lassen** — `pytest tests/test_users.py -v` → FAIL

- [ ] **Step 3: Implementieren**

`models.py` User: `km_factor: float = 1.0`

`db.py` migrate(), im User-Block:

```python
        if user_cols and "km_factor" not in user_cols:
            conn.execute(
                text('ALTER TABLE "user" ADD COLUMN km_factor FLOAT NOT NULL DEFAULT 1.0')
            )
```

`users.py`:

```python
class UserAdminOut(BaseModel):
    # ... bestehende Felder ...
    km_factor: float

class UserAdminPatch(BaseModel):
    is_active: bool | None = None
    km_factor: float | None = Field(default=None, gt=0)

# in patch_user, nach is_active-Block:
    if data.km_factor is not None:
        user.km_factor = data.km_factor
```

- [ ] **Step 4: Grün** — `pytest tests/ -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: Admin-Handicap User.km_factor"`

---

### Task 3: Vergleich — Challenge-Filter, Warm-up-Phase, km_factor

**Files:**
- Modify: `backend/app/routers/comparison.py`
- Test: `backend/tests/test_comparison.py`

- [ ] **Step 1: Failing Tests**

```python
from datetime import date, timedelta

def _setup(session, start_offset_days):
    """Season mit start_date relativ zu heute; 2 Aktivitäten um den Stichtag."""
    from app.models import Activity, Season
    from tests.conftest import make_user, make_category
    user = make_user(session, is_admin=True)
    cat = make_category(session, factor=1.0)
    start = date.today() + timedelta(days=start_offset_days)
    season = Season(year=date.today().year, goal_km=1000,
                    start_date=start, milestones_json="[]")
    session.add(season)
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=start - timedelta(days=1), distance_km=10))
    if start_offset_days <= 0:
        session.add(Activity(user_id=user.id, category_id=cat.id,
                             date=start, distance_km=7))
    session.commit()
    return user, start


def test_comparison_counts_everything_before_start(client, session):
    _setup(session, start_offset_days=5)  # Start in der Zukunft = Testphase
    from tests.conftest import login; login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    assert r.json()["users"][0]["total_scaled_km"] == 10.0


def test_comparison_counts_only_from_start_after_start(client, session):
    _setup(session, start_offset_days=0)  # Start heute = Challenge läuft
    from tests.conftest import login; login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    assert r.json()["users"][0]["total_scaled_km"] == 7.0


def test_comparison_warmup_phase(client, session):
    _setup(session, start_offset_days=0)
    from tests.conftest import login; login(client)
    r = client.get(f"/api/comparison/{date.today().year}?phase=warmup")
    assert r.json()["users"][0]["total_scaled_km"] == 10.0


def test_comparison_applies_km_factor(client, session):
    user, _ = _setup(session, start_offset_days=0)
    user.km_factor = 3.0
    session.add(user); session.commit()
    from tests.conftest import login; login(client)
    r = client.get(f"/api/comparison/{date.today().year}")
    assert r.json()["users"][0]["total_scaled_km"] == 21.0
    assert r.json()["users"][0]["km_factor"] == 3.0
```

- [ ] **Step 2: Rot** — `pytest tests/test_comparison.py -v` → FAIL

- [ ] **Step 3: Implementieren**

`comparison.py` — Signatur & Filter (Kern-Diff):

```python
from datetime import date as date_type
from typing import Literal

@router.get("/{year}", response_model=ComparisonOut,
            dependencies=[Depends(get_current_user)])
def comparison(year: int, phase: Literal["challenge", "warmup"] = "challenge",
               session: Session = Depends(get_session)):
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Kein Jahr konfiguriert")

    start = season.start_date
    today = date_type.today()
    rows = [(a, c) for a, c in rows if a.date.year == year]
    if phase == "warmup":
        if start is None:
            raise HTTPException(status_code=404, detail="Keine Warm-up-Phase konfiguriert")
        rows = [(a, c) for a, c in rows if a.date < start]
    elif start is not None and today >= start:
        # Challenge läuft: Warm-up-KM zählen nicht mehr.
        rows = [(a, c) for a, c in rows if a.date >= start]
    # (vor dem Start: Testphase, alles zählt)
```

In der User-Schleife den Faktor anwenden und ausgeben:

```python
        factor = user.km_factor if phase == "challenge" else 1.0
        for a, c in acts:
            scaled = round(a.distance_km * c.factor * factor, 2)
```

`schemas.py`: `ComparisonUser` + `km_factor: float = 1.0`; `ComparisonOut` + `start_date: date_type | None = None` und `phase: str = "challenge"`. In `comparison()` beides befüllen (`km_factor=user.km_factor`, `start_date=season.start_date`, `phase=phase`).

- [ ] **Step 4: Grün** — `pytest tests/ -v` → PASS (auch Bestandstests: Seasons ohne start_date verhalten sich wie bisher)
- [ ] **Step 5: Commit** — `git commit -m "feat: Vergleich mit Challenge-Stichtag, Warm-up-Phase und km_factor"`

---

### Task 4: Warm-up-Achievements (Backend)

**Files:**
- Modify: `backend/app/routers/achievements.py`
- Test: `backend/tests/test_achievements.py`

- [ ] **Step 1: Failing Test**

```python
from datetime import date, timedelta

def test_warmup_achievements(client, session):
    from app.models import Activity, Season
    from tests.conftest import make_user, make_category, login
    erik = make_user(session, is_admin=True)
    lisa = make_user(session, username="lisa")
    lauf = make_category(session, name="Laufen", icon="laufen", factor=1.0)
    rad = make_category(session, name="Rad", icon="rad", factor=0.25)
    start = date.today()  # Challenge startet heute -> Warm-up vorbei
    session.add(Season(year=date.today().year, goal_km=1000,
                       start_date=start, milestones_json="[]"))
    d = start - timedelta(days=2)
    session.add(Activity(user_id=erik.id, category_id=lauf.id, date=d, distance_km=20))
    session.add(Activity(user_id=lisa.id, category_id=rad.id, date=d, distance_km=100))
    session.commit()
    login(client)
    r = client.get("/api/achievements/warmup")
    assert r.status_code == 200
    by_key = {a["key"]: a for a in r.json()["achievements"]}
    assert by_key["warmup_laeufer"]["winners"][0]["display_name"] == "Erik"
    # Guter Start: gewertete km — Erik 20*1.0=20, Lisa 100*0.25=25
    assert by_key["guter_start"]["winners"][0]["display_name"] == "Lisa"
    assert by_key["guter_start"]["winners"][0]["km"] == 25.0
    assert "warmup_schwimmer" not in by_key  # keine Schwimm-Aktivität -> nicht vergeben
    assert r.json()["final"] is True
```

- [ ] **Step 2: Rot** — FAIL (404)

- [ ] **Step 3: Implementieren** — in `achievements.py` ergänzen:

```python
from datetime import date as date_type
from ..models import Season


class WarmupWinner(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    km: float


class WarmupAchievement(BaseModel):
    key: str
    title: str
    icon: str
    winners: list[WarmupWinner]  # bei Gleichstand mehrere


class WarmupOut(BaseModel):
    final: bool  # True sobald Challenge gestartet ist
    start_date: date_type | None
    achievements: list[WarmupAchievement]


_WARMUP_DEFS = [  # (key, titel, icon, bucket oder "gesamt")
    ("guter_start", "Guter Start", "fahne", "gesamt"),
    ("warmup_laeufer", "Warm-up-Läufer", "laufen", LAUF),
    ("warmup_radler", "Warm-up-Radler", "rad", RAD),
    ("warmup_schwimmer", "Warm-up-Schwimmer", "schwimmen", SCHWIMM),
]


@router.get("/warmup", response_model=WarmupOut,
            dependencies=[Depends(get_current_user)])
def warmup_achievements(session: Session = Depends(get_session)):
    today = date_type.today()
    season = session.exec(
        select(Season).where(Season.year == today.year)
    ).first()
    start = season.start_date if season else None
    if start is None:
        return WarmupOut(final=False, start_date=None, achievements=[])

    cats = {c.id: c for c in session.exec(select(Category)).all()}
    users = {u.id: u for u in session.exec(select(User).where(User.is_active)).all()}
    # {bucket/gesamt: {user_id: km}} — "gesamt" gewertet (Kategorie-Faktor), Buckets roh
    sums: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    acts = session.exec(select(Activity).where(Activity.date < start)).all()
    for act in acts:
        if act.user_id not in users or act.date.year != start.year:
            continue
        cat = cats.get(act.category_id)
        if cat is None:
            continue
        sums["gesamt"][act.user_id] += act.distance_km * cat.factor
        bucket = bucket_for_category(cat)
        if bucket is not None:
            sums[bucket][act.user_id] += act.distance_km

    out = []
    for key, title, icon, bucket in _WARMUP_DEFS:
        totals = sums.get(bucket, {})
        if not totals:
            continue
        best = max(totals.values())
        winners = [
            WarmupWinner(user_id=uid, display_name=users[uid].display_name,
                         avatar=users[uid].avatar, km=round(km, 2))
            for uid, km in sorted(totals.items(), key=lambda kv: -kv[1])
            if km == best
        ]
        out.append(WarmupAchievement(key=key, title=title, icon=icon, winners=winners))
    return WarmupOut(final=today >= start, start_date=start, achievements=out)
```

**Wichtig:** Route `/warmup` muss VOR eventuellen dynamischen Routen im selben Router stehen (hier unkritisch, `""` ist die einzige andere Route).

- [ ] **Step 4: Grün** — `pytest tests/ -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: Warm-up-Achievements (Guter Start, Warm-up-Läufer/-Radler/-Schwimmer)"`

---

### Task 5: Frontend — API-Typen & Countdown-Banner

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/ui/CountdownBanner.tsx`
- Create: `frontend/src/components/ui/countdown.ts` (pure Logik, testbar)
- Test: `frontend/src/components/ui/countdown.test.ts`
- Modify: `frontend/src/components/ui/Layout.tsx` (Banner einhängen — Struktur vorher lesen)

- [ ] **Step 1: `client.ts` erweitern**

```ts
export type Season = {
  id: number; year: number; goal_km: number
  milestones: Milestone[]; start_date: string | null
}
export type Comparison = {
  year: number; goal_km: number; milestones: Milestone[]
  users: ComparisonUser[]; start_date: string | null; phase: string
}
export type ComparisonUser = { /* bestehende Felder */ km_factor: number }
export type WarmupWinner = { user_id: number; display_name: string; avatar: string; km: number }
export type WarmupAchievement = { key: string; title: string; icon: string; winners: WarmupWinner[] }
export type WarmupOut = { final: boolean; start_date: string | null; achievements: WarmupAchievement[] }
// api:
  comparisonWarmup: (year: number) =>
    request<Comparison>(`/api/comparison/${year}?phase=warmup`),
  warmupAchievements: () => request<WarmupOut>('/api/achievements/warmup'),
// patchUser um km_factor erweitern:
  patchUser: (id: number, b: { is_active?: boolean; km_factor?: number }) => ...
```

- [ ] **Step 2: Failing Test für Countdown-Logik** (`countdown.test.ts`)

```ts
import { describe, expect, it } from 'vitest'
import { challengeStartMs, formatCountdown } from './countdown'

describe('countdown', () => {
  it('baut den Startzeitpunkt mit deutscher Sommerzeit (+02:00)', () => {
    expect(challengeStartMs('2026-07-20')).toBe(Date.parse('2026-07-20T00:00:00+02:00'))
  })
  it('formatiert Tage/Stunden/Minuten/Sekunden', () => {
    const start = Date.parse('2026-07-20T00:00:00+02:00')
    const now = Date.parse('2026-07-12T10:17:55+02:00')
    expect(formatCountdown(start - now)).toBe('7 T 13:42:05')
  })
  it('liefert null wenn vorbei', () => {
    expect(formatCountdown(-1)).toBeNull()
  })
})
```

Run: `cd frontend && npx vitest run src/components/ui/countdown.test.ts` → FAIL

- [ ] **Step 3: `countdown.ts` implementieren**

```ts
// Challenge startet um Mitternacht deutscher Zeit. Im Juli gilt CEST (+02:00);
// fester Offset reicht, solange der Stichtag im Sommer liegt.
export function challengeStartMs(startDate: string): number {
  return Date.parse(`${startDate}T00:00:00+02:00`)
}

export function formatCountdown(msLeft: number): string | null {
  if (msLeft <= 0) return null
  const s = Math.floor(msLeft / 1000)
  const days = Math.floor(s / 86400)
  const hh = String(Math.floor((s % 86400) / 3600)).padStart(2, '0')
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${days} T ${hh}:${mm}:${ss}`
}
```

Run: Test → PASS

- [ ] **Step 4: `CountdownBanner.tsx`** (Neon-Stil der App übernehmen — vorher `Layout.tsx` und bestehende Komponenten lesen)

```tsx
import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { challengeStartMs, formatCountdown } from './countdown'

export default function CountdownBanner() {
  const { data: seasons } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const season = seasons?.find((s) => s.year === new Date().getFullYear())
  if (!season?.start_date) return null
  const label = formatCountdown(challengeStartMs(season.start_date) - now)
  if (!label) return null
  return (
    <div className="bg-surface border-b border-edge px-4 py-2 text-center text-sm">
      <span className="text-ink-mute">Testphase — Challenge startet in </span>
      <span className="font-mono font-bold text-accent tabular-nums">{label}</span>
    </div>
  )
}
```

(Farb-/Klassennamen an die tatsächlichen Tailwind-Tokens der App anpassen — in `Layout.tsx`/`index.css` nachsehen.) In `Layout.tsx` direkt über dem Seiteninhalt rendern.

- [ ] **Step 5: Alle Frontend-Tests + Lint** — `cd frontend && npx vitest run && npm run lint` → PASS
- [ ] **Step 6: Commit** — `git commit -m "feat: Countdown-Banner bis Challenge-Start"`

---

### Task 6: Frontend — Archiv-Seite

**Files:**
- Create: `frontend/src/pages/Archiv.tsx`
- Modify: `frontend/src/App.tsx` (Route), `frontend/src/components/ui/Layout.tsx` (Nav-Link, nur ab Start)

- [ ] **Step 1: Seite bauen**

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'

export default function Archiv() {
  const year = new Date().getFullYear()
  const { data: warmup } = useQuery({
    queryKey: ['comparison', year, 'warmup'],
    queryFn: () => api.comparisonWarmup(year),
  })
  const { data: badges } = useQuery({
    queryKey: ['warmupAchievements'],
    queryFn: api.warmupAchievements,
  })
  if (!warmup) return <p className="p-8 text-ink-mute">Lade…</p>
  return (
    <div className="space-y-8 p-4">
      <section>
        <h2 className="text-xl font-bold">Warm-up-Phase (bis {warmup.start_date})</h2>
        <p className="text-sm text-ink-mute">
          Diese Kilometer zählen nicht für die Challenge — Ehre, wem Ehre gebührt.
        </p>
        <table className="mt-4 w-full text-left">
          <tbody>
            {warmup.users.map((u) => (
              <tr key={u.user_id} className="border-b border-edge">
                <td className="py-2 pr-2 text-ink-mute">{u.rank}.</td>
                <td className="py-2">{u.display_name}</td>
                <td className="py-2 text-right font-mono">{u.total_scaled_km.toFixed(1)} km</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      {badges && badges.achievements.length > 0 && (
        <section>
          <h2 className="text-xl font-bold">Warm-up-Auszeichnungen</h2>
          <ul className="mt-4 space-y-2">
            {badges.achievements.map((a) => (
              <li key={a.key} className="flex items-baseline gap-2">
                <span className="font-bold">{a.title}:</span>
                {a.winners.map((w) => (
                  <span key={w.user_id}>{w.display_name} ({w.km.toFixed(1)} km)</span>
                ))}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
```

(Optik an bestehende Seiten wie `Vergleich.tsx` angleichen — Avatar-Komponente, Icons etc. wiederverwenden.)

- [ ] **Step 2: Route + Nav**

`App.tsx`: `<Route path="/archiv" element={<Archiv />} />`. In `Layout.tsx` Nav-Link „Archiv" nur zeigen, wenn die Challenge gestartet ist (Season des Jahres hat `start_date` und `Date.now() >= challengeStartMs(start_date)`).

- [ ] **Step 3: Tests + Lint + Build** — `npx vitest run && npm run lint && npm run build` → PASS
- [ ] **Step 4: Commit** — `git commit -m "feat: Archiv-Seite mit Warm-up-Endstand und Auszeichnungen"`

---

### Task 7: Frontend — Admin km_factor + Ranking-Hinweis

**Files:**
- Modify: `frontend/src/pages/Admin.tsx` (Mitgliederliste: km_factor-Eingabe, bestehendes Muster von is_active-Toggle übernehmen)
- Modify: `frontend/src/pages/Vergleich.tsx` (bei `km_factor !== 1` Badge „×N" am Nutzernamen)
- Test: `frontend/src/pages/Admin.test.tsx` (bestehendes Muster erweitern: patchUser wird mit `{ km_factor: 3 }` aufgerufen)

- [ ] **Step 1: Admin-UI** — numerisches Eingabefeld (step 0.1, min 0.1) je Mitglied neben dem Aktiv-Toggle, `onBlur`/Speichern-Button ruft `api.patchUser(id, { km_factor })`, invalidiert `['users']`.
- [ ] **Step 2: Vergleich-Badge** — neben `display_name`: `{u.km_factor !== 1 && <span className="text-xs text-ink-mute">×{u.km_factor}</span>}`
- [ ] **Step 3: Tests + Lint** — `npx vitest run && npm run lint` → PASS
- [ ] **Step 4: Commit** — `git commit -m "feat: Admin-Handicap editierbar, Faktor-Badge im Ranking"`

---

### Task 8: End-to-End-Verify & Deploy

- [ ] **Step 1:** Backend komplett: `cd backend && .venv\Scripts\python -m pytest tests/ -v` → alle PASS
- [ ] **Step 2:** Frontend komplett: `cd frontend && npx vitest run && npm run lint && npm run build` → PASS
- [ ] **Step 3:** App lokal starten (README/`docker-compose.yml` beachten) und manuell prüfen: Banner tickt, Vergleich zeigt aktuell alle KM (Testphase), `/api/comparison/2026?phase=warmup` liefert Daten, Admin-Faktor speicherbar.
- [ ] **Step 4:** `git push` auf `main` → Auto-Deploy auf VPS. Danach `https://metermachen.jasperz.de/api/health` prüfen und einmal die Seite laden (Banner sichtbar?).
