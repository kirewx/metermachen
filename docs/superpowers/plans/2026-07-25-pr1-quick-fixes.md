# PR 1: Quick-Fixes (A1–A9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neun kleine UI-/Regel-Anpassungen aus der Spec `docs/superpowers/specs/2026-07-25-anpassungen-und-newsfeed-design.md` Teil A umsetzen.

**Architecture:** Kleine, unabhängige Änderungen an bestehenden Dateien. Backend: eine Datenmigration, eine Metrik-Änderung, ein erweitertes API-Feld. Frontend: Dropdown-Erweiterung, Label-/Stil-Anpassungen, ein neues Popover-Component.

**Tech Stack:** FastAPI + SQLModel + pytest (Backend, `cd backend && uv run pytest`), React 19 + TypeScript + Vitest (Frontend, `cd frontend && npx vitest run`).

**Branch:** `feature/quick-fixes-ui` von `origin/main`:
```bash
git fetch origin && git checkout -b feature/quick-fixes-ui origin/main
```

**Wichtig:** Vor dem ersten Task `frontend/package.json` prüfen, wie das Test-Script heißt (vermutlich `npm test` → vitest). Alle Pfade unten relativ zum Repo-Root.

---

### Task 1: Saisonende 2026 → 16.05.2027 (A2 Daten)

**Files:**
- Modify: `backend/app/db.py` (Funktion `migrate`, Season-Block ~Zeile 74–92)
- Test: `backend/tests/test_migration.py` (anhängen)

- [ ] **Step 1: Failing Test schreiben** — in `backend/tests/test_migration.py` anhängen (Imports oben ergänzen: `from datetime import date` und `from sqlmodel import select` sowie `from app.db import migrate` und `from app.models import Season`, soweit nicht vorhanden — vorher die bestehenden Imports der Datei ansehen und nur Fehlendes ergänzen):

```python
def test_backfill_saisonende_2026(session):
    session.add(Season(year=2026, goal_km=1000.0))
    session.commit()
    migrate(session.get_bind())
    session.expire_all()
    s = session.exec(select(Season).where(Season.year == 2026)).one()
    assert s.end_date == date(2027, 5, 16)


def test_backfill_saisonende_ueberschreibt_nicht(session):
    session.add(Season(year=2026, goal_km=1000.0, end_date=date(2027, 6, 1)))
    session.commit()
    migrate(session.get_bind())
    session.expire_all()
    s = session.exec(select(Season).where(Season.year == 2026)).one()
    assert s.end_date == date(2027, 6, 1)
```

- [ ] **Step 2:** `cd backend && uv run pytest tests/test_migration.py -q` → die zwei neuen Tests FAILen (end_date bleibt None).

- [ ] **Step 3: Implementieren** — in `backend/app/db.py`, im `if _table_exists(conn, "season"):`-Block, direkt NACH dem `if "end_date" not in season_cols:`-Block einfügen (unconditional, damit auch Bestands-DBs mit bereits vorhandener Spalte den Backfill bekommen):

```python
            # Einmaliger Backfill (Spec 2026-07-25 A2): Saisonende 2026/27 =
            # Stuttgartlauf 16.05.2027. Nur wenn der Admin nichts gesetzt hat.
            conn.execute(text(
                "UPDATE season SET end_date = '2027-05-16' "
                "WHERE year = 2026 AND end_date IS NULL"
            ))
```

- [ ] **Step 4:** `cd backend && uv run pytest tests/test_migration.py tests/test_seasons.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_migration.py
git commit -m "feat(season): Backfill Saisonende 16.05.2027 fuer Season 2026"
```

---

### Task 2: Saison-Label „2026/27" (A2 Frontend)

**Files:**
- Modify: `frontend/src/components/ui/season.ts:27-32` (`saisonLabel`)
- Test: `frontend/src/components/ui/season.test.ts`

- [ ] **Step 1: Test anpassen/ergänzen** — in `season.test.ts` den bestehenden Test auf `"Saison 2026/27"` suchen und die Erwartung auf `"2026/27"` ändern; falls keiner existiert, ergänzen:

```ts
it('zeigt jahresuebergreifende Saison als 2026/27', () => {
  const s = { id: 1, year: 2026, goal_km: 1000, milestones: [], start_date: '2026-07-20', end_date: '2027-05-16' }
  expect(saisonLabel(s)).toBe('2026/27')
})
```

- [ ] **Step 2:** `cd frontend && npx vitest run src/components/ui/season.test.ts` → FAIL (liefert „Saison 2026/27").

- [ ] **Step 3: Implementieren** — in `season.ts`:

```ts
export function saisonLabel(season: Season | undefined): string {
  if (!season) return String(new Date().getFullYear())
  const endJahr = season.end_date ? Number(season.end_date.slice(0, 4)) : season.year
  if (endJahr === season.year) return String(season.year)
  return `${season.year}/${String(endJahr).slice(2)}`
}
```

- [ ] **Step 4:** `npx vitest run src/components/ui/season.test.ts` → PASS.

- [ ] **Step 5: Commit** — `git add frontend/src/components/ui/season.*` + `git commit -m "feat(season): Label 2026/27 statt Saison 2026/27"`

---

### Task 3: Streak-Wetten: 5-MM-Tagesminimum (A7)

**Files:**
- Modify: `backend/app/services/bet_metrics.py:44-63` (`longest_streak`)
- Modify: `frontend/src/components/bets/BetCreateDialog.tsx:16` (Hilfetext)
- Test: `backend/tests/test_bet_metrics.py`

- [ ] **Step 1: Failing Tests** — in `test_bet_metrics.py` zuerst die bestehenden `longest_streak`-Tests lesen: sie legen vermutlich Aktivitäten mit ≥ 1 km an und erwarten Streak-Tage. Diese Tests auf die neue Regel umstellen (Kategorie-Faktor beachten: `make_category(..., factor=4.0)` → 1,3 km ⇒ 5,2 MM zählt, 1,2 km ⇒ 4,8 MM zählt nicht). Zusätzlich anhängen:

```python
def test_streak_tag_braucht_5_mm(session):
    user = make_user(session)
    cat = make_category(session, factor=4.0)
    # Tag 1: 1.3 km * 4.0 = 5.2 MM -> zaehlt. Tag 2: 1.2 km * 4.0 = 4.8 MM -> zaehlt nicht.
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 3), distance_km=1.3))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 4), distance_km=1.2))
    session.commit()
    assert longest_streak(session, user.id, date(2026, 8, 3), date(2026, 8, 5)) == 1


def test_streak_summiert_mm_pro_tag(session):
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    # Zwei Aktivitaeten am selben Tag: 3.0 + 2.5 = 5.5 MM -> zaehlt
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 3), distance_km=3.0))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 3), distance_km=2.5))
    session.commit()
    assert longest_streak(session, user.id, date(2026, 8, 3), date(2026, 8, 3)) == 1
```

(Imports der Datei prüfen; `make_user`/`make_category` kommen aus `tests/conftest.py`, `Activity` aus `app.models`, `date` aus `datetime`.)

- [ ] **Step 2:** `cd backend && uv run pytest tests/test_bet_metrics.py -q` → neue Tests FAIL.

- [ ] **Step 3: Implementieren** — `longest_streak` in `bet_metrics.py` komplett ersetzen:

```python
STREAK_MIN_MM = 5.0  # Tages-Minimum in MM (km × Kategorie-Faktor), Spec 2026-07-25 A7


def longest_streak(
    session: Session, user_id: int, start: date_type, end: date_type
) -> int:
    """Längste Serie von Tagen mit >= STREAK_MIN_MM gewerteten km (Kategorie-
    Faktor, ohne Admin-Handicap — wie alle Wett-Metriken) im Zeitraum."""
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    per_day: dict[date_type, float] = defaultdict(float)
    for a in session.exec(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.date >= start,
            Activity.date <= end,
        )
    ).all():
        cat = cats.get(a.category_id)
        if cat is not None:
            per_day[a.date] += a.distance_km * cat.factor
    best = run = 0
    day = start
    while day <= end:
        run = run + 1 if per_day[day] >= STREAK_MIN_MM else 0
        best = max(best, run)
        day += timedelta(days=1)
    return best
```

- [ ] **Step 4:** `uv run pytest tests/test_bet_metrics.py tests/test_bets_resolution.py -q` → PASS (Resolution-Tests, die Streaks bauen, ggf. auf 5-MM-Tage anheben).

- [ ] **Step 5: Hilfetext** — in `BetCreateDialog.tsx:16`:

```ts
  { key: 'streak', label: 'Streak-Wette', hilfe: 'N Tage in Folge Sport (mind. 5 MM pro Tag, sonst zählt der Tag nicht). Andere halten dagegen.' },
```

- [ ] **Step 6:** `cd frontend && npx vitest run src/pages/Wetten.test.tsx` → PASS (falls der Text dort geprüft wird, Erwartung anpassen).

- [ ] **Step 7: Commit** — `git add backend/app/services/bet_metrics.py backend/tests/test_bet_metrics.py backend/tests/test_bets_resolution.py frontend/src/components/bets/BetCreateDialog.tsx` + `git commit -m "feat(wetten): Streak-Tage brauchen mind. 5 MM statt 1 km roh"`

---

### Task 4: Auszeichnungs-Infos im Comparison-Endpoint (A6 Backend)

**Files:**
- Modify: `backend/app/services/achievements.py` (nach dem `EMOJIS`-Dict, ~Zeile 136)
- Modify: `backend/app/schemas.py` (`ComparisonUser`, ~Zeile 207)
- Modify: `backend/app/routers/comparison.py:62-69` und `:110`
- Test: `backend/tests/test_comparison.py` (anhängen)

- [ ] **Step 1: Failing Test** — in `test_comparison.py` anhängen (bestehende Fixtures/Helper der Datei nutzen; Muster für Login/Comparison-Aufruf aus vorhandenen Tests der Datei übernehmen):

```python
def test_comparison_liefert_auszeichnungen_mit_beschreibung(client, session):
    user = make_user(session)
    make_category(session)
    session.add(Season(year=2026, goal_km=1000.0))
    session.add(AchievementUnlock(user_id=user.id, key="hattrick"))
    session.commit()
    login(client)
    data = client.get("/api/comparison/2026").json()
    me = next(u for u in data["users"] if u["user_id"] == user.id)
    assert me["emojis"] == ["🎩"]
    assert me["auszeichnungen"] == [{
        "emoji": "🎩",
        "title": "Hattrick",
        "description": "Drei Aktivitäten an einem Tag.",
    }]
```

- [ ] **Step 2:** `uv run pytest tests/test_comparison.py -q` → FAIL (`auszeichnungen` fehlt).

- [ ] **Step 3: Implementieren.** In `achievements.py` nach dem `EMOJIS`-Dict:

```python
def _showcase_info() -> dict[str, tuple[str, str, str]]:
    """key -> (emoji, titel, beschreibung) für alle Emoji-Achievements."""
    titel_desc = {
        key: (titel, desc)
        for key, titel, desc, _icon in
        (*HIDDEN_DEFS, *EINMAL_DEFS, FRUEHSTARTER_DEF, EARLY_BIRD_DEF)
    }
    return {
        key: (emoji, *titel_desc[key])
        for key, emoji in EMOJIS.items()
        if key in titel_desc
    }


SHOWCASE_INFO = _showcase_info()
```

In `schemas.py` vor `ComparisonUser`:

```python
class Auszeichnung(BaseModel):
    emoji: str
    title: str
    description: str
```

und in `ComparisonUser` unter `emojis`:

```python
    auszeichnungen: list[Auszeichnung] = []
```

In `comparison.py`: Import `EMOJIS` durch `EMOJIS, SHOWCASE_INFO` ersetzen, `Auszeichnung` aus `..schemas` mitimportieren; die Emoji-Sammlung (Zeile 62–69) erweitern:

```python
    emojis_by_user: dict[int, list[str]] = defaultdict(list)
    auszeichnungen_by_user: dict[int, list[Auszeichnung]] = defaultdict(list)
    for ul in emoji_rows:
        info = SHOWCASE_INFO.get(ul.key)
        if info is None:
            continue
        emoji, titel, desc = info
        emojis_by_user[ul.user_id].append(emoji)
        auszeichnungen_by_user[ul.user_id].append(
            Auszeichnung(emoji=emoji, title=titel, description=desc)
        )
```

und im `ComparisonUser(...)`-Konstruktor (Zeile ~110): `auszeichnungen=auszeichnungen_by_user.get(user.id, []),` ergänzen.

- [ ] **Step 4:** `uv run pytest tests/test_comparison.py tests/test_comparison_seen.py -q` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(achievements): Comparison liefert Titel+Beschreibung der Auszeichnungen"` (mit den drei Backend-Dateien + Test).

---

### Task 5: Auszeichnungs-Popover im Frontend (A6 Frontend)

**Files:**
- Create: `frontend/src/components/ui/AuszeichnungsBadges.tsx`
- Test (create): `frontend/src/components/ui/AuszeichnungsBadges.test.tsx`
- Modify: `frontend/src/api/client.ts` (Typen), `frontend/src/components/comparison/RaceBahnen.tsx:99-103`, `frontend/src/components/bets/BetCard.tsx:38` (Spieler-Typ), `frontend/src/components/bets/Blackboard.tsx:44-49`, `frontend/src/pages/Wetten.tsx:33-37`

- [ ] **Step 1: Typen** — in `client.ts` ergänzen:

```ts
export type Auszeichnung = { emoji: string; title: string; description: string }
```

und in `ComparisonUser`: `auszeichnungen?: Auszeichnung[]`.

- [ ] **Step 2: Failing Component-Test** — `AuszeichnungsBadges.test.tsx`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import AuszeichnungsBadges from './AuszeichnungsBadges'

const liste = [{ emoji: '🎩', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.' }]

it('zeigt Popover mit Titel und Beschreibung beim Klick', () => {
  render(<AuszeichnungsBadges liste={liste} />)
  expect(screen.queryByText('Hattrick')).toBeNull()
  fireEvent.click(screen.getByText('🎩'))
  expect(screen.getByText('Hattrick')).toBeInTheDocument()
  expect(screen.getByText('Drei Aktivitäten an einem Tag.')).toBeInTheDocument()
  fireEvent.click(screen.getByText('🎩'))
  expect(screen.queryByText('Hattrick')).toBeNull()
})
```

- [ ] **Step 3:** `npx vitest run src/components/ui/AuszeichnungsBadges.test.tsx` → FAIL (Modul fehlt).

- [ ] **Step 4: Implementieren** — `AuszeichnungsBadges.tsx` (span statt button, weil es in RaceBahnen INNERHALB eines `<button>` sitzt — verschachtelte Buttons sind invalides HTML):

```tsx
import { useState } from 'react'
import type { Auszeichnung } from '../../api/client'

/** Emoji-Badges mit Popover (Hover + Tap): "🎩 Hattrick — Drei Aktivitäten…" */
export default function AuszeichnungsBadges({ liste }: { liste: Auszeichnung[] }) {
  const [offen, setOffen] = useState<number | null>(null)
  if (liste.length === 0) return null
  return (
    <span className="relative ml-1.5 text-xs">
      {liste.map((a, i) => (
        <span
          key={`${a.emoji}-${i}`}
          role="button"
          tabIndex={0}
          className="cursor-help"
          onMouseEnter={() => setOffen(i)}
          onMouseLeave={() => setOffen((o) => (o === i ? null : o))}
          onClick={(e) => {
            e.stopPropagation()
            e.preventDefault()
            setOffen((o) => (o === i ? null : i))
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') setOffen((o) => (o === i ? null : i))
          }}
        >
          {a.emoji}
          {offen === i && (
            <span className="absolute bottom-full left-0 z-40 mb-1.5 w-56 rounded-xl border border-line bg-card p-2 text-left shadow-lg">
              <span className="block text-xs font-bold text-ink">
                {a.emoji} {a.title}
              </span>
              <span className="block text-[11px] font-normal text-ink-mute">
                {a.description}
              </span>
            </span>
          )}
        </span>
      ))}
    </span>
  )
}
```

- [ ] **Step 5:** Test → PASS.

- [ ] **Step 6: Einbauen.** `RaceBahnen.tsx`: Import ergänzen, die Zeilen 99–103 (`<span … title="Erspielte Auszeichnungen">{(u.emojis ?? []).join(' ')}</span>`) ersetzen durch:

```tsx
                    <AuszeichnungsBadges liste={u.auszeichnungen ?? []} />
```

`BetCard.tsx:38`: `export type Spieler = { user_id: number; display_name: string; emojis?: string[]; auszeichnungen?: Auszeichnung[] }` (Import des Typs ergänzen). `Wetten.tsx:33-37`: beim Spieler-Mapping `auszeichnungen: u.auszeichnungen ?? [],` mitgeben. `Blackboard.tsx`: die `name()`-Funktion liefert nur noch den Namen (ohne Emoji-Join); überall wo `{name(id)}` gerendert wird, dahinter `<AuszeichnungsBadges liste={auszeichnungenVon(id)} />` rendern — Helper in der Komponente:

```tsx
  const auszeichnungenVon = (id: number | undefined) =>
    spieler.find((sp) => sp.user_id === id)?.auszeichnungen ?? []
```

Achtung: In `Blackboard.tsx` Zeile 88–90 wird `name()` in JSX-Text interpoliert — auf Fragmente umbauen, z. B. `{name(b.creator_id)}<AuszeichnungsBadges liste={auszeichnungenVon(b.creator_id)} /> ⚔️ {name(b.params.opponent_id)}<AuszeichnungsBadges …/>`; für `beteiligte(...).map(...)` analog pro Person ein Fragment.

- [ ] **Step 7:** `npx vitest run src/components/comparison/RaceBahnen.test.tsx src/components/bets/Blackboard.test.tsx` — bestehende Erwartungen an den Emoji-Join anpassen (Emoji ist jetzt ein eigenes Element statt Teil des Namens-Strings) → PASS.

- [ ] **Step 8: Commit** — `git commit -m "feat(achievements): Popover mit Titel+Beschreibung an Emoji-Badges"`.

---

### Task 6: Platzierungen ohne „P" + Rückstand-Zeile weg (A3 + A4)

**Files:**
- Modify: `frontend/src/components/comparison/RaceBahnen.tsx` (Zeilen 41, 78–79, 88–94, 113–115), `frontend/src/pages/Archiv.tsx:47`, `frontend/src/components/bets/PunkteRanking.tsx:28`, `frontend/src/components/comparison/PersonDetail.tsx:36`
- Test: `frontend/src/components/comparison/RaceBahnen.test.tsx`

- [ ] **Step 1: Tests anpassen** — in `RaceBahnen.test.tsx` Erwartungen auf `P1`/`auf P1` suchen: `P1` → `1`, und Assertions auf die Rückstand-Zeile (`auf P1`) ersatzlos streichen bzw. in `expect(screen.queryByText(/auf P1/)).toBeNull()` umdrehen.

- [ ] **Step 2:** `npx vitest run src/components/comparison/RaceBahnen.test.tsx` → FAIL.

- [ ] **Step 3: Implementieren.**
  - `RaceBahnen.tsx`: Zeile 93 `P{u.rank}` → `{u.rank}`. Zeilen 113–115 (`{!fuehrt && (<p …>−{abstand} km auf P1</p>)}`) komplett löschen. Zeilen 78–79 (`const abstand = …`) und Zeile 41 (`const fuehrend = …`) löschen (beide nur dafür da).
  - `Archiv.tsx:47`: `P{u.rank}` → `{u.rank}`.
  - `PunkteRanking.tsx:28`: `P{e.rank}` → `{e.rank}`.
  - `PersonDetail.tsx:36`: `P{user.rank} · {…} km gewertet` → `Platz {user.rank} · {…} km gewertet` (mitten im Satz liest sich die nackte Zahl nicht — bewusste Abweichung, in Listen bleibt es die nackte Zahl).

- [ ] **Step 4:** `npx vitest run src/components/comparison src/components/bets` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(vergleich): Platzierungen ohne P-Praefix, Rueckstand-Zeile entfernt"`.

---

### Task 7: Archiv ins Saison-Dropdown (A1)

**Files:**
- Create: `frontend/src/components/comparison/WarmupArchiv.tsx` (Inhalt aus `pages/Archiv.tsx`)
- Modify: `frontend/src/pages/Vergleich.tsx`, `frontend/src/components/ui/tabs.ts:16`, `frontend/src/App.tsx` (Zeilen 6, 63)
- Delete: `frontend/src/pages/Archiv.tsx`
- Test: `frontend/src/components/ui/tabs.test.ts`, ggf. `frontend/src/pages/*.test.tsx`

- [ ] **Step 1: Komponente extrahieren** — `WarmupArchiv.tsx` anlegen: kompletter JSX-Inhalt von `Archiv.tsx`, aber als `export default function WarmupArchiv({ year }: { year: number })` — die `seasons`-Query und die `year`-Berechnung entfallen (kommt als Prop), Rest identisch (inkl. der beiden Queries `comparisonWarmup(year)` und `warmupAchievements`; Import-Pfade von `../` auf `../../` anpassen). Danach `pages/Archiv.tsx` löschen.

- [ ] **Step 2: Vergleich.tsx umbauen.**

```tsx
  const [gewaehlt, setGewaehlt] = useState<number | 'archiv' | null>(null)
  const aktive = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const archiv = gewaehlt === 'archiv'
  const year = archiv || gewaehlt === null ? aktive : gewaehlt
  const { data, error } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
    enabled: !archiv,
  })
```

Select (Zeilen 101–112) ersetzen:

```tsx
        <Select
          label="Saison"
          value={archiv ? 'archiv' : year}
          onChange={(e) =>
            setGewaehlt(e.target.value === 'archiv' ? 'archiv' : Number(e.target.value))
          }
        >
          {[...seasons].sort((a, b) => b.year - a.year).map((s) => (
            <option key={s.id} value={s.year}>
              {saisonLabel(s)}
            </option>
          ))}
          <option value="archiv">Archiv (Warm-up)</option>
        </Select>
```

Ansicht-Buttons und MM/km-Toggle im Archiv-Modus ausblenden: den `{ANSICHTEN.map(…)}`-Block und den MM/km-`<div>` jeweils in `{!archiv && (…)}` wrappen. Rendering unten:

```tsx
      {archiv && <WarmupArchiv year={aktive} />}
      {!archiv && data && ansicht === 'rennen' && <RaceBahnen data={data} mode={mode} />}
      {!archiv && data && ansicht === 'verlauf' && <JahresVerlauf data={data} mode={mode} />}
      {!archiv && data && ansicht === 'sportmix' && <SportMix data={data} mode={mode} />}
```

(Fehleranzeige `{error && …}` ebenfalls mit `!archiv &&` guarden.)

- [ ] **Step 3: Tab + Route entfernen.** `tabs.ts`: die Archiv-Zeile (`{ to: '/archiv', … }`) löschen. `App.tsx`: Import `Archiv` (Zeile 6) und Route `/archiv` (Zeile 63) löschen — die `*`-Route leitet alte `/archiv`-Bookmarks auf `/` um.

- [ ] **Step 4: Tests.** `npx vitest run src/components/ui/tabs.test.ts` — Erwartungen, die den Archiv-Tab referenzieren (z. B. `abStart`-Filterung), auf einen synthetischen Tab oder den neuen Tab-Bestand umstellen. Danach `npx vitest run` (kompletter Lauf) → PASS; `npm run build` → OK.

- [ ] **Step 5: Commit** — `git commit -m "feat(vergleich): Archiv als Saison-Dropdown-Option statt eigenem Tab"`.

---

### Task 8: Aktivitäts-Titel mehrzeilig (A5)

**Files:**
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx:137`, `frontend/src/components/comparison/PersonDetail.tsx:54`

- [ ] **Step 1:** `MeineAktivitaeten.tsx:137`: `className="truncate text-xs text-ink-mute"` → `className="break-words text-xs text-ink-mute"`. `PersonDetail.tsx:54`: `className="min-w-0 flex-1 truncate text-ink"` → `className="min-w-0 flex-1 break-words text-ink"`.

- [ ] **Step 2:** `npx vitest run src/pages/MeineAktivitaeten.test.tsx` → PASS (Snapshot-/Klassen-Erwartungen ggf. anpassen).

- [ ] **Step 3: Commit** — `git commit -m "fix(aktivitaeten): lange Strava-Titel brechen um statt abgeschnitten"`.

---

### Task 9: MM-Logo statt Blitz (A8)

**Files:**
- Modify: `frontend/public/icons.svg` (Symbol ergänzen), `frontend/src/components/ui/Layout.tsx:41`

- [ ] **Step 1:** In `icons.svg` vor `</defs>` das Logo-Symbol ergänzen (Zickzack-„M" aus `favicon.svg`, ohne Kasten):

```svg
    <symbol id="logo" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 40 H9 L20.9 25 L24.75 40 L35.6 25 L38.75 40 L50.3 25 L55.2 40 H60"/></symbol>
```

- [ ] **Step 2:** `Layout.tsx:41`: `<Icon name="blitz" size={16} className="text-accent" />` → `<Icon name="logo" size={16} className="text-accent" />`.

- [ ] **Step 3:** `npm run build` → OK; im Browser (`npm run dev`) prüfen: Zickzack-M neben „METERMACHEN". Hinweis: `frontend/dist/icons.svg` NICHT anfassen (Build-Artefakt).

- [ ] **Step 4: Commit** — `git commit -m "feat(ui): MM-Logo statt Blitz in der Top-Leiste"`.

---

### Task 10: Aktive Tabs/Umschalter ohne Umrandung (A9)

**Files:**
- Modify: `frontend/src/components/ui/Layout.tsx:14-19` (`pill`), `frontend/src/pages/Vergleich.tsx:67-71` (ANSICHTEN-Buttons)

- [ ] **Step 1:** `Layout.tsx` `pill` ersetzen:

```ts
const pill = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 px-3 py-1 text-sm transition ${
    isActive
      ? 'font-bold text-accent [text-shadow:var(--t-glow)]'
      : 'text-ink-mute hover:text-ink'
  }`
```

- [ ] **Step 2:** `Vergleich.tsx` ANSICHTEN-Button-Klassen ersetzen (Umrandung auch bei inaktiven weg):

```tsx
            className={`flex items-center gap-1.5 px-4 py-1 text-sm transition ${
              ansicht === a.key
                ? 'font-bold text-accent [text-shadow:var(--t-glow)]'
                : 'text-ink-mute hover:text-ink'
            }`}
```

Der MM/km-Toggle daneben bleibt unverändert.

- [ ] **Step 3:** `npx vitest run` → PASS; optisch im Dev-Server prüfen (Desktop-Breite!).

- [ ] **Step 4: Commit** — `git commit -m "style(ui): aktive Tabs/Umschalter mit Neon-Glow statt Pill-Umrandung"`.

---

### Task 11: Gesamtverifikation + PR

- [ ] **Step 1:** `cd backend && uv run pytest -q` → alles PASS.
- [ ] **Step 2:** `cd frontend && npx vitest run && npm run build` → alles PASS/OK.
- [ ] **Step 3:** Push + PR gegen `main`:

```bash
git push -u origin feature/quick-fixes-ui
gh pr create --title "Quick-Fixes: Archiv-Dropdown, Saison 2026/27, Ranking-Optik, Titel, Tooltips, 5-MM-Streak" --body "Setzt Teil A der Spec docs/superpowers/specs/2026-07-25-anpassungen-und-newsfeed-design.md um (A1-A9)."
```

## Self-Review (erledigt)

- Spec-Abdeckung: A1→Task 7, A2→Tasks 1+2, A3+A4→Task 6, A5→Task 8, A6→Tasks 4+5, A7→Task 3, A8→Task 9, A9→Task 10. Vollständig.
- Typen konsistent: `Auszeichnung {emoji,title,description}` identisch in Backend-Schema (Task 4), client.ts und Component (Task 5). `SHOWCASE_INFO` wird in PR 2 wiederverwendet.
- Reihenfolge: Task 6 (P-Präfix) ändert `Archiv.tsx` VOR der Extraktion in Task 7 — beim Extrahieren den dann aktuellen Stand übernehmen.
