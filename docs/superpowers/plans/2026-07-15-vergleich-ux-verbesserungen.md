# Vergleichs-Views UX-Verbesserungen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vier UX-Verbesserungen der Vergleichs-Views umsetzen: MM/km-Einheiten-Toggle, Sport-Piktogramme im Sport-Mix-Balken, Personen-Filter im Verlauf, „Seit letztem Besuch"-Animation im Rennen.

**Architecture:** Frontend (React/TS) bekommt einen kleinen Einheiten-Helper (`unit.ts`, localStorage-gestützt) und einen reinen Diff-Helper (`sinceLastSeen.ts`); die drei Vergleichs-Komponenten werden erweitert. Backend (FastAPI/SQLModel) bekommt eine neue Tabelle `ComparisonSeen` plus zwei Endpoints; die Standings-Berechnung wird in eine wiederverwendbare Funktion extrahiert.

**Tech Stack:** React 19, TypeScript, Vitest, @testing-library/react, recharts, Tailwind · FastAPI, SQLModel, SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-07-15-vergleich-ux-verbesserungen-design.md`

---

## File Structure

**Neu (Frontend):**
- `frontend/src/components/comparison/unit.ts` — `UnitMode`, `useUnitMode()` (localStorage), `toDisplay()`, `unitLabel()`.
- `frontend/src/components/comparison/unit.test.ts`
- `frontend/src/components/comparison/sinceLastSeen.ts` — reine Diff-Logik + Banner-Text.
- `frontend/src/components/comparison/sinceLastSeen.test.ts`

**Geändert (Frontend):**
- `frontend/src/api/client.ts` — Typen `SeenEntry`/`LastSeen` + `lastSeenComparison`/`markComparisonSeen`.
- `frontend/src/pages/Vergleich.tsx` — MM/km-Toggle + `mode`-Prop an die drei Views.
- `frontend/src/components/comparison/RaceBahnen.tsx` — Einheit (F1) + Seit-Besuch-Animation (F2).
- `frontend/src/components/comparison/SportMix.tsx` — Einheit (F1) + Sport-Piktogramme (F3).
- `frontend/src/components/comparison/JahresVerlauf.tsx` — Einheit/km-Achse (F1) + Personen-Filter (F4).

**Neu (Backend):**
- `backend/tests/test_comparison_seen.py`

**Geändert (Backend):**
- `backend/app/models.py` — Model `ComparisonSeen`.
- `backend/app/schemas.py` — `LastSeenEntry`, `LastSeenOut`.
- `backend/app/routers/comparison.py` — `compute_comparison()`-Refactor + GET `last-seen` + POST `seen`.

**Befehle:**
- Frontend-Test einzeln: `cd frontend && npx vitest run <pfad>`
- Frontend alle: `cd frontend && npm test`
- Frontend Build/Typecheck: `cd frontend && npm run build`
- Backend-Test: `cd backend && uv run pytest <pfad> -v`

---

## Task 1: Einheiten-Helper (`unit.ts`)

**Files:**
- Create: `frontend/src/components/comparison/unit.ts`
- Test: `frontend/src/components/comparison/unit.test.ts`

- [ ] **Step 1: Failing test schreiben**

`frontend/src/components/comparison/unit.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { toDisplay, unitLabel } from './unit'

describe('unit helpers', () => {
  it('MM-Modus gibt den skalierten Wert unverändert zurück', () => {
    expect(toDisplay(130, 1.3, 'mm')).toBe(130)
  })
  it('km-Modus teilt durch den km_factor', () => {
    expect(toDisplay(130, 1.3, 'km')).toBeCloseTo(100)
  })
  it('km_factor 1 liefert in beiden Modi denselben Wert', () => {
    expect(toDisplay(120, 1, 'km')).toBe(120)
    expect(toDisplay(120, 1, 'mm')).toBe(120)
  })
  it('faktor 0 wird abgefangen (kein Division-durch-0)', () => {
    expect(toDisplay(50, 0, 'km')).toBe(50)
  })
  it('unitLabel benennt die Modi', () => {
    expect(unitLabel('mm')).toBe('MM')
    expect(unitLabel('km')).toBe('km')
  })
})
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/components/comparison/unit.test.ts`
Expected: FAIL (`Cannot find module './unit'`).

- [ ] **Step 3: `unit.ts` implementieren**

`frontend/src/components/comparison/unit.ts`:
```ts
import { useEffect, useState } from 'react'

export type UnitMode = 'mm' | 'km'

const KEY = 'mm_unit_mode'

/** MM (skaliert, Standard) vs. echte km. Auswahl wird im Browser gemerkt. */
export function useUnitMode() {
  const [mode, setMode] = useState<UnitMode>(() =>
    localStorage.getItem(KEY) === 'km' ? 'km' : 'mm',
  )
  useEffect(() => {
    localStorage.setItem(KEY, mode)
  }, [mode])
  return { mode, toggle: () => setMode((m) => (m === 'mm' ? 'km' : 'mm')) }
}

/** Skalierte MM in die anzuzeigende Einheit umrechnen. km = MM / km_factor. */
export function toDisplay(scaledKm: number, kmFactor: number, mode: UnitMode): number {
  return mode === 'km' && kmFactor > 0 ? scaledKm / kmFactor : scaledKm
}

export const unitLabel = (mode: UnitMode): string => (mode === 'km' ? 'km' : 'MM')
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `cd frontend && npx vitest run src/components/comparison/unit.test.ts`
Expected: PASS (5 Tests grün).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/unit.ts frontend/src/components/comparison/unit.test.ts
git commit -m "feat(vergleich): Einheiten-Helper MM/km (unit.ts)"
```

---

## Task 2: MM/km-Toggle verdrahten + Rennen-Einheit (F1)

**Files:**
- Modify: `frontend/src/pages/Vergleich.tsx`
- Modify: `frontend/src/components/comparison/RaceBahnen.tsx`

- [ ] **Step 1: `mode`-Prop in RaceBahnen ergänzen (optional, Default `'mm'`)**

In `frontend/src/components/comparison/RaceBahnen.tsx` den Import und die Signatur ändern.

Import oben ergänzen (nach den bestehenden Imports):
```ts
import { toDisplay, unitLabel, type UnitMode } from './unit'
```

Signatur (Zeile 9) ersetzen:
```ts
export default function RaceBahnen({ data, mode = 'mm' }: { data: Comparison; mode?: UnitMode }) {
```

- [ ] **Step 2: Zahl-Readout im Rennen auf Einheit umstellen**

In `RaceBahnen.tsx` den rechten Wert (aktuell Zeilen ~98-101) ersetzen:
```tsx
              <p className="w-24 shrink-0 text-right text-lg font-black tabular-nums text-ink">
                {Math.round(toDisplay(u.total_scaled_km, u.km_factor, mode))}{' '}
                <span className="text-xs font-normal text-ink-mute">{unitLabel(mode)}</span>
              </p>
```

Hinweis: Bahnenlänge (`pct`, `maxKm`), Rangfolge und `abstand` bleiben in MM — **nur die Zahl** ändert sich (Variante A, Ranking bleibt).

- [ ] **Step 3: Toggle + `mode` in Vergleich.tsx**

In `frontend/src/pages/Vergleich.tsx`:

Import ergänzen (nach den bestehenden Component-Imports):
```ts
import { useUnitMode } from '../components/comparison/unit'
```

In der Komponente nach `const [ansicht, ...]` (Zeile ~46) einfügen:
```ts
  const { mode, toggle: toggleUnit } = useUnitMode()
```

Den MM/km-Umschalter direkt vor das `<Select label="Jahr" …>` einsetzen (in derselben Flex-Zeile, vor dem Select — das Select behält `ml-auto` und schiebt beide nach rechts; den Umschalter mit eigenem `ml-auto` versehen und beim Select `ml-auto` entfernen):

Select-Zeile: `className="ml-auto w-24"` → `className="w-24"`.

Davor einfügen:
```tsx
        <div className="ml-auto flex overflow-hidden rounded-full border border-line text-xs">
          <button
            type="button"
            onClick={() => {
              if (mode !== 'mm') toggleUnit()
            }}
            className={`px-3 py-1 font-bold transition ${
              mode === 'mm' ? 'bg-accent text-accent-ink' : 'text-ink-mute hover:text-ink'
            }`}
          >
            MM
          </button>
          <button
            type="button"
            onClick={() => {
              if (mode !== 'km') toggleUnit()
            }}
            className={`px-3 py-1 font-bold transition ${
              mode === 'km' ? 'bg-accent text-accent-ink' : 'text-ink-mute hover:text-ink'
            }`}
          >
            km
          </button>
        </div>
```

- [ ] **Step 4: `mode` an die drei Views durchreichen**

Die drei Render-Zeilen (unten in Vergleich.tsx) ersetzen:
```tsx
      {data && ansicht === 'rennen' && <RaceBahnen data={data} mode={mode} />}
      {data && ansicht === 'verlauf' && <JahresVerlauf data={data} mode={mode} />}
      {data && ansicht === 'sportmix' && <SportMix data={data} mode={mode} />}
```

(JahresVerlauf und SportMix bekommen die `mode`-Prop in Task 3/5/6; bis dahin ignorieren sie sie — daher jetzt schon optional halten. Damit der Typecheck grün bleibt, in **beiden** Komponenten die Signatur vorab auf optional erweitern: siehe Step 5.)

- [ ] **Step 5: Signaturen von SportMix & JahresVerlauf vorab optional machen (Typecheck)**

`frontend/src/components/comparison/SportMix.tsx` — Import + Signatur:
```ts
import { type UnitMode } from './unit'
```
```ts
export default function SportMix({ data }: { data: Comparison; mode?: UnitMode }) {
```
(Der Parameter wird in Task 4 genutzt; das `mode?` im Typ reicht fürs Durchreichen.)

`frontend/src/components/comparison/JahresVerlauf.tsx` — Import + Signatur:
```ts
import { type UnitMode } from './unit'
```
```ts
export default function JahresVerlauf({ data }: { data: Comparison; mode?: UnitMode }) {
```

- [ ] **Step 6: Build/Typecheck + bestehende Tests**

Run: `cd frontend && npm run build`
Expected: Build ok, kein TS-Fehler.
Run: `cd frontend && npx vitest run src/components/comparison/RaceBahnen.test.tsx`
Expected: PASS (bestehender Test unverändert grün, da `mode` optional).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Vergleich.tsx frontend/src/components/comparison/RaceBahnen.tsx frontend/src/components/comparison/SportMix.tsx frontend/src/components/comparison/JahresVerlauf.tsx
git commit -m "feat(vergleich): MM/km-Toggle im Header + Rennen-Readout (F1)"
```

---

## Task 3: Sport-Piktogramme im Balken + Sport-Mix-Einheit (F3 + F1)

**Files:**
- Modify: `frontend/src/components/comparison/SportMix.tsx`
- Test: `frontend/src/components/comparison/SportMix.test.tsx`

- [ ] **Step 1: Failing test ergänzen (Icon ab Breite + Einheit)**

In `frontend/src/components/comparison/SportMix.test.tsx`:

**Zuerst** die bestehende Assertion anpassen — der Gesamtwert rendert künftig als „300 MM" (Zahl + Einheiten-Span), der exakte Match `getByText('300')` bricht dann:
```ts
    expect(screen.getByText(/^300/)).toBeInTheDocument()
```
(`/^300/` matcht nur den Wert-Span, dessen textContent mit „300" beginnt — Eltern-Elemente beginnen mit „P1Erik…".)

**Dann** innerhalb `describe('SportMix', …)` zwei Tests ergänzen. Die Testdaten oben haben Erik mit Laufen 200 (66,7 %) und Radfahren 100 (33,3 %) — beide über der 9 %-Schwelle → beide Icons sichtbar.

```ts
  it('zeigt Sportart-Piktogramme in ausreichend breiten Segmenten', () => {
    renderMix()
    // Icon rendert als <svg> mit aria-label = Kategoriename
    expect(screen.getByLabelText('Laufen')).toBeInTheDocument()
    expect(screen.getByLabelText('Radfahren')).toBeInTheDocument()
  })

  it('blendet Piktogramme in sehr schmalen Segmenten aus', () => {
    const schmal: Comparison = {
      ...data,
      users: [
        {
          ...data.users[0],
          by_category: [
            { category_id: 1, name: 'Laufen', color: '#f00', icon: 'laufen', scaled_km: 195 },
            { category_id: 2, name: 'Radfahren', color: '#00f', icon: 'rad', scaled_km: 5 }, // 2,5 % < 9 %
          ],
        },
      ],
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <SportMix data={schmal} />
      </QueryClientProvider>,
    )
    expect(screen.getByLabelText('Laufen')).toBeInTheDocument()
    expect(screen.queryByLabelText('Radfahren')).not.toBeInTheDocument()
  })
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/components/comparison/SportMix.test.tsx`
Expected: FAIL (`getByLabelText('Laufen')` findet nichts — Icons noch nicht gerendert).

- [ ] **Step 3: Icon-Komponente mit `aria-label` erweitern (testbar + a11y)**

`frontend/src/components/ui/Icon.tsx` ersetzen, damit ein optionales Label gesetzt werden kann:
```tsx
type Props = { name: string; size?: number; className?: string; label?: string }

export default function Icon({ name, size = 20, className = '', label }: Props) {
  return (
    <svg
      width={size}
      height={size}
      className={className}
      aria-hidden={label ? undefined : 'true'}
      aria-label={label}
      role={label ? 'img' : undefined}
    >
      <use href={`/icons.svg#${name}`} />
    </svg>
  )
}
```

- [ ] **Step 4: Piktogramm + Einheit in SportMix implementieren**

In `frontend/src/components/comparison/SportMix.tsx`:

Imports ergänzen:
```ts
import Icon from '../ui/Icon'
import { toDisplay, unitLabel, type UnitMode } from './unit'
```
Signatur auf genutzten Parameter erweitern:
```ts
export default function SportMix({ data, mode = 'mm' }: { data: Comparison; mode?: UnitMode }) {
```

Die Balken-Höhe von `h-4` auf `h-6` erhöhen (Segment-Container, aktuell `className="flex h-4 flex-1 …"`):
```tsx
              <div className="flex h-6 flex-1 overflow-hidden rounded-full bg-surface">
```

Das Segment-`<span>` (aktuell nur farbige Fläche) so ersetzen, dass ab ≥ 9 % Breite das weiße Piktogramm zentriert erscheint:
```tsx
                {u.by_category.map((c) => {
                  const anteil = gesamt > 0 ? (c.scaled_km / gesamt) * 100 : 0
                  return (
                    <span
                      key={c.category_id}
                      title={`${c.name}: ${Math.round(toDisplay(c.scaled_km, u.km_factor, mode))} ${unitLabel(mode)}`}
                      className="balken-wachsen flex h-full items-center justify-center"
                      style={{ width: `${anteil}%`, background: c.color }}
                    >
                      {anteil >= 9 && (
                        <Icon
                          name={c.icon}
                          size={14}
                          label={c.name}
                          className="text-white [filter:drop-shadow(0_1px_1px_rgba(0,0,0,.5))]"
                        />
                      )}
                    </span>
                  )
                })}
```

Den rechten Gesamtwert auf die Einheit umstellen (aktuell `{Math.round(gesamt)}`):
```tsx
              <span className="w-24 text-right font-mono text-sm font-bold tabular-nums text-ink">
                {Math.round(toDisplay(gesamt, u.km_factor, mode))}{' '}
                <span className="text-[10px] font-normal text-ink-mute">{unitLabel(mode)}</span>
              </span>
```

Hinweis: `gesamt` bleibt die Summe der skalierten `by_category`-Werte (= `total_scaled`); `toDisplay(gesamt, u.km_factor, mode)` liefert im km-Modus die echten km.

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `cd frontend && npx vitest run src/components/comparison/SportMix.test.tsx`
Expected: PASS (alte + neue Tests grün).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/comparison/SportMix.tsx frontend/src/components/comparison/SportMix.test.tsx frontend/src/components/ui/Icon.tsx
git commit -m "feat(vergleich): Sport-Piktogramme im Balken + Einheit im Sport-Mix (F3/F1)"
```

---

## Task 4: Verlauf — km-Achse & Ziel-Linien (F1)

**Files:**
- Modify: `frontend/src/components/comparison/JahresVerlauf.tsx`

- [ ] **Step 1: `mode` nutzen — Kurvenwerte, Achse, Referenzlinien**

In `frontend/src/components/comparison/JahresVerlauf.tsx`:

Import ergänzen (Helper):
```ts
import { unitLabel, type UnitMode } from './unit'
```
Signatur:
```ts
export default function JahresVerlauf({ data, mode = 'mm' }: { data: Comparison; mode?: UnitMode }) {
```

Beim Merge der Kurven-Datenpunkte die Werte im km-Modus durch den `km_factor` der Person teilen. Den Block (aktuell Zeilen ~22-29) ersetzen:
```tsx
  const byDate = new Map<string, Record<string, number | string>>()
  for (const u of data.users) {
    const faktor = mode === 'km' && u.km_factor > 0 ? u.km_factor : 1
    for (const p of u.cumulative) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[u.display_name] = p.scaled_km / faktor
      byDate.set(p.date, row)
    }
  }
```

Die YAxis-Einheit dynamisch machen (aktuell `unit=" km"`):
```tsx
          <YAxis fontSize={11} unit={` ${unitLabel(mode)}`} stroke="var(--t-ink-mute)" tickLine={false} axisLine={false} />
```

Ziel- und Meilenstein-Referenzlinien nur im MM-Modus rendern (in MM definiert, pro Person nicht auf km übertragbar). Den Meilenstein-`map` und die Ziel-`ReferenceLine` (aktuell Zeilen ~67-81) in eine Bedingung hüllen:
```tsx
          {mode === 'mm' && data.milestones.map((m) => (
            <ReferenceLine
              key={m.km}
              y={m.km}
              stroke="var(--t-ink-mute)"
              strokeOpacity={0.5}
              strokeDasharray="5 4"
              label={{ value: m.label, fontSize: 11, position: 'right', fill: 'var(--t-ink-mute)' }}
            />
          ))}
          {mode === 'mm' && (
            <ReferenceLine
              y={data.goal_km}
              stroke="var(--t-accent)"
              label={{ value: 'Ziel', fontSize: 11, fill: 'var(--t-accent)' }}
            />
          )}
```

- [ ] **Step 2: Build/Typecheck + bestehender Test**

Run: `cd frontend && npm run build`
Expected: ok.
Run: `cd frontend && npx vitest run src/components/comparison/JahresVerlauf.test.tsx`
Expected: PASS (bestehender Test grün, Default `mode='mm'`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/comparison/JahresVerlauf.tsx
git commit -m "feat(vergleich): Verlauf km-Achse + Ziel-Linien nur in MM (F1)"
```

---

## Task 5: Verlauf — Personen-Filter (F4)

**Files:**
- Modify: `frontend/src/components/comparison/JahresVerlauf.tsx`
- Test: `frontend/src/components/comparison/JahresVerlauf.test.tsx`

- [ ] **Step 1: Failing test schreiben**

Die Datei `JahresVerlauf.test.tsx` hat bereits einen `vi.mock('../../api/client', …)` mit `userActivities`/„Morgenlauf" und ein `describe` mit einem Detail-Test (klickt `getByLabelText('Details zu Erik')` — bleibt gültig, weil der „i"-Button dieses aria-label behält). `fireEvent` ist bereits importiert. Folgende Tests im `describe` ergänzen:
```ts
  it('togglet eine Kurve über den Chip und schaltet mit Alle/Keine', () => {
    const zwei: Comparison = {
      year: 2026, goal_km: 1000, milestones: [], start_date: null, phase: 'challenge',
      users: [
        { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, km_factor: 1,
          by_category: [], segments: [], cumulative: [{ date: '2026-01-01', scaled_km: 300 }] },
        { user_id: 2, display_name: 'Lisa', avatar: 'icon:laufen', rank: 2, total_scaled_km: 200, km_factor: 1,
          by_category: [], segments: [], cumulative: [{ date: '2026-01-01', scaled_km: 200 }] },
      ],
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={qc}><JahresVerlauf data={zwei} /></QueryClientProvider>)
    // Toggle-Chip hat aria-pressed
    const chip = screen.getByRole('button', { name: 'Erik ein-/ausblenden' })
    expect(chip).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(chip)
    expect(chip).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Keine' }))
    expect(screen.getByRole('button', { name: 'Lisa ein-/ausblenden' })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Alle' }))
    expect(screen.getByRole('button', { name: 'Lisa ein-/ausblenden' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('öffnet Detail über den i-Button am Chip', async () => {
    const zwei: Comparison = {
      year: 2026, goal_km: 1000, milestones: [], start_date: null, phase: 'challenge',
      users: [
        { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, km_factor: 1,
          by_category: [], segments: [], cumulative: [{ date: '2026-01-01', scaled_km: 300 }] },
      ],
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={qc}><JahresVerlauf data={zwei} /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Details zu Erik' }))
    expect(await screen.findByText('Morgenlauf', { exact: false })).toBeInTheDocument()
  })
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/components/comparison/JahresVerlauf.test.tsx`
Expected: FAIL (Chips mit `aria-pressed` / „Alle"/„Keine" existieren noch nicht).

- [ ] **Step 3: Sichtbarkeits-State + Lines filtern**

In `frontend/src/components/comparison/JahresVerlauf.tsx`:

State nach `const [detail, …]` einfügen:
```ts
  const [visible, setVisible] = useState<Set<number>>(() => new Set(data.users.map((u) => u.user_id)))
```

Beim Rendern der Linien nur sichtbare Personen zeichnen. Den `data.users.map((u) => { … <Line/> … })` mit einem Filter beginnen:
```tsx
          {data.users.filter((u) => visible.has(u.user_id)).map((u) => {
```

- [ ] **Step 4: Chip-Leiste umbauen (Toggle + „i" + Alle/Keine)**

Den bestehenden Chip-Block (`<div className="mt-3 flex flex-wrap gap-2">…</div>`) komplett ersetzen:
```tsx
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setVisible(new Set(data.users.map((u) => u.user_id)))}
          className="rounded-full border border-line px-2.5 py-1 text-xs font-bold text-ink-mute transition hover:text-ink"
        >
          Alle
        </button>
        <button
          type="button"
          onClick={() => setVisible(new Set())}
          className="rounded-full border border-line px-2.5 py-1 text-xs font-bold text-ink-mute transition hover:text-ink"
        >
          Keine
        </button>
        {data.users.map((u) => {
          const an = visible.has(u.user_id)
          const farbe = userColor(u.user_id, ids)
          return (
            <span
              key={u.user_id}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
                an ? 'text-ink' : 'text-ink-mute opacity-50'
              }`}
              style={{ borderColor: an ? farbe : 'var(--t-line)' }}
            >
              <button
                type="button"
                aria-pressed={an}
                aria-label={`${u.display_name} ein-/ausblenden`}
                onClick={() =>
                  setVisible((prev) => {
                    const next = new Set(prev)
                    if (next.has(u.user_id)) next.delete(u.user_id)
                    else next.add(u.user_id)
                    return next
                  })
                }
                className="flex items-center gap-1.5"
              >
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: an ? farbe : 'var(--t-ink-mute)' }} />
                {u.display_name}
              </button>
              <button
                type="button"
                aria-label={`Details zu ${u.display_name}`}
                onClick={() => setDetail(u)}
                className="flex h-4 w-4 items-center justify-center rounded-full border border-line text-[9px] text-ink-mute transition hover:border-accent hover:text-accent"
              >
                i
              </button>
            </span>
          )
        })}
      </div>
```

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `cd frontend && npx vitest run src/components/comparison/JahresVerlauf.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/comparison/JahresVerlauf.tsx frontend/src/components/comparison/JahresVerlauf.test.tsx
git commit -m "feat(vergleich): Personen-Filter im Verlauf mit Alle/Keine + i-Detail (F4)"
```

---

## Task 6: Backend — `ComparisonSeen` Model + Schemas

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`

- [ ] **Step 1: Model `ComparisonSeen` ergänzen**

In `backend/app/models.py` oben den Import erweitern:
```python
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel
```
Am Dateiende ergänzen:
```python
class ComparisonSeen(SQLModel, table=True):
    """Letzter vom jeweiligen Betrachter gesehener Vergleichsstand (pro Jahr)."""

    __table_args__ = (UniqueConstraint("user_id", "year", name="uq_seen_user_year"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    year: int = Field(index=True)
    seen_at: datetime = Field(default_factory=utcnow)
    # JSON: [{"user_id": int, "scaled_km": float, "rank": int}, …]
    snapshot_json: str = "[]"
```

Hinweis: Neue Tabelle → wird über `SQLModel.metadata.create_all` in `db.init_db()` automatisch angelegt (kein `migrate()`-Eintrag nötig).

- [ ] **Step 2: Schemas ergänzen**

In `backend/app/schemas.py` am Dateiende ergänzen:
```python
class LastSeenEntry(BaseModel):
    user_id: int
    scaled_km: float
    rank: int


class LastSeenOut(BaseModel):
    seen_at: datetime
    entries: list[LastSeenEntry]
```

- [ ] **Step 3: Import prüfen (Typecheck über Test-Sammlung)**

Run: `cd backend && uv run pytest tests/test_comparison.py -q`
Expected: PASS (bestehende Comparison-Tests unverändert grün; Import-Fehler würden hier auffallen).

- [ ] **Step 4: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py
git commit -m "feat(comparison): ComparisonSeen-Model + LastSeen-Schemas"
```

---

## Task 7: Backend — Endpoints `last-seen` & `seen`

**Files:**
- Modify: `backend/app/routers/comparison.py`
- Test: `backend/tests/test_comparison_seen.py`

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_comparison_seen.py`:
```python
from datetime import date

from sqlmodel import select

from app.models import Activity, ComparisonSeen, Season
from tests.conftest import login, make_category, make_user


def _setup(session):
    erik = make_user(session)
    cat = make_category(session, factor=2.0)  # scaled = distance * 2
    session.add(Season(year=2026, goal_km=1000.0))
    session.commit()
    session.add(Activity(user_id=erik.id, category_id=cat.id, date=date(2026, 1, 10), distance_km=10))
    session.commit()
    return erik


def test_last_seen_null_without_snapshot(client, session):
    _setup(session)
    login(client)
    r = client.get("/api/comparison/2026/last-seen")
    assert r.status_code == 200
    assert r.json() is None


def test_mark_seen_then_last_seen_returns_snapshot(client, session):
    _setup(session)
    login(client)
    r = client.post("/api/comparison/2026/seen")
    assert r.status_code == 200
    entry = r.json()["entries"][0]
    assert entry["scaled_km"] == 20.0
    assert entry["rank"] == 1
    g = client.get("/api/comparison/2026/last-seen").json()
    assert g["entries"][0]["scaled_km"] == 20.0
    assert "seen_at" in g


def test_mark_seen_is_idempotent_per_user_year(client, session):
    _setup(session)
    login(client)
    client.post("/api/comparison/2026/seen")
    client.post("/api/comparison/2026/seen")
    rows = session.exec(select(ComparisonSeen)).all()
    assert len(rows) == 1


def test_seen_requires_login(client, session):
    _setup(session)
    r = client.post("/api/comparison/2026/seen")
    assert r.status_code == 401
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd backend && uv run pytest tests/test_comparison_seen.py -v`
Expected: FAIL (404 auf `/2026/last-seen` — Route existiert nicht).

- [ ] **Step 3: `compute_comparison` extrahieren**

In `backend/app/routers/comparison.py` die bestehende Route so umbauen, dass der Rechenkörper in einer wiederverwendbaren Funktion liegt. Die Funktion `comparison(...)` (Zeilen 22-108) ersetzen durch:

```python
def compute_comparison(
    session: Session, year: int, phase: Literal["challenge", "warmup"] = "challenge"
) -> ComparisonOut:
    season = session.exec(select(Season).where(Season.year == year)).first()
    if season is None:
        raise HTTPException(status_code=404, detail="Kein Jahr konfiguriert")

    users = session.exec(select(User).where(User.is_active).order_by(User.id)).all()
    rows = session.exec(
        select(Activity, Category)
        .join(Category, Activity.category_id == Category.id)
        .order_by(Activity.date, Activity.id)
    ).all()
    rows = [(a, c) for a, c in rows if a.date.year == year]

    start = season.start_date
    if phase == "warmup":
        if start is None:
            raise HTTPException(status_code=404, detail="Keine Warm-up-Phase konfiguriert")
        rows = [(a, c) for a, c in rows if a.date < start]
    elif start is not None and date_type.today() >= start:
        rows = [(a, c) for a, c in rows if a.date >= start]

    by_user: dict[int, list[tuple[Activity, Category]]] = defaultdict(list)
    for a, c in rows:
        by_user[a.user_id].append((a, c))

    result_users = []
    for user in users:
        acts = by_user.get(user.id, [])
        segments, cumulative, shares = [], [], defaultdict(float)
        running = 0.0
        factor = user.km_factor if phase == "challenge" else 1.0
        for a, c in acts:
            scaled = round(a.distance_km * c.factor * factor, 2)
            running = round(running + scaled, 2)
            segments.append(
                Segment(date=a.date, category_id=c.id, color=c.color, scaled_km=scaled)
            )
            cumulative.append(CumulativePoint(date=a.date, scaled_km=running))
            shares[c.id] += scaled
        by_category = [
            CategoryShare(
                category_id=c.id,
                name=c.name,
                color=c.color,
                icon=c.icon,
                scaled_km=round(km, 2),
            )
            for c, km in (
                (session.get(Category, cid), km) for cid, km in shares.items()
            )
        ]
        result_users.append(
            ComparisonUser(
                user_id=user.id,
                display_name=user.display_name,
                avatar=user.avatar,
                km_factor=user.km_factor,
                rank=0,
                total_scaled_km=running,
                by_category=by_category,
                segments=segments,
                cumulative=cumulative,
            )
        )

    result_users.sort(key=lambda u: -u.total_scaled_km)
    for i, u in enumerate(result_users):
        u.rank = i + 1

    return ComparisonOut(
        year=year,
        goal_km=season.goal_km,
        milestones=json.loads(season.milestones_json),
        users=result_users,
        start_date=season.start_date,
        phase=phase,
    )


@router.get(
    "/{year}", response_model=ComparisonOut, dependencies=[Depends(get_current_user)]
)
def comparison(
    year: int,
    phase: Literal["challenge", "warmup"] = "challenge",
    session: Session = Depends(get_session),
):
    return compute_comparison(session, year, phase)
```

- [ ] **Step 4: Neue Endpoints + Imports ergänzen**

Imports in `comparison.py` erweitern:
```python
from ..models import Activity, Category, ComparisonSeen, Season, User, utcnow
from ..schemas import (
    CategoryShare,
    ComparisonOut,
    ComparisonUser,
    CumulativePoint,
    LastSeenEntry,
    LastSeenOut,
    Segment,
)
```

Am Dateiende (nach der `comparison`-Route) ergänzen:
```python
@router.get("/{year}/last-seen", response_model=LastSeenOut | None)
def last_seen(
    year: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    row = session.exec(
        select(ComparisonSeen).where(
            ComparisonSeen.user_id == user.id, ComparisonSeen.year == year
        )
    ).first()
    if row is None:
        return None
    return LastSeenOut(
        seen_at=row.seen_at,
        entries=[LastSeenEntry(**e) for e in json.loads(row.snapshot_json)],
    )


@router.post("/{year}/seen", response_model=LastSeenOut)
def mark_seen(
    year: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    data = compute_comparison(session, year, "challenge")
    entries = [
        LastSeenEntry(user_id=u.user_id, scaled_km=u.total_scaled_km, rank=u.rank)
        for u in data.users
    ]
    row = session.exec(
        select(ComparisonSeen).where(
            ComparisonSeen.user_id == user.id, ComparisonSeen.year == year
        )
    ).first()
    payload = json.dumps([e.model_dump() for e in entries])
    now = utcnow()
    if row is None:
        row = ComparisonSeen(
            user_id=user.id, year=year, seen_at=now, snapshot_json=payload
        )
    else:
        row.seen_at = now
        row.snapshot_json = payload
    session.add(row)
    session.commit()
    return LastSeenOut(seen_at=now, entries=entries)
```

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `cd backend && uv run pytest tests/test_comparison_seen.py tests/test_comparison.py -v`
Expected: PASS (neue + bestehende Comparison-Tests grün).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/comparison.py backend/tests/test_comparison_seen.py
git commit -m "feat(comparison): last-seen/seen Endpoints + compute_comparison-Refactor"
```

---

## Task 8: Frontend — Diff-Helper `sinceLastSeen.ts` (F2)

**Files:**
- Create: `frontend/src/components/comparison/sinceLastSeen.ts`
- Test: `frontend/src/components/comparison/sinceLastSeen.test.ts`

- [ ] **Step 1: Failing test schreiben**

`frontend/src/components/comparison/sinceLastSeen.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { computeSinceLastSeen, describeSinceLastSeen, type UserLike } from './sinceLastSeen'

const users: UserLike[] = [
  { user_id: 1, display_name: 'Erik', total_scaled_km: 130, rank: 1 },
  { user_id: 2, display_name: 'Ben', total_scaled_km: 128, rank: 2 },
]
const NOW = 1_700_000_000_000
const OLD = new Date(NOW - 3 * 86_400_000).toISOString() // vor 3 Tagen
const RECENT = new Date(NOW - 2 * 3_600_000).toISOString() // vor 2 h

it('ist inaktiv ohne Snapshot', () => {
  const s = computeSinceLastSeen(users, null, NOW)
  expect(s.active).toBe(false)
})

it('ist inaktiv, wenn letzter Besuch < 8 h her ist', () => {
  const s = computeSinceLastSeen(users, { seen_at: RECENT, entries: [] }, NOW)
  expect(s.active).toBe(false)
})

it('berechnet Deltas, Rang-Verbesserung und daysAgo', () => {
  const s = computeSinceLastSeen(
    users,
    { seen_at: OLD, entries: [
      { user_id: 1, scaled_km: 122, rank: 1 },
      { user_id: 2, scaled_km: 100, rank: 3 },
    ] },
    NOW,
  )
  expect(s.active).toBe(true)
  expect(s.daysAgo).toBe(3)
  expect(s.perUser[1].delta).toBe(8)
  expect(s.perUser[2].delta).toBe(28)
  expect(s.perUser[2].improved).toBe(true) // Rang 3 -> 2
  expect(s.perUser[1].improved).toBe(false)
})

it('neue Person (nicht im Snapshot) bekommt Delta 0 und rankPrev null', () => {
  const s = computeSinceLastSeen(
    users,
    { seen_at: OLD, entries: [{ user_id: 1, scaled_km: 122, rank: 1 }] },
    NOW,
  )
  expect(s.perUser[2].delta).toBe(0)
  expect(s.perUser[2].rankPrev).toBeNull()
})

it('describeSinceLastSeen fasst die Top-Bewegungen zusammen', () => {
  const s = computeSinceLastSeen(
    users,
    { seen_at: OLD, entries: [
      { user_id: 1, scaled_km: 122, rank: 1 },
      { user_id: 2, scaled_km: 100, rank: 3 },
    ] },
    NOW,
  )
  const text = describeSinceLastSeen(s, users)
  expect(text).toContain('vor 3 Tagen')
  expect(text).toContain('Ben +28 MM')
  expect(text).toContain('🚀')
})
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/components/comparison/sinceLastSeen.test.ts`
Expected: FAIL (`Cannot find module './sinceLastSeen'`).

- [ ] **Step 3: Helper implementieren**

`frontend/src/components/comparison/sinceLastSeen.ts`:
```ts
export type SeenEntry = { user_id: number; scaled_km: number; rank: number }
export type LastSeen = { seen_at: string; entries: SeenEntry[] }
export type UserLike = {
  user_id: number
  display_name: string
  total_scaled_km: number
  rank: number
}

export const SEEN_THRESHOLD_MS = 8 * 60 * 60 * 1000

export type PerUser = {
  prevScaled: number
  delta: number
  rankNow: number
  rankPrev: number | null
  improved: boolean
}

export type SinceLastSeen = {
  active: boolean
  daysAgo: number
  perUser: Record<number, PerUser>
}

/** Reiner Diff aktueller Stand vs. letzter Snapshot. `nowMs` wird injiziert (testbar). */
export function computeSinceLastSeen(
  users: UserLike[],
  last: LastSeen | null,
  nowMs: number,
): SinceLastSeen {
  const active = last != null && nowMs - Date.parse(last.seen_at) > SEEN_THRESHOLD_MS
  const prevMap = new Map<number, SeenEntry>()
  if (last) for (const e of last.entries) prevMap.set(e.user_id, e)

  const perUser: Record<number, PerUser> = {}
  for (const u of users) {
    const prev = prevMap.get(u.user_id)
    const prevScaled = prev ? prev.scaled_km : u.total_scaled_km
    const rankPrev = prev ? prev.rank : null
    perUser[u.user_id] = {
      prevScaled,
      delta: Math.max(0, u.total_scaled_km - prevScaled),
      rankNow: u.rank,
      rankPrev,
      improved: rankPrev != null && u.rank < rankPrev,
    }
  }
  const daysAgo = last
    ? Math.max(0, Math.round((nowMs - Date.parse(last.seen_at)) / 86_400_000))
    : 0
  return { active, daysAgo, perUser }
}

/** Kurztext fürs Banner: Zeitangabe + bis zu drei größte Zuwächse. */
export function describeSinceLastSeen(since: SinceLastSeen, users: UserLike[]): string {
  if (!since.active) return ''
  const zeit =
    since.daysAgo <= 0 ? 'seit heute' : since.daysAgo === 1 ? 'seit gestern' : `vor ${since.daysAgo} Tagen`
  const top = users
    .map((u) => ({
      name: u.display_name,
      delta: since.perUser[u.user_id]?.delta ?? 0,
      improved: since.perUser[u.user_id]?.improved ?? false,
    }))
    .filter((x) => x.delta > 0)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 3)
  if (top.length === 0) return `Seit deinem letzten Besuch (${zeit}) hat sich nichts getan.`
  const teile = top.map((x) => `${x.name} +${Math.round(x.delta)} MM${x.improved ? ' 🚀' : ''}`)
  return `Seit deinem letzten Besuch (${zeit}): ${teile.join(' · ')}`
}
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `cd frontend && npx vitest run src/components/comparison/sinceLastSeen.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/sinceLastSeen.ts frontend/src/components/comparison/sinceLastSeen.test.ts
git commit -m "feat(vergleich): Diff-Helper sinceLastSeen (F2)"
```

---

## Task 9: Frontend — API-Client für last-seen/seen (F2)

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Typen + Endpunkte ergänzen**

In `frontend/src/api/client.ts` bei den Typ-Definitionen (z. B. direkt nach `Comparison`) ergänzen:
```ts
export type SeenEntry = { user_id: number; scaled_km: number; rank: number }
export type LastSeen = { seen_at: string; entries: SeenEntry[] }
```

Im `api`-Objekt nach `comparison: …` ergänzen:
```ts
  lastSeenComparison: (year: number) =>
    request<LastSeen | null>(`/api/comparison/${year}/last-seen`),
  markComparisonSeen: (year: number) =>
    request<LastSeen>(`/api/comparison/${year}/seen`, { method: 'POST' }),
```

- [ ] **Step 2: Build/Typecheck**

Run: `cd frontend && npm run build`
Expected: ok.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(vergleich): API-Client last-seen/seen (F2)"
```

---

## Task 10: Frontend — Seit-Besuch-Animation im Rennen (F2)

**Files:**
- Modify: `frontend/src/components/comparison/RaceBahnen.tsx`
- Test: `frontend/src/components/comparison/RaceBahnen.test.tsx`

- [ ] **Step 1: Failing test schreiben**

Im `vi.mock('../../api/client', …)` von `RaceBahnen.test.tsx` die zwei neuen Funktionen ergänzen (Snapshot älter als 8 h → Banner/Delta aktiv). Mock-Objekt ersetzen:
```ts
vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
    ]),
    userActivities: vi.fn().mockResolvedValue([
      { id: 7, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, elevation_m: 120, note: 'Morgenlauf', scaled_km: 20, edited: false, source: 'strava', strava_url: 'https://www.strava.com/activities/42' },
    ]),
    lastSeenComparison: vi.fn().mockResolvedValue({
      seen_at: '2020-01-01T00:00:00Z',
      entries: [{ user_id: 1, scaled_km: 100, rank: 1 }],
    }),
    markComparisonSeen: vi.fn().mockResolvedValue({ seen_at: '2020-01-01T00:00:00Z', entries: [] }),
  },
}))
```

Neuen Test im `describe` ergänzen (Erik jetzt 300, Snapshot 100 → +200):
```ts
  it('zeigt das Seit-Besuch-Banner und das Delta, wenn der letzte Besuch alt genug ist', async () => {
    renderRace()
    expect(await screen.findByText(/Seit deinem letzten Besuch/)).toBeInTheDocument()
    // Exakter String: matcht nur das Balken-Label "+200" — das Banner enthält
    // "+200" ebenfalls, aber als Teil eines längeren Textes (kein exakter Match).
    expect(screen.getByText('+200')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/components/comparison/RaceBahnen.test.tsx`
Expected: FAIL (kein Banner/Delta gerendert).

- [ ] **Step 3: Query + Diff + Effekte in RaceBahnen**

In `frontend/src/components/comparison/RaceBahnen.tsx`:

Imports ergänzen:
```ts
import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { computeSinceLastSeen, describeSinceLastSeen } from './sinceLastSeen'
```
(Der bestehende `import { useState } from 'react'` wird durch die erweiterte Zeile ersetzt.)

Innerhalb der Komponente, nach `const [detail, …]`:
```ts
  const { data: lastSeen } = useQuery({
    queryKey: ['comparison-last-seen', data.year],
    queryFn: () => api.lastSeenComparison(data.year),
  })
  const since = computeSinceLastSeen(data.users, lastSeen ?? null, Date.now())
  const [grown, setGrown] = useState(false)
  const marked = useRef(false)
  useEffect(() => {
    if (!since.active) return
    const t = setTimeout(() => setGrown(true), 60)
    return () => clearTimeout(t)
  }, [since.active])
  useEffect(() => {
    if (!since.active || marked.current) return
    marked.current = true
    const t = setTimeout(() => {
      api.markComparisonSeen(data.year).catch(() => {})
    }, 1600)
    return () => clearTimeout(t)
  }, [since.active, data.year])
```

- [ ] **Step 4: Banner rendern**

Direkt nach dem öffnenden `<Card className="overflow-x-auto">` und vor `<div className="min-w-[640px] space-y-3">` einfügen:
```tsx
      {since.active && (
        <div className="mb-3 rounded-xl border border-accent/40 bg-accent/10 px-3 py-2 text-sm text-ink">
          ⏱ {describeSinceLastSeen(since, data.users)}
        </div>
      )}
```

- [ ] **Step 5: Geist-Balken, animierte Breite und Delta rendern**

Den Balken-Block (die `<div className="relative h-5 flex-1 …">` samt Inhalt, aktuell Zeilen ~81-97) ersetzen durch:
```tsx
              <div className="relative h-5 flex-1 overflow-hidden rounded-full border border-line bg-surface">
                {data.milestones.map((m) => (
                  <span
                    key={m.km}
                    className="absolute top-0 bottom-0 w-px bg-line"
                    style={{ left: pct(m.km) }}
                  />
                ))}
                {since.active && since.perUser[u.user_id]?.delta > 0 && (
                  <>
                    <div
                      className="absolute inset-y-0 left-0 rounded-full bg-ink-mute/25"
                      style={{ width: pct(since.perUser[u.user_id].prevScaled) }}
                    />
                    <span
                      className="absolute top-[-3px] bottom-[-3px] w-px bg-white/60"
                      style={{ left: pct(since.perUser[u.user_id].prevScaled) }}
                    />
                  </>
                )}
                <div
                  className={since.active ? 'absolute inset-y-0 left-0 rounded-full' : 'balken-wachsen absolute inset-y-0 left-0 rounded-full'}
                  style={{
                    width: since.active
                      ? grown
                        ? pct(u.total_scaled_km)
                        : pct(since.perUser[u.user_id]?.prevScaled ?? u.total_scaled_km)
                      : pct(u.total_scaled_km),
                    transition: since.active ? 'width 1.3s cubic-bezier(.2,.8,.2,1)' : undefined,
                    background: `linear-gradient(90deg, transparent, ${farbe})`,
                    boxShadow: fuehrt ? `0 0 14px ${farbe}` : `0 0 6px ${farbe}55`,
                  }}
                />
                {since.active && since.perUser[u.user_id]?.delta > 0 && (
                  <span
                    className="absolute top-1/2 -translate-x-full -translate-y-1/2 pr-1 text-[10px] font-black text-white [text-shadow:0_1px_2px_rgba(0,0,0,.6)]"
                    style={{ left: pct(u.total_scaled_km) }}
                  >
                    +{Math.round(since.perUser[u.user_id].delta)}
                  </span>
                )}
              </div>
```

- [ ] **Step 6: Tests laufen lassen — müssen bestehen**

Run: `cd frontend && npx vitest run src/components/comparison/RaceBahnen.test.tsx`
Expected: PASS (Detail-Test + neuer Banner/Delta-Test grün).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/comparison/RaceBahnen.tsx frontend/src/components/comparison/RaceBahnen.test.tsx
git commit -m "feat(vergleich): Seit-Besuch-Animation im Rennen mit Banner + Delta (F2)"
```

---

## Task 11: Gesamt-Verifikation

**Files:** keine (nur Prüfen)

- [ ] **Step 1: Alle Frontend-Tests**

Run: `cd frontend && npm test`
Expected: alle Suites grün.

- [ ] **Step 2: Frontend Build/Typecheck + Lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: Build ok, keine Lint-Fehler.

- [ ] **Step 3: Alle Backend-Tests**

Run: `cd backend && uv run pytest -q`
Expected: alle Tests grün.

- [ ] **Step 4: Abschluss-Commit (falls noch offene Änderungen)**

```bash
git add -A
git commit -m "chore(vergleich): Verifikation grün (Tests, Build, Lint)" || echo "nichts zu committen"
```

---

## Manuelle Prüfung (nach Umsetzung, im Browser)

Diese Punkte lassen sich nicht sinnvoll unit-testen — vor dem PR-Merge kurz manuell prüfen:

1. **F1:** MM/km-Toggle im Header schaltet die Zahlen in allen drei Views; Rangfolge im Rennen bleibt gleich; im Verlauf verschwinden im km-Modus die Ziel-/Meilenstein-Linien; Auswahl bleibt nach Reload erhalten.
2. **F3:** Piktogramme sitzen mittig in breiten Segmenten, schmale bleiben leer, Legende weiter sichtbar.
3. **F4:** Chip togglet Kurve, „i" öffnet Detail, „Alle/Keine" funktionieren.
4. **F2:** Nach > 8 h erneutem Aufruf: Banner + Geist-Balken + wachsende Balken + „+X"; danach (Reload innerhalb 8 h) statische Anzeige ohne Banner.
</content>
