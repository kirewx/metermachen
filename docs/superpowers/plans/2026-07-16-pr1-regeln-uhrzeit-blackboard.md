# PR 1: Regeln-Reiter, Uhrzeit-Erfassung, Wetten-Blackboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Statischer Regeln-Tab, optionale Startzeit auf Aktivitäten (nur sammeln), Blackboard-Übersicht aller Wetten im Wetten-Tab hinter neuem Add-on `blackboard`.

**Architecture:** Backend: neue nullable Spalte `Activity.start_time` (Migration im `db.py migrate()`-Muster), Schemas/Router/Strava-Import durchgereicht; neues Add-on `blackboard` wird in `seed.py` idempotent geseedet. Frontend: neue Seite `Regeln.tsx` (statischer Text + live geladene Faktoren-Tabelle), Startzeit-Feld im Eintrag-Formular, `Blackboard`-Komponente im Wetten-Tab auf Basis des bestehenden `GET /api/bets`.

**Tech Stack:** FastAPI + SQLModel + SQLite (Backend, pytest), React 19 + TanStack Query + Tailwind (Frontend, vitest + testing-library).

**Spec:** `docs/superpowers/specs/2026-07-16-regeln-achievements-uhrzeit-blackboard-design.md` (§1, §3, §4)

**Branch:** `feature/regeln-uhrzeit-blackboard` (existiert bereits, Spec liegt darauf). PR gegen `main`.

**Kommandos** (vom Repo-Root):
- Backend-Tests: `cd backend && python -m pytest -q`
- Frontend: `cd frontend && npm run test` / `npm run lint` / `npm run build`

---

### Task 1: Migration + Modell — `Activity.start_time`

**Files:**
- Modify: `backend/app/models.py` (Activity, ~Zeile 52)
- Modify: `backend/app/db.py` (migrate(), Activity-Block ~Zeile 92)
- Test: `backend/tests/test_migration.py`

- [ ] **Step 1: Failing Test schreiben**

Ans Ende von `backend/tests/test_migration.py` anhängen:

```python
def test_migration_adds_activity_start_time(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE activity (id INTEGER PRIMARY KEY, user_id INTEGER, "
            "category_id INTEGER, date DATE, distance_km FLOAT, duration_min INTEGER, "
            "elevation_m FLOAT, note VARCHAR, created_at DATETIME, updated_at DATETIME, "
            "source VARCHAR, external_id VARCHAR)"
        ))
        conn.execute(text(
            "INSERT INTO activity (user_id, category_id, date, distance_km, source)"
            " VALUES (1, 1, '2026-07-01', 5.0, 'manual')"
        ))
    migrate(engine)
    migrate(engine)  # zweiter Lauf: idempotent
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info("activity")'))]
        assert "start_time" in cols
        assert conn.execute(text("SELECT start_time FROM activity")).scalar() is None
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd backend && python -m pytest tests/test_migration.py::test_migration_adds_activity_start_time -q`
Expected: FAIL mit `assert "start_time" in cols`

- [ ] **Step 3: Modell + Migration implementieren**

In `backend/app/models.py` den Import oben ergänzen und `Activity` erweitern:

```python
from datetime import time as time_type
```

In der Klasse `Activity`, direkt nach `date: date_type = Field(index=True)`:

```python
    start_time: time_type | None = None  # nur Datensammlung, keine Auswertung (Spec §3)
```

In `backend/app/db.py`, im bestehenden `if _table_exists(conn, "activity"):`-Block nach dem `elevation_m`-Eintrag:

```python
            if "start_time" not in act_cols:
                conn.execute(text("ALTER TABLE activity ADD COLUMN start_time TIME"))
```

- [ ] **Step 4: Tests laufen lassen — müssen grün sein**

Run: `cd backend && python -m pytest tests/test_migration.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_migration.py
git commit -m "feat(activities): Spalte start_time (nullable) + Migration"
```

---

### Task 2: Add-on `blackboard` seeden

**Files:**
- Modify: `backend/app/seed.py` (KNOWN_ADDONS, ~Zeile 24)
- Test: `backend/tests/test_seed.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_seed.py` anhängen und **einen bestehenden Test anpassen**:

```python
def test_seed_registers_blackboard_addon_scheduled(session):
    from datetime import datetime, timezone

    from app.deps import addon_active

    seed_all(session, admin_user="chef", admin_password="geheim", year=2026)
    addon = session.exec(select(AddOn).where(AddOn.key == "blackboard")).one()
    # Gleiches Fenster wie sidebets: an, aber erst ab Challenge-Start aktiv.
    assert addon.enabled is True
    assert addon_active(addon, datetime(2026, 7, 1, tzinfo=timezone.utc)) is False
    assert addon_active(addon, datetime(2026, 7, 20, 12, tzinfo=timezone.utc)) is True
```

In `test_seed_is_idempotent` die letzte Zeile ändern:

```python
    assert len(session.exec(select(AddOn)).all()) == 2
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd backend && python -m pytest tests/test_seed.py -q`
Expected: FAIL (blackboard-Addon fehlt, Idempotenz-Count 1 ≠ 2)

- [ ] **Step 3: Seed implementieren**

In `backend/app/seed.py` in der Liste `KNOWN_ADDONS` einen zweiten Eintrag ergänzen:

```python
    {
        "key": "blackboard",
        "label": "Blackboard",
        "description": "Schwarzes Brett im Wetten-Tab: wer wettet gerade gegen wen.",
        "enabled": True,
        "active_from": SIDEBETS_START,  # schaltet zusammen mit den Wetten scharf
    },
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_seed.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/seed.py backend/tests/test_seed.py
git commit -m "feat(addons): Add-on blackboard seeden (Fenster wie sidebets)"
```

---

### Task 3: API — `start_time` in Create/Patch/Out

**Files:**
- Modify: `backend/app/schemas.py` (ActivityCreate ~133, ActivityPatch ~148, ActivityOut ~163)
- Modify: `backend/app/routers/activities.py` (`_to_out` ~19, Patch-Filter ~84)
- Test: `backend/tests/test_activities.py`

- [ ] **Step 1: Failing Tests schreiben**

Ans Ende von `backend/tests/test_activities.py` anhängen (Imports `login, make_category, make_user` aus `tests.conftest` sind dort schon vorhanden — prüfen, sonst ergänzen):

```python
def test_start_time_roundtrip(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    r = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-01", "distance_km": 5.0,
        "start_time": "07:30",
    })
    assert r.status_code == 201, r.text
    assert r.json()["start_time"] == "07:30:00"
    act_id = r.json()["id"]
    # Patch ohne Angabe lässt die Zeit unangetastet
    r = client.patch(f"/api/activities/{act_id}", json={"distance_km": 6.0})
    assert r.json()["start_time"] == "07:30:00"
    # explizit null = Zeit löschen
    r = client.patch(f"/api/activities/{act_id}", json={"start_time": None})
    assert r.json()["start_time"] is None


def test_start_time_ist_optional(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    r = client.post("/api/activities", json={
        "category_id": cat.id, "date": "2026-07-01", "distance_km": 5.0,
    })
    assert r.status_code == 201, r.text
    assert r.json()["start_time"] is None
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd backend && python -m pytest tests/test_activities.py -q -k start_time`
Expected: FAIL (ValidationError bzw. KeyError `start_time`)

- [ ] **Step 3: Schemas + Router implementieren**

In `backend/app/schemas.py` oben den Import ergänzen:

```python
from datetime import time as time_type
```

`ActivityCreate` ergänzen (nach `duration_min`):

```python
    start_time: time_type | None = None
```

`ActivityPatch` ergänzen (nach `duration_min`):

```python
    start_time: time_type | None = None
```

`ActivityOut` ergänzen (nach `duration_min`):

```python
    start_time: time_type | None
```

In `backend/app/routers/activities.py`:

`_to_out` bekommt das Feld (nach `duration_min=activity.duration_min,`):

```python
        start_time=activity.start_time,
```

Im Patch-Endpoint den Nullable-Filter erweitern — aus

```python
        if value is not None or key in ("note", "duration_min")
```

wird

```python
        if value is not None or key in ("note", "duration_min", "start_time")
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_activities.py -q`
Expected: alle PASS (auch die Bestandstests — `_to_out` wird überall benutzt)

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/activities.py backend/tests/test_activities.py
git commit -m "feat(activities): start_time in Create/Patch/Out"
```

---

### Task 4: Strava-Import speichert den Zeitanteil

**Files:**
- Modify: `backend/app/services/strava.py` (`_parse_date` ~93, `import_activity` ~99)
- Test: `backend/tests/test_strava.py`

Webhook und Backfill laufen beide durch `import_activity` — eine Änderungsstelle reicht. Bereits importierte Aktivitäten bleiben ohne Zeit (Spec §3, bewusst).

- [ ] **Step 1: Failing Test schreiben**

Ans Ende von `backend/tests/test_strava.py` anhängen (Helpers `_setup_conn`, `make_category` existieren dort):

```python
def test_import_activity_sets_start_time(session):
    from datetime import time as time_type

    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    data = {"id": 1001, "sport_type": "Run", "distance": 5000.0,
            "start_date_local": "2026-03-01T06:45:00Z", "name": "Frühlauf"}
    assert strava.import_activity(session, conn, data) is True
    act = session.exec(select(Activity).where(Activity.external_id == "1001")).one()
    assert act.start_time == time_type(6, 45)


def test_import_activity_without_start_date_has_no_time(session):
    user, conn = _setup_conn(session)
    make_category(session, name="Laufen", strava_sport_types='["Run"]')
    data = {"id": 1002, "sport_type": "Run", "distance": 5000.0, "name": "Lauf"}
    assert strava.import_activity(session, conn, data) is True
    act = session.exec(select(Activity).where(Activity.external_id == "1002")).one()
    assert act.start_time is None
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd backend && python -m pytest tests/test_strava.py -q -k start_time`
Expected: FAIL (`act.start_time` ist None statt 06:45)

- [ ] **Step 3: Implementieren**

In `backend/app/services/strava.py` oben den Import ergänzen:

```python
from datetime import time as time_type
```

Nach `_parse_date` eine neue Funktion:

```python
def _parse_time(value: str | None) -> time_type | None:
    """Zeitanteil von start_date_local — Strava liefert lokale Wanduhrzeit mit 'Z'."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).time()
```

In `import_activity` nach der Zeile `act_date = _parse_date(...)`:

```python
    act_time = _parse_time(data.get("start_date_local") or data.get("start_date"))
```

und im `Activity(...)`-Konstruktor nach `date=act_date,`:

```python
        start_time=act_time,
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd backend && python -m pytest tests/test_strava.py -q`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strava.py backend/tests/test_strava.py
git commit -m "feat(strava): Startzeit aus start_date_local importieren"
```

---

### Task 5: Frontend — Startzeit-Feld im Formular + Anzeige

**Files:**
- Modify: `frontend/src/api/client.ts` (Types `Activity` ~26, `ActivityInput` ~39)
- Modify: `frontend/src/components/activities/SchnellwahlCard.tsx`
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx` (Meta-Zeile ~134)
- Test: `frontend/src/components/activities/SchnellwahlCard.test.tsx`

- [ ] **Step 1: Bestehende Submit-Tests anpassen + neuen Test schreiben**

In `SchnellwahlCard.test.tsx` erwarten die Submit-Tests exakte Payloads (`toHaveBeenCalledWith`) — dort überall `start_time: null` ergänzen, z. B. im Test „Submit ohne Details nutzt heute als Datum":

```tsx
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: heute(),
      distance_km: 5,
      duration_min: null,
      note: null,
      start_time: null,
    })
```

(Gleiches im Details-Test weiter unten in der Datei.) Zusätzlich neuen Test anhängen:

```tsx
  it('Details: Startzeit wird als HH:MM übernommen', async () => {
    const onSubmit = vi.fn()
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: 'Details' }))
    await userEvent.type(screen.getByLabelText('Startzeit'), '07:30')
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ start_time: '07:30' }),
    )
  })
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- SchnellwahlCard`
Expected: FAIL (Label „Startzeit" existiert nicht, Payload ohne `start_time`)

- [ ] **Step 3: Implementieren**

`frontend/src/api/client.ts` — Typ `Activity` ergänzen (nach `duration_min`):

```ts
  start_time: string | null
```

Typ `ActivityInput` ergänzen:

```ts
  start_time?: string | null
```

`SchnellwahlCard.tsx`:

State ergänzen (nach `duration`-State):

```tsx
  const [startzeit, setStartzeit] = useState(initial?.start_time?.slice(0, 5) ?? '')
```

Im `onSubmit(...)`-Objekt in `submit()`:

```tsx
        start_time: startzeit || null,
```

Im Reset-Block (`if (!initial) { ... }`):

```tsx
          setStartzeit('')
```

Im Details-Grid nach dem Datum-Input:

```tsx
            <Input
              label="Startzeit"
              type="time"
              value={startzeit}
              onChange={(e) => setStartzeit(e.target.value)}
            />
```

`MeineAktivitaeten.tsx` — Meta-Zeile der Einträge (die `<p className="truncate text-xs text-ink-mute">`) nach `{a.date}` ergänzen:

```tsx
                          {a.start_time ? ` · ${a.start_time.slice(0, 5)} Uhr` : ''}
```

- [ ] **Step 4: Tests + Lint laufen lassen**

Run: `cd frontend && npm run test && npm run lint`
Expected: alle PASS (Backend liefert `HH:MM:SS`, `slice(0, 5)` zeigt `HH:MM`)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/activities/SchnellwahlCard.tsx frontend/src/components/activities/SchnellwahlCard.test.tsx frontend/src/pages/MeineAktivitaeten.tsx
git commit -m "feat(frontend): optionales Startzeit-Feld im Eintrag-Formular"
```

---

### Task 6: Regeln-Seite + Tab + Route

**Files:**
- Create: `frontend/src/pages/Regeln.tsx`
- Modify: `frontend/src/components/ui/tabs.ts` (TABS ~11)
- Modify: `frontend/src/App.tsx` (Import + Route)

Kein Add-on-Gate, sichtbar für alle Eingeloggten. Faktoren-Tabelle lädt live aus `GET /api/categories`; der Wetten-Abschnitt erscheint nur bei aktivem `sidebets`-Add-on. Icon: `notiz` (existiert in `frontend/public/icons.svg`). Der Regeltext ist Entwurf — Rick korrigiert im PR-Review.

- [ ] **Step 1: Tab + Route ergänzen**

`tabs.ts` — in `TABS` zwischen „Wetten" und „Archiv" einfügen:

```ts
  { to: '/regeln', label: 'Regeln', icon: 'notiz', end: false, adminOnly: false, abStart: false },
```

`App.tsx` — Import ergänzen:

```tsx
import Regeln from './pages/Regeln'
```

und Route (nach der `/archiv`-Route):

```tsx
        <Route path="/regeln" element={<Regeln />} />
```

- [ ] **Step 2: Seite anlegen**

`frontend/src/pages/Regeln.tsx` (vollständig):

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'

function Abschnitt({ titel, children }: { titel: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2 className="mb-2 text-sm font-black uppercase tracking-wider text-accent">{titel}</h2>
      <div className="space-y-2 text-sm text-ink-soft">{children}</div>
    </Card>
  )
}

export default function Regeln() {
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  const sidebetsAktiv = addons.some((a) => a.key === 'sidebets' && a.active)
  const aktive = categories.filter((c) => c.is_active)

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Abschnitt titel="Worum geht es">
        <p>
          MeterMachen ist unsere gemeinsame Jahres-Challenge: Jede Person sammelt über das Jahr
          Kilometer — beim Laufen, Radfahren, Schwimmen oder was auch immer dich bewegt. Damit
          unterschiedliche Sportarten fair gegeneinander antreten, zählen nicht die rohen
          Kilometer, sondern <strong className="text-ink">gewertete Kilometer (MM)</strong>.
          Wer am Jahresende vorn liegt, gewinnt — aber eigentlich gewinnen alle, die dranbleiben.
        </p>
      </Abschnitt>

      <Abschnitt titel="Zeitraum">
        <p>
          Die Challenge startet am <strong className="text-ink">20.07.2026</strong> und läuft bis
          zum Jahresende. Alles davor war Warm-up: Diese Kilometer zählen nicht für die
          Hauptwertung, bleiben aber im Archiv sichtbar — inklusive der Warm-up-Auszeichnungen.
        </p>
      </Abschnitt>

      <Abschnitt titel="Wertung">
        <p>
          Jede Sportart hat einen Faktor. Gewertete km (MM) = echte km × Faktor. Die Faktoren
          gleichen aus, dass ein Rad-Kilometer schneller gesammelt ist als ein Schwimm-Kilometer.
        </p>
        <table className="w-full text-left">
          <thead>
            <tr className="text-xs uppercase tracking-wider text-ink-mute">
              <th className="py-1 font-bold">Sportart</th>
              <th className="py-1 text-right font-bold">Faktor</th>
            </tr>
          </thead>
          <tbody>
            {aktive.map((c) => (
              <tr key={c.id} className="border-t border-line/30">
                <td className="flex items-center gap-2 py-1.5 font-bold text-ink">
                  <Icon name={c.icon} size={16} className="text-accent" />
                  {c.name}
                </td>
                <td className="py-1.5 text-right font-mono tabular-nums text-accent">
                  ×{c.factor}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-ink-mute">
          Die Tabelle ist live — wenn ein Admin Faktoren anpasst, stimmt sie automatisch.
        </p>
      </Abschnitt>

      <Abschnitt titel="Einträge & Fairness">
        <p>
          Aktivitäten trägst du von Hand ein oder du verbindest Strava — dann kommen sie
          automatisch. Es gilt Ehrlichkeit vor Ehrgeiz:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Nur echte, selbst zurückgelegte Kilometer eintragen.</li>
          <li>Einträge zeitnah erfassen — Nachtragen ist ok, Fantasie-Kilometer nicht.</li>
          <li>Bei Strava-Import gilt, was Strava gemessen hat.</li>
          <li>Im Zweifel klärt die Gruppe — der Spaß steht über der Platzierung.</li>
        </ul>
      </Abschnitt>

      {sidebetsAktiv && (
        <Abschnitt titel="Wetten (Kurzfassung)">
          <p>
            Im Wetten-Tab kannst du Punkte auf sportliche Duelle, Monats-Tipps, Ziel-, Streak-
            und Über/Unter-Wetten setzen. Punkte-Nachschub gibt es über Sport: +1 Punkt je 5
            gewertete km seit Challenge-Start. Punkte sind Spielwährung — kein Echtgeld.
          </p>
        </Abschnitt>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Lint, Tests und Build laufen lassen**

Run: `cd frontend && npm run lint && npm run test && npm run build`
Expected: alle PASS (bestehende `tabs.test.ts` nutzt eine lokale TABS-Kopie und bleibt grün)

- [ ] **Step 4: Manuell prüfen**

Dev-Server starten (`cd frontend && npm run dev`, Backend läuft via `cd backend && uvicorn app.main:app --reload`), einloggen, Tab „Regeln" öffnen: Faktoren-Tabelle zeigt die Kategorien, Wetten-Abschnitt erscheint nur bei aktivem sidebets-Add-on.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Regeln.tsx frontend/src/components/ui/tabs.ts frontend/src/App.tsx
git commit -m "feat(regeln): statischer Regeln-Tab mit Live-Faktoren-Tabelle"
```

---

### Task 7: Blackboard-Komponente (Filterlogik + UI)

**Files:**
- Create: `frontend/src/components/bets/Blackboard.tsx`
- Test: `frontend/src/components/bets/Blackboard.test.tsx`

Datenquelle ist das bestehende `GET /api/bets` (liefert alle Wetten aller Nutzer, siehe `bets_router.list_bets`). Kein neuer Endpoint.

- [ ] **Step 1: Failing Test schreiben**

`frontend/src/components/bets/Blackboard.test.tsx` (neu):

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Bet } from '../../api/client'
import Blackboard, { filtereBlackboard } from './Blackboard'

const basis = {
  stake: 10, jackpot: 0, created_at: '2026-07-20T00:00:00Z', resolved_at: null,
  result: {}, standing: {}, my_role: null, participants: [] as Bet['participants'],
  period_start: '2026-08-01', period_end: '2026-08-31',
}

const bets: Bet[] = [
  { ...basis, id: 1, type: 'duell', creator_id: 1, title: 'Erik vs. Lisa',
    status: 'laufend', params: { opponent_id: 2 } },
  { ...basis, id: 2, type: 'ziel', creator_id: 2, title: 'Lisa schafft 100',
    status: 'offen', params: { target_km: 100 } },
  { ...basis, id: 3, type: 'duell', creator_id: 1, title: 'Alte Wette',
    status: 'entschieden', params: { opponent_id: 2 } },
]

const spieler = [
  { user_id: 1, display_name: 'Erik' },
  { user_id: 2, display_name: 'Lisa' },
]

describe('filtereBlackboard', () => {
  it('zeigt nur offene und laufende Wetten', () => {
    const r = filtereBlackboard(bets, { personId: null, typ: null })
    expect(r.map((b) => b.id)).toEqual([1, 2])
  })

  it('filtert nach Person (Ersteller, Duell-Gegner oder Teilnehmer)', () => {
    const r = filtereBlackboard(bets, { personId: 2, typ: null })
    expect(r.map((b) => b.id)).toEqual([1, 2])
    expect(filtereBlackboard(bets, { personId: 1, typ: null }).map((b) => b.id)).toEqual([1])
  })

  it('filtert nach Wett-Typ', () => {
    expect(filtereBlackboard(bets, { personId: null, typ: 'ziel' }).map((b) => b.id)).toEqual([2])
  })
})

describe('Blackboard', () => {
  it('zeigt Duelle als A ⚔️ B und filtert per Dropdown', async () => {
    render(<Blackboard bets={bets} spieler={spieler} />)
    expect(screen.getByText('Erik ⚔️ Lisa')).toBeInTheDocument()
    expect(screen.getByText('Lisa schafft 100')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Wett-Typ'), 'ziel')
    expect(screen.queryByText('Erik ⚔️ Lisa')).not.toBeInTheDocument()
    expect(screen.getByText('Lisa schafft 100')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- Blackboard`
Expected: FAIL (Modul existiert nicht)

- [ ] **Step 3: Komponente implementieren**

`frontend/src/components/bets/Blackboard.tsx` (neu, vollständig):

```tsx
import { useState } from 'react'
import type { Bet } from '../../api/client'
import Card from '../ui/Card'
import Select from '../ui/Select'
import type { Spieler } from './BetCard'

const TYP_LABEL: Record<Bet['type'], string> = {
  duell: 'Duell',
  monats_tipp: 'Monats-Tipp',
  ziel: 'Ziel-Wette',
  streak: 'Streak-Wette',
  ueber_unter: 'Über/Unter',
}

function datum(d: string) {
  return new Date(`${d}T00:00:00`).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
  })
}

function beteiligte(bet: Bet): number[] {
  const ids = new Set<number>([bet.creator_id])
  if (bet.params.opponent_id) ids.add(bet.params.opponent_id)
  for (const p of bet.participants) ids.add(p.user_id)
  return [...ids]
}

export function filtereBlackboard(
  bets: Bet[],
  filter: { personId: number | null; typ: Bet['type'] | null },
): Bet[] {
  return bets
    .filter((b) => b.status === 'offen' || b.status === 'laufend')
    .filter((b) => filter.typ === null || b.type === filter.typ)
    .filter((b) => filter.personId === null || beteiligte(b).includes(filter.personId))
}

export default function Blackboard({ bets, spieler }: { bets: Bet[]; spieler: Spieler[] }) {
  const [personId, setPersonId] = useState<number | null>(null)
  const [typ, setTyp] = useState<Bet['type'] | null>(null)
  const zeilen = filtereBlackboard(bets, { personId, typ })
  const name = (id: number | undefined) =>
    spieler.find((s) => s.user_id === id)?.display_name ?? `#${id}`

  return (
    <Card>
      <div className="mb-3 flex flex-wrap gap-3">
        <Select
          label="Person"
          value={personId ?? ''}
          onChange={(e) => setPersonId(e.target.value ? Number(e.target.value) : null)}
          className="w-40"
        >
          <option value="">Alle</option>
          {spieler.map((s) => (
            <option key={s.user_id} value={s.user_id}>
              {s.display_name}
            </option>
          ))}
        </Select>
        <Select
          label="Wett-Typ"
          value={typ ?? ''}
          onChange={(e) => setTyp((e.target.value || null) as Bet['type'] | null)}
          className="w-40"
        >
          <option value="">Alle</option>
          {Object.entries(TYP_LABEL).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      {zeilen.length === 0 && (
        <p className="text-sm text-ink-mute">Nichts an der Tafel — Zeit für eine Wette.</p>
      )}
      <ul className="divide-y divide-line/30">
        {zeilen.map((b) => (
          <li key={b.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm">
            <span className="font-bold text-ink">
              {b.type === 'duell'
                ? `${name(b.creator_id)} ⚔️ ${name(b.params.opponent_id)}`
                : beteiligte(b).map((id) => name(id)).join(', ')}
            </span>
            <span className="rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-tech">
              {TYP_LABEL[b.type]}
            </span>
            <span className="min-w-0 flex-1 truncate text-ink-soft">{b.title}</span>
            <span className="font-bold text-accent">{b.stake} P</span>
            <span className="font-mono text-xs text-ink-mute">
              {datum(b.period_start)}–{datum(b.period_end)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd frontend && npm run test -- Blackboard`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/bets/Blackboard.tsx frontend/src/components/bets/Blackboard.test.tsx
git commit -m "feat(wetten): Blackboard-Komponente mit Person/Typ-Filter"
```

---

### Task 8: Blackboard in Wetten.tsx einhängen (Add-on-gated)

**Files:**
- Modify: `frontend/src/pages/Wetten.tsx`
- Test: `frontend/src/pages/Wetten.test.tsx`

Sichtbar nur, wenn das Add-on `blackboard` aktiv ist. Der Wetten-Tab selbst ist bereits `sidebets`-gated (tabs.ts + App.tsx) — die Spec-Bedingung „nur wenn Wetten-Tab sichtbar" ist damit automatisch erfüllt.

- [ ] **Step 1: Failing Test schreiben**

In `frontend/src/pages/Wetten.test.tsx` im `vi.mock('../api/client', ...)`-Block eine `addons`-Mock-Funktion ergänzen (neben `me`, `points`, …):

```tsx
    addons: vi.fn().mockResolvedValue([
      { id: 1, key: 'blackboard', label: 'Blackboard', description: '', enabled: true,
        active_from: null, active_until: null, active: true },
    ]),
```

Neuen Test im `describe('Wetten', ...)`-Block anhängen:

```tsx
  it('zeigt das Blackboard, wenn das Add-on aktiv ist', async () => {
    renderWetten()
    expect(await screen.findByText('Blackboard')).toBeInTheDocument()
    // die offene Duell-Wette hängt an der Tafel
    expect(screen.getAllByText('Lisa vs. Chef').length).toBeGreaterThanOrEqual(2)
  })
```

- [ ] **Step 2: Test laufen lassen — muss scheitern**

Run: `cd frontend && npm run test -- Wetten`
Expected: neuer Test FAIL („Blackboard" nicht gefunden), Bestandstests PASS

- [ ] **Step 3: Implementieren**

In `frontend/src/pages/Wetten.tsx`:

Import ergänzen:

```tsx
import Blackboard from '../components/bets/Blackboard'
```

Query ergänzen (bei den anderen Queries):

```tsx
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
```

Nach der `spieler`-Definition:

```tsx
  const blackboardAktiv = addons.some((a) => a.key === 'blackboard' && a.active)
```

Zwischen der Sektion „Laufende Wetten" und `<PunkteRanking />` einfügen:

```tsx
      {blackboardAktiv && (
        <section className="space-y-3">
          <h2 className="text-sm font-black uppercase tracking-wider text-ink-mute">
            Blackboard
          </h2>
          <Blackboard bets={wetten} spieler={spieler} />
        </section>
      )}
```

- [ ] **Step 4: Tests laufen lassen**

Run: `cd frontend && npm run test -- Wetten`
Expected: alle PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Wetten.tsx frontend/src/pages/Wetten.test.tsx
git commit -m "feat(wetten): Blackboard-Sektion hinter Add-on blackboard"
```

---

### Task 9: Gesamtverifikation + PR

- [ ] **Step 1: Volle Test-Suiten**

Run: `cd backend && python -m pytest -q`
Expected: alle PASS

Run: `cd frontend && npm run lint && npm run test && npm run build`
Expected: alle PASS

- [ ] **Step 2: End-to-End-Check (verify-Skill nutzen)**

Backend + Frontend lokal starten und durchklicken: (1) Regeln-Tab zeigt Faktoren-Tabelle, (2) Eintrag mit Startzeit 07:30 anlegen → erscheint mit „· 07:30 Uhr", ohne Startzeit → keine Zeitanzeige, (3) Wetten-Tab zeigt Blackboard (dazu ggf. Add-on `blackboard` im Admin ohne Fenster aktivieren), Filter funktionieren.

- [ ] **Step 3: Push + PR**

```bash
git push -u origin feature/regeln-uhrzeit-blackboard
gh pr create --title "Regeln-Reiter, Startzeit-Erfassung, Wetten-Blackboard" --body "Implementiert Spec §1/§3/§4 (docs/superpowers/specs/2026-07-16-...). Regeln-Tab (statisch, Faktoren live), Activity.start_time (nur sammeln), Blackboard hinter Add-on blackboard.

Review-Fokus: Regeltext in frontend/src/pages/Regeln.tsx (Entwurf, bitte korrigieren)."
```
