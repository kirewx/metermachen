# Frontend-Redesign „Neon Night" — Plan 2: Visualisierungen + Vergleichsseite

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die drei Vergleichs-Visualisierungen (Race-Bahnen, Wanderkarte, Jahresverlauf) im Neon-Look mit stabiler Personenfarbe, die Vergleichsseite mit Pill-Tabs und kompakter einklappbarer Schnellwahl, plus Schnellwahl-Polish (Press-and-hold am Stepper, Glow-Puls beim Speichern, freie-km-Eingabe als String-State).

**Architektur:** Reines Frontend — keine Backend-Änderungen. Neuer Helper `userColor` (feste Neon-Palette, stabil über sortierte User-IDs) wird von allen drei Visualisierungen genutzt. Die Visualisierungen behalten ihre Datenlogik (`pathMath` unverändert) und werden auf die Theme-Tokens/UI-Bausteine aus Plan 1 umgestellt. Spec: `docs/superpowers/specs/2026-06-13-frontend-redesign-neon-design.md` §6–§7, §10.2.

**Tech Stack:** React 19 + TS + Tailwind v4 + TanStack Query + Recharts 3 (Vite, Vitest/RTL).

**Arbeitsbranch:** `feature/neon-redesign-2` (von `feature/neon-redesign-1` — Plan 1 ist noch nicht gemerged; PR wird gestackt mit Base `feature/neon-redesign-1` erstellt).

**Befehle** (im Worktree `.worktrees/neon-redesign-2`): Frontend-Tests `cd frontend && npm test`, einzelner Test `cd frontend && npx vitest run <pfad>`, Lint `cd frontend && npm run lint`, Build `cd frontend && npm run build`.

---

## Verbindliche Namen (überall identisch verwenden)

- Helper: `userColor(userId: number, alleIds: number[]): string` und Palette `USER_FARBEN` in `frontend/src/components/comparison/userColor.ts`
- CSS-Klassen (in `index.css` definiert): `glow-puls` (Karte pulst beim Speichern), `balken-wachsen` (Balken wächst beim Mount)
- SVG-IDs in WanderKarte: Filter `neon-glow`, Gradient `vignette`
- `localStorage`-Schlüssel: `schnellwahl-leiste-offen` (Werte `offen`/`zu`; Default offen), bestehend bleiben `theme`, `schnellwahl-kategorie`
- Vergleichs-Tabs: `karte` (Icon `karte`), `rennen` (Icon `fahne`), `verlauf` (Icon `chart`)
- Theme-Utilityklassen aus Plan 1: `bg-surface`, `bg-card`, `border-line`, `text-ink`, `text-ink-soft`, `text-ink-mute`, `text-accent`, `bg-accent`, `text-accent-ink`, `text-danger`, `shadow-glow`, `shadow-glow-strong`
- `SchnellwahlCard`-Prop `onSubmit` ändert den Typ zu `(input: ActivityInput) => void | Promise<unknown>` (Aufrufer geben `mutateAsync` weiter)

---

### Task 0: Worktree + Branch anlegen

- [ ] **Step 1: Worktree von Plan-1-Branch erstellen** (im Haupt-Repo `C:\Users\Erik\Documents\MeterMachen`)

```bash
git worktree add .worktrees/neon-redesign-2 -b feature/neon-redesign-2 feature/neon-redesign-1
```

- [ ] **Step 2: Abhängigkeiten installieren**

```bash
cd .worktrees/neon-redesign-2/frontend && npm install
```

- [ ] **Step 3: Tests laufen grün (Ausgangslage prüfen)**

Run: `cd .worktrees/neon-redesign-2/frontend && npm test`
Expected: alle Tests grün (Stand von Plan 1)

---

### Task 1: `userColor`-Helper

**Files:**
- Create: `frontend/src/components/comparison/userColor.ts`
- Test: `frontend/src/components/comparison/userColor.test.ts`

- [ ] **Step 1: Failing Test schreiben** — `frontend/src/components/comparison/userColor.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { USER_FARBEN, userColor } from './userColor'

describe('userColor', () => {
  it('vergibt Farben nach sortierter User-ID-Reihenfolge', () => {
    expect(userColor(3, [7, 3, 12])).toBe(USER_FARBEN[0])
    expect(userColor(7, [7, 3, 12])).toBe(USER_FARBEN[1])
    expect(userColor(12, [7, 3, 12])).toBe(USER_FARBEN[2])
  })

  it('ist unabhängig von der Reihenfolge des ID-Arrays', () => {
    expect(userColor(7, [12, 7, 3])).toBe(userColor(7, [3, 7, 12]))
  })

  it('wiederholt die Palette bei mehr Personen als Farben', () => {
    const ids = Array.from({ length: USER_FARBEN.length + 1 }, (_, i) => i + 1)
    expect(userColor(ids[ids.length - 1], ids)).toBe(USER_FARBEN[0])
  })

  it('liefert eine Fallback-Farbe für unbekannte IDs', () => {
    expect(userColor(99, [1, 2])).toBe(USER_FARBEN[0])
  })
})
```

- [ ] **Step 2: Test läuft rot**

Run: `cd frontend && npx vitest run src/components/comparison/userColor.test.ts`
Expected: FAIL — `Cannot find module './userColor'`

- [ ] **Step 3: Helper implementieren** — `frontend/src/components/comparison/userColor.ts`:

```ts
/**
 * Feste Neon-Palette pro Person — identische Farbe in allen drei
 * Vergleichs-Ansichten. Zuordnung stabil über die sortierte User-ID-Reihenfolge.
 */
export const USER_FARBEN = [
  '#22d3ee', '#818cf8', '#2dd4bf', '#a78bfa', '#38bdf8', '#e879f9', '#34d399', '#f472b6',
] as const

export function userColor(userId: number, alleIds: number[]): string {
  const sortiert = [...alleIds].sort((a, b) => a - b)
  const i = Math.max(0, sortiert.indexOf(userId))
  return USER_FARBEN[i % USER_FARBEN.length]
}
```

- [ ] **Step 4: Test läuft grün**

Run: `cd frontend && npx vitest run src/components/comparison/userColor.test.ts`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/userColor.ts frontend/src/components/comparison/userColor.test.ts
git commit -m "feat: userColor-helper mit fester neon-palette pro person"
```

---

### Task 2: Stepper Press-and-hold

**Files:**
- Modify: `frontend/src/components/ui/Stepper.tsx` (komplett ersetzen)
- Test: `frontend/src/components/ui/Stepper.test.tsx` (Tests ergänzen)

- [ ] **Step 1: Failing Tests ergänzen** — in `frontend/src/components/ui/Stepper.test.tsx` Imports anpassen und zwei Tests anhängen. `fireEvent` aus `@testing-library/react` zusätzlich importieren, `afterEach` aus `vitest`:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Stepper from './Stepper'
```

Neue Tests innerhalb des bestehenden `describe`-Blocks:

```tsx
  afterEach(() => vi.useRealTimers())

  it('gedrückt halten wiederholt nach kurzer Verzögerung', () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    const plus = screen.getByRole('button', { name: '1 km mehr' })
    fireEvent.pointerDown(plus)
    expect(onChange).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(400 + 3 * 120)
    expect(onChange).toHaveBeenCalledTimes(4)
    fireEvent.pointerUp(plus)
    vi.advanceTimersByTime(500)
    expect(onChange).toHaveBeenCalledTimes(4)
  })

  it('reagiert auf Tastatur-Klicks (click mit detail 0)', () => {
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    expect(onChange).toHaveBeenCalledWith(11)
  })
```

- [ ] **Step 2: Tests laufen rot**

Run: `cd frontend && npx vitest run src/components/ui/Stepper.test.tsx`
Expected: die zwei neuen Tests FAIL (Hold wiederholt nicht bzw. doppelte Aufrufe), die zwei alten PASS

- [ ] **Step 3: Stepper ersetzen** — `frontend/src/components/ui/Stepper.tsx` komplett ersetzen durch:

```tsx
import { useEffect, useRef } from 'react'
import Icon from './Icon'

type Props = {
  value: number
  onChange: (v: number) => void
  min?: number
  step?: number
  size?: 'hero' | 'kompakt'
}

export default function Stepper({ value, onChange, min = 1, step = 1, size = 'hero' }: Props) {
  const hero = size === 'hero'
  const btn = hero ? 'h-13 w-13' : 'h-8 w-8'
  const valueRef = useRef(value)
  const stopRef = useRef<(() => void) | null>(null)
  useEffect(() => {
    valueRef.current = value
  })
  useEffect(() => () => stopRef.current?.(), [])

  // Press-and-hold: sofort ein Schritt, nach 400 ms Wiederholung alle 120 ms.
  function startHold(richtung: 1 | -1) {
    const tick = () => onChange(Math.max(min, valueRef.current + richtung * step))
    tick()
    let interval = 0
    const delay = window.setTimeout(() => {
      interval = window.setInterval(tick, 120)
    }, 400)
    stopRef.current = () => {
      window.clearTimeout(delay)
      window.clearInterval(interval)
      stopRef.current = null
    }
  }
  const stopHold = () => stopRef.current?.()

  // Maus/Touch laufen über Pointer-Events; Tastatur-Klicks (Enter/Leertaste)
  // erzeugen click-Events mit detail 0 und bekommen einen Einzelschritt.
  const haltbar = (richtung: 1 | -1) => ({
    onPointerDown: () => startHold(richtung),
    onPointerUp: stopHold,
    onPointerLeave: stopHold,
    onPointerCancel: stopHold,
    onClick: (e: React.MouseEvent) => {
      if (e.detail === 0) onChange(Math.max(min, valueRef.current + richtung * step))
    },
  })

  return (
    <div className={`flex items-center justify-center ${hero ? 'gap-5' : 'gap-2'}`}>
      <button
        type="button"
        aria-label="1 km weniger"
        {...haltbar(-1)}
        className={`flex items-center justify-center rounded-full border-2 border-accent/60 text-accent ${btn}`}
      >
        <Icon name="minus" size={hero ? 24 : 14} />
      </button>
      {hero ? (
        <div className="min-w-24 text-center">
          <div
            data-testid="km-wert"
            className="text-5xl font-black tabular-nums text-ink [text-shadow:var(--t-glow-strong)]"
          >
            {value % 1 === 0 ? value : value.toFixed(1)}
          </div>
          <div className="text-xs font-bold tracking-[0.3em] text-accent">KM</div>
        </div>
      ) : (
        <div
          data-testid="km-wert"
          className="min-w-16 text-center text-lg font-black tabular-nums text-ink"
        >
          {value % 1 === 0 ? value : value.toFixed(1)} km
        </div>
      )}
      <button
        type="button"
        aria-label="1 km mehr"
        {...haltbar(1)}
        className={`flex items-center justify-center rounded-full bg-accent text-accent-ink shadow-glow-strong ${btn}`}
      >
        <Icon name="plus" size={hero ? 24 : 14} />
      </button>
    </div>
  )
}
```

Hinweis: Die zwei Bestandstests klicken mit `userEvent.click` — das feuert die volle Pointer-Sequenz (`pointerdown` → Schritt, `click` mit `detail: 1` → ignoriert), sie bleiben also grün.

- [ ] **Step 4: Tests laufen grün**

Run: `cd frontend && npx vitest run src/components/ui/Stepper.test.tsx`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Stepper.tsx frontend/src/components/ui/Stepper.test.tsx
git commit -m "feat: press-and-hold am stepper"
```

---

### Task 3: SchnellwahlCard — freie km als String-State + Glow-Puls

**Files:**
- Modify: `frontend/src/components/activities/SchnellwahlCard.tsx` (komplett ersetzen)
- Modify: `frontend/src/index.css` (Keyframes anhängen)
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx:54` (`onSubmit` auf `mutateAsync`)
- Test: `frontend/src/components/activities/SchnellwahlCard.test.tsx` (Tests ergänzen)

- [ ] **Step 1: Failing Tests ergänzen** — in `frontend/src/components/activities/SchnellwahlCard.test.tsx` den Import erweitern:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
```

und am Ende des `describe`-Blocks drei Tests anhängen:

```tsx
  it('freie km: Zwischenzustände und Komma funktionieren', async () => {
    const onSubmit = vi.fn()
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: 'Details' }))
    const frei = screen.getByLabelText('km (frei)')
    await userEvent.clear(frei)
    await userEvent.type(frei, '7,')
    expect(frei).toHaveValue('7,')
    await userEvent.type(frei, '5')
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ distance_km: 7.5 }))
  })

  it('nach Erfolg: Wert springt auf Standard zurück und Karte pulsiert', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const { container } = render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    await waitFor(() => expect(container.querySelector('.glow-puls')).not.toBeNull())
    expect(screen.getByTestId('km-wert')).toHaveTextContent('5')
  })

  it('bei Fehler bleiben die Eingaben erhalten', async () => {
    const onSubmit = vi.fn().mockRejectedValue(new Error('kaputt'))
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalled())
    expect(screen.getByTestId('km-wert')).toHaveTextContent('6')
  })
```

- [ ] **Step 2: Tests laufen rot**

Run: `cd frontend && npx vitest run src/components/activities/SchnellwahlCard.test.tsx`
Expected: die drei neuen Tests FAIL (u. a. `'7,'`-Zwischenzustand geht im number-Input verloren, `.glow-puls` existiert nicht, Reset passiert auch bei Fehler)

- [ ] **Step 3: SchnellwahlCard ersetzen** — `frontend/src/components/activities/SchnellwahlCard.tsx` komplett ersetzen durch:

```tsx
import { useState } from 'react'
import type { Activity, ActivityInput, Category } from '../../api/client'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Icon from '../ui/Icon'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Stepper from '../ui/Stepper'

const heute = () => new Date().toISOString().slice(0, 10)

type Props = {
  categories: Category[]
  variant?: 'hero' | 'kompakt'
  initial?: Activity
  onSubmit: (input: ActivityInput) => void | Promise<unknown>
  onCancel?: () => void
}

export default function SchnellwahlCard({
  categories,
  variant = 'hero',
  initial,
  onSubmit,
  onCancel,
}: Props) {
  const aktive = categories.filter((c) => c.is_active || c.id === initial?.category_id)
  const gemerkt = Number(localStorage.getItem('schnellwahl-kategorie'))
  const [categoryId, setCategoryId] = useState(
    initial?.category_id ??
      (aktive.some((c) => c.id === gemerkt) ? gemerkt : (aktive[0]?.id ?? 0)),
  )
  const kategorie = aktive.find((c) => c.id === categoryId)
  // String-State, damit Zwischenzustände wie "7," beim Tippen erhalten bleiben.
  const [kmText, setKmText] = useState(String(initial?.distance_km ?? kategorie?.default_km ?? 10))
  const [details, setDetails] = useState(Boolean(initial))
  const [date, setDate] = useState(initial?.date ?? heute())
  const [duration, setDuration] = useState(initial?.duration_min ? String(initial.duration_min) : '')
  const [note, setNote] = useState(initial?.note ?? '')
  const [pulsiert, setPulsiert] = useState(false)

  const km = parseFloat(kmText.replace(',', '.'))

  function wechselKategorie(id: number) {
    setCategoryId(id)
    localStorage.setItem('schnellwahl-kategorie', String(id))
    if (!initial) setKmText(String(aktive.find((c) => c.id === id)?.default_km ?? 10))
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!categoryId || !Number.isFinite(km) || km <= 0 || !date) return
    Promise.resolve(
      onSubmit({
        category_id: categoryId,
        date,
        distance_km: km,
        duration_min: duration ? parseInt(duration, 10) : null,
        note: note || null,
      }),
    )
      .then(() => {
        setPulsiert(true)
        window.setTimeout(() => setPulsiert(false), 700)
        if (!initial) {
          setKmText(String(kategorie?.default_km ?? 10))
          setDetails(false)
          setDate(heute())
          setDuration('')
          setNote('')
        }
      })
      .catch(() => {
        /* Fehler-Toast zeigt der Aufrufer; Eingaben bleiben erhalten */
      })
  }

  const gewertet = kategorie && Number.isFinite(km) ? (km * kategorie.factor).toFixed(1) : '0.0'
  const datumText = date === heute() ? 'heute' : date

  return (
    <form onSubmit={submit}>
      <Card
        glow
        className={`${variant === 'hero' ? 'mx-auto max-w-md p-6 text-center' : 'p-3'} ${pulsiert ? 'glow-puls' : ''}`}
      >
        <div className={variant === 'hero' ? 'space-y-4' : 'flex flex-wrap items-end gap-3'}>
          <Select
            label="Kategorie"
            value={categoryId}
            onChange={(e) => wechselKategorie(Number(e.target.value))}
            className={variant === 'hero' ? 'mx-auto w-56 text-left' : 'w-44'}
          >
            {aktive.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {c.factor}x
              </option>
            ))}
          </Select>
          <Stepper
            value={Number.isFinite(km) ? km : 0}
            onChange={(v) => setKmText(String(v))}
            size={variant === 'hero' ? 'hero' : 'kompakt'}
          />
          {variant === 'hero' && (
            <p className="text-xs text-ink-mute">
              = {gewertet} km gewertet · {datumText}
            </p>
          )}
          <Button type="submit" className={variant === 'hero' ? 'w-full' : ''}>
            <span className="inline-flex items-center gap-1">
              Eintragen <Icon name="blitz" size={14} />
            </span>
          </Button>
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              Abbrechen
            </Button>
          )}
        </div>
        <button
          type="button"
          onClick={() => setDetails(!details)}
          className="mt-3 inline-flex items-center gap-1 text-xs text-ink-mute hover:text-accent"
        >
          <Icon name="chevron" size={12} className={details ? 'rotate-180' : ''} />
          Details
        </button>
        {details && (
          <div className="mt-3 grid gap-3 text-left sm:grid-cols-2">
            <Input label="Datum" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            <Input
              label="km (frei)"
              type="text"
              inputMode="decimal"
              value={kmText}
              onChange={(e) => setKmText(e.target.value)}
            />
            <Input
              label="Dauer (min)"
              type="number"
              min="1"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
            <Input label="Notiz" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        )}
      </Card>
    </form>
  )
}
```

- [ ] **Step 4: Keyframes anhängen** — ans Ende von `frontend/src/index.css`:

```css
@keyframes glow-puls {
  0% {
    box-shadow: var(--t-glow);
  }
  35% {
    box-shadow: 0 0 26px var(--t-accent);
  }
  100% {
    box-shadow: var(--t-glow);
  }
}
.glow-puls {
  animation: glow-puls 0.7s ease-out;
}

@keyframes balken-wachsen {
  from {
    width: 0;
  }
}
.balken-wachsen {
  animation: balken-wachsen 0.8s ease-out;
}
```

(`balken-wachsen` wird in Task 4 von den Race-Bahnen genutzt.)

- [ ] **Step 5: Aufrufer auf `mutateAsync` umstellen** — in `frontend/src/pages/MeineAktivitaeten.tsx` die Zeile

```tsx
        onSubmit={save.mutate}
```

ersetzen durch

```tsx
        onSubmit={(input) => save.mutateAsync(input)}
```

(`mutateAsync` liefert ein Promise — die Karte pulst erst nach Server-Erfolg und behält bei Fehlern die Eingaben; den Fehler-Toast übernimmt weiterhin `onError` der Mutation.)

- [ ] **Step 6: Tests laufen grün**

Run: `cd frontend && npx vitest run src/components/activities/SchnellwahlCard.test.tsx`
Expected: 11 passed (8 alte + 3 neue)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/activities/SchnellwahlCard.tsx frontend/src/components/activities/SchnellwahlCard.test.tsx frontend/src/index.css frontend/src/pages/MeineAktivitaeten.tsx
git commit -m "feat: schnellwahl mit glow-puls, fehlertolerantem reset und freier km-eingabe als string"
```

---

### Task 4: RaceBahnen im Neon-Look

**Files:**
- Modify: `frontend/src/components/comparison/RaceBahnen.tsx` (komplett ersetzen)

Keine eigenen Unit-Tests (rein visuelle Komponente, Datenlogik steckt im Backend bzw. `userColor`). Verifikation über Build + bestehende Tests.

- [ ] **Step 1: RaceBahnen ersetzen** — `frontend/src/components/comparison/RaceBahnen.tsx` komplett ersetzen durch:

```tsx
import type { Comparison } from '../../api/client'
import Avatar from '../ui/Avatar'
import Card from '../ui/Card'
import Icon from '../ui/Icon'
import { userColor } from './userColor'

export default function RaceBahnen({ data }: { data: Comparison }) {
  const maxKm = Math.max(data.goal_km, ...data.users.map((u) => u.total_scaled_km))
  const pct = (km: number) => `${(km / maxKm) * 100}%`
  const ids = data.users.map((u) => u.user_id)
  const fuehrend = data.users.find((u) => u.rank === 1)

  return (
    <Card className="overflow-x-auto">
      <div className="min-w-[640px] space-y-3">
        {/* Kopfzeile: Meilenstein- und Ziel-Marker über der Bahnspur */}
        <div className="flex items-end gap-3">
          <div className="w-44 shrink-0" />
          <div className="relative h-9 flex-1">
            {data.milestones.map((m) => (
              <span
                key={m.km}
                className="absolute flex -translate-x-1/2 flex-col items-center text-ink-mute"
                style={{ left: pct(m.km) }}
              >
                <Icon name={m.icon} size={13} />
                <span className="text-[9px] tabular-nums">{m.km}</span>
              </span>
            ))}
            <span
              className="absolute flex -translate-x-1/2 flex-col items-center text-accent"
              style={{ left: pct(data.goal_km) }}
            >
              <Icon name="fahne" size={13} />
              <span className="text-[9px] font-bold tabular-nums">{data.goal_km}</span>
            </span>
          </div>
          <div className="w-24 shrink-0" />
        </div>
        {data.users.map((u) => {
          const farbe = userColor(u.user_id, ids)
          const fuehrt = u.rank === 1
          const abstand =
            fuehrend && !fuehrt ? Math.round(fuehrend.total_scaled_km - u.total_scaled_km) : 0
          return (
            <div key={u.user_id} className="flex items-center gap-3">
              <div className="flex w-44 shrink-0 items-center gap-2">
                <span
                  className={`w-7 text-sm font-black tabular-nums ${
                    fuehrt ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
                  }`}
                >
                  P{u.rank}
                </span>
                <Avatar value={u.avatar} size="sm" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-ink">{u.display_name}</p>
                  {!fuehrt && (
                    <p className="text-[10px] text-ink-mute">−{abstand} km auf P1</p>
                  )}
                </div>
              </div>
              <div className="relative h-5 flex-1 overflow-hidden rounded-full border border-line bg-surface">
                {data.milestones.map((m) => (
                  <span
                    key={m.km}
                    className="absolute top-0 bottom-0 w-px bg-line"
                    style={{ left: pct(m.km) }}
                  />
                ))}
                <div
                  className="balken-wachsen absolute inset-y-0 left-0 rounded-full"
                  style={{
                    width: pct(u.total_scaled_km),
                    background: `linear-gradient(90deg, transparent, ${farbe})`,
                    boxShadow: fuehrt ? `0 0 14px ${farbe}` : `0 0 6px ${farbe}55`,
                  }}
                />
              </div>
              <p className="w-24 shrink-0 text-right text-lg font-black tabular-nums text-ink">
                {Math.round(u.total_scaled_km)}{' '}
                <span className="text-xs font-normal text-ink-mute">km</span>
              </p>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
```

Wichtig: Kopfzeile und Bahn-Zeilen nutzen dieselbe Spaltenstruktur (`w-44` + `flex-1` + `w-24`, `gap-3`), damit die Marker exakt über den Bahnen sitzen.

- [ ] **Step 2: Verifizieren**

Run: `cd frontend && npm test && npm run build`
Expected: alle Tests grün, Build ohne TS-Fehler

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/comparison/RaceBahnen.tsx
git commit -m "feat: race-bahnen mit personenfarbe, glow-balken und abstand zu p1"
```

---

### Task 5: WanderKarte im Neon-Look

**Files:**
- Modify: `frontend/src/components/comparison/WanderKarte.tsx` (komplett ersetzen)

`pathMath.ts` und `pathMath.test.ts` bleiben unverändert. Die `Landschaft`-Fallback-Grafik bleibt erhalten.

- [ ] **Step 1: WanderKarte ersetzen** — `frontend/src/components/comparison/WanderKarte.tsx` komplett ersetzen durch:

```tsx
import { useLayoutEffect, useRef, useState } from 'react'
import type { Comparison } from '../../api/client'
import Card from '../ui/Card'
import { progressFraction, spreadBadges } from './pathMath'
import { userColor } from './userColor'

const TRAIL = 'M 40,460 C 120,330 220,300 320,320 S 520,400 640,360 S 820,180 920,150'

type Point = { x: number; y: number }

export default function WanderKarte({ data }: { data: Comparison }) {
  const pathRef = useRef<SVGPathElement>(null)
  const [points, setPoints] = useState<Map<number, Point>>(new Map())
  const [milestonePoints, setMilestonePoints] = useState<Point[]>([])
  const [selected, setSelected] = useState<number | null>(null)

  useLayoutEffect(() => {
    const path = pathRef.current
    if (!path) return
    const len = path.getTotalLength()
    const at = (fraction: number) => {
      const p = path.getPointAtLength(fraction * len)
      return { x: p.x, y: p.y }
    }
    setPoints(
      new Map(
        data.users.map((u) => [
          u.user_id,
          at(progressFraction(u.total_scaled_km, data.goal_km)),
        ]),
      ),
    )
    setMilestonePoints(data.milestones.map((m) => at(progressFraction(m.km, data.goal_km))))
  }, [data])

  const badgeLanes = spreadBadges(
    data.users.map((u) => ({ id: u.user_id, x: points.get(u.user_id)?.x ?? 0 })),
    120,
  )

  const selectedUser = data.users.find((u) => u.user_id === selected)
  const ids = data.users.map((u) => u.user_id)
  const besteKm = Math.max(0, ...data.users.map((u) => u.total_scaled_km))

  return (
    <div className="space-y-3">
      <Card className="p-2">
        <svg viewBox="0 0 960 520" className="w-full rounded-xl">
          <defs>
            <radialGradient id="vignette" cx="50%" cy="50%" r="72%">
              <stop offset="55%" stopColor="#050508" stopOpacity="0" />
              <stop offset="100%" stopColor="#050508" stopOpacity="0.55" />
            </radialGradient>
            <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {data.map_image ? (
            <image
              href={data.map_image}
              width="960"
              height="520"
              preserveAspectRatio="xMidYMid slice"
            />
          ) : (
            <Landschaft />
          )}
          <rect width="960" height="520" fill="url(#vignette)" />
          <path
            d={TRAIL}
            fill="none"
            stroke="#050508"
            strokeOpacity="0.45"
            strokeWidth="14"
            strokeLinecap="round"
          />
          <path
            ref={pathRef}
            d={TRAIL}
            fill="none"
            stroke="var(--t-accent)"
            strokeWidth="3.5"
            strokeDasharray="10,9"
            strokeLinecap="round"
            filter="url(#neon-glow)"
          />
          {data.milestones.map((m, i) => {
            const p = milestonePoints[i]
            if (!p) return null
            const erreicht = besteKm >= m.km
            return (
              <g key={m.km} color={erreicht ? 'var(--t-accent)' : 'var(--t-ink-mute)'}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="14"
                  fill="var(--t-card)"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  filter={erreicht ? 'url(#neon-glow)' : undefined}
                />
                <use href={`/icons.svg#${m.icon}`} x={p.x - 8} y={p.y - 8} width="16" height="16" />
                <text x={p.x} y={p.y + 32} textAnchor="middle" fontSize="11" fill="var(--t-ink-soft)">
                  {m.label} · {m.km} km
                </text>
              </g>
            )
          })}
          <g color="var(--t-accent)">
            <circle
              cx="920"
              cy="150"
              r="16"
              fill="var(--t-card)"
              stroke="currentColor"
              strokeWidth="3"
              filter="url(#neon-glow)"
            />
            <use href="/icons.svg#fahne" x={911} y={141} width="18" height="18" />
            <text x="920" y="122" textAnchor="middle" fontSize="11" fill="var(--t-ink-soft)">
              {data.goal_km} km
            </text>
          </g>
          {[...data.users].reverse().map((u) => {
            const p = points.get(u.user_id)
            if (!p) return null
            const lane = badgeLanes.get(u.user_id) ?? 0
            const badgeY = p.y - 30 - lane * 24
            const farbe = userColor(u.user_id, ids)
            return (
              <g
                key={u.user_id}
                className="cursor-pointer"
                onClick={() => setSelected(u.user_id === selected ? null : u.user_id)}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="15"
                  fill="var(--t-card)"
                  stroke={farbe}
                  strokeWidth="2.5"
                  filter={u.rank === 1 ? 'url(#neon-glow)' : undefined}
                />
                {u.avatar.startsWith('icon:') ? (
                  <use
                    href={`/icons.svg#${u.avatar.slice(5)}`}
                    x={p.x - 8}
                    y={p.y - 8}
                    width="16"
                    height="16"
                    color={farbe}
                  />
                ) : (
                  <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="14">
                    {u.avatar}
                  </text>
                )}
                <rect
                  x={p.x - 56}
                  y={badgeY - 13}
                  width="112"
                  height="19"
                  rx="9.5"
                  fill="#050508"
                  fillOpacity="0.85"
                  stroke={farbe}
                  strokeOpacity="0.6"
                />
                <text
                  x={p.x}
                  y={badgeY}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="700"
                  fill="#f2fbfd"
                >
                  P{u.rank} {u.display_name} · {Math.round(u.total_scaled_km)}
                </text>
              </g>
            )
          })}
        </svg>
      </Card>
      {selectedUser && (
        <Card className="p-3">
          <p className="text-sm font-bold text-ink">
            {selectedUser.display_name} —{' '}
            <span className="text-accent">{Math.round(selectedUser.total_scaled_km)}</span> von{' '}
            {data.goal_km} km
          </p>
          <ul className="mt-1 flex flex-wrap gap-3 text-sm text-ink-soft">
            {selectedUser.by_category.map((b) => (
              <li key={b.category_id} className="flex items-center gap-1">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ background: b.color }}
                />
                {b.name}: {Math.round(b.scaled_km)} km
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

function Landschaft() {
  return (
    <g>
      <rect width="960" height="520" fill="#e7f0d8" />
      <ellipse cx="220" cy="120" rx="190" ry="80" fill="#7db86a" />
      <circle cx="160" cy="100" r="22" fill="#4e8c3f" />
      <circle cx="220" cy="125" r="26" fill="#5da04c" />
      <circle cx="280" cy="95" r="20" fill="#4e8c3f" />
      <polygon points="680,170 770,40 860,170" fill="#a8a29a" />
      <polygon points="745,75 770,40 795,75 770,88" fill="#f4f4f2" />
      <polygon points="770,170 840,80 910,170" fill="#bdb8b0" />
      <path d="M 0,400 Q 240,360 480,410 T 960,390 L 960,520 L 0,520 Z" fill="#79b9dd" />
      <path
        d="M 90,440 q 20,-9 40,0 M 300,465 q 20,-9 40,0 M 540,445 q 20,-9 40,0"
        stroke="#fff" strokeWidth="3" fill="none" opacity="0.7" strokeLinecap="round"
      />
    </g>
  )
}
```

Hinweise: Die Sprite-Icons zeichnen mit `stroke="currentColor"` — deshalb steuert das `color`-Attribut auf `<g>`/`<use>` die Icon-Farbe. „Erreicht" heißt: die führende Person hat den Meilenstein-km-Wert erreicht.

- [ ] **Step 2: Verifizieren**

Run: `cd frontend && npm test && npm run build`
Expected: alle Tests grün (inkl. unverändertem `pathMath.test.ts`), Build ohne TS-Fehler

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/comparison/WanderKarte.tsx
git commit -m "feat: wanderkarte mit vignette, glow-route und neon-badges"
```

---

### Task 6: Jahresverlauf im Neon-Look

**Files:**
- Modify: `frontend/src/components/comparison/JahresVerlauf.tsx` (komplett ersetzen)

- [ ] **Step 1: JahresVerlauf ersetzen** — `frontend/src/components/comparison/JahresVerlauf.tsx` komplett ersetzen durch:

```tsx
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Comparison } from '../../api/client'
import Card from '../ui/Card'
import { userColor } from './userColor'

type EndPunktProps = { key?: string; index?: number; cx?: number; cy?: number; x?: number; y?: number }

export default function JahresVerlauf({ data }: { data: Comparison }) {
  // Kurven zu einem gemeinsamen Datensatz mergen: eine Zeile pro Datum.
  const byDate = new Map<string, Record<string, number | string>>()
  for (const u of data.users) {
    for (const p of u.cumulative) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[u.display_name] = p.scaled_km
      byDate.set(p.date, row)
    }
  }
  const rows = [...byDate.values()].sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )
  const ids = data.users.map((u) => u.user_id)
  // Letzter Datenpunkt je Person — dort sitzen Endpunkt-Dot und Namens-Label.
  const lastIndex = new Map<string, number>()
  for (const u of data.users) {
    for (let i = rows.length - 1; i >= 0; i--) {
      if (rows[i][u.display_name] !== undefined) {
        lastIndex.set(u.display_name, i)
        break
      }
    }
  }

  return (
    <Card>
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={rows} margin={{ top: 8, right: 90, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--t-line)" strokeOpacity={0.25} vertical={false} />
          <XAxis
            dataKey="date"
            fontSize={11}
            stroke="var(--t-ink-mute)"
            tickLine={false}
            axisLine={{ stroke: 'var(--t-line)' }}
          />
          <YAxis fontSize={11} unit=" km" stroke="var(--t-ink-mute)" tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{
              background: 'var(--t-card)',
              border: '1px solid var(--t-line)',
              borderRadius: 12,
              color: 'var(--t-ink)',
            }}
            labelStyle={{ color: 'var(--t-ink-mute)' }}
          />
          {data.milestones.map((m) => (
            <ReferenceLine
              key={m.km}
              y={m.km}
              stroke="var(--t-ink-mute)"
              strokeOpacity={0.5}
              strokeDasharray="5 4"
              label={{ value: m.label, fontSize: 11, position: 'right', fill: 'var(--t-ink-mute)' }}
            />
          ))}
          <ReferenceLine
            y={data.goal_km}
            stroke="var(--t-accent)"
            label={{ value: 'Ziel', fontSize: 11, fill: 'var(--t-accent)' }}
          />
          {data.users.map((u) => {
            const farbe = userColor(u.user_id, ids)
            const letzte = lastIndex.get(u.display_name)
            return (
              <Line
                key={u.user_id}
                dataKey={u.display_name}
                stroke={farbe}
                strokeWidth={2.5}
                connectNulls
                style={{ filter: `drop-shadow(0 0 4px ${farbe})` }}
                dot={(p: EndPunktProps) =>
                  p.index === letzte ? (
                    <circle key={p.key} cx={p.cx} cy={p.cy} r={4} fill={farbe} />
                  ) : (
                    <g key={p.key} />
                  )
                }
                label={(p: EndPunktProps) =>
                  p.index === letzte ? (
                    <text
                      key={p.key}
                      x={(p.x ?? 0) + 8}
                      y={(p.y ?? 0) + 4}
                      fontSize={11}
                      fontWeight={700}
                      fill={farbe}
                    >
                      {u.display_name}
                    </text>
                  ) : (
                    <g key={p.key} />
                  )
                }
              />
            )
          })}
        </LineChart>
      </ResponsiveContainer>
    </Card>
  )
}
```

Änderungen gegenüber vorher: `Legend` entfällt (Namens-Label am Linienende), feste `COLORS`-Liste → `userColor`, Grid/Achsen/Tooltip auf Theme-Variablen, `🏁 Ziel` → `Ziel`, Neon-Glow per CSS-`drop-shadow` auf der Linie, rechter Rand 90 px für die Labels.

- [ ] **Step 2: Verifizieren**

Run: `cd frontend && npm test && npm run build`
Expected: alle Tests grün, Build ohne TS-Fehler. Falls TypeScript die `dot`/`label`-Funktions-Signatur ablehnt: Recharts 3 typisiert beide Render-Props mit `(props: any)` — dann die eigene `EndPunktProps`-Annotation beibehalten und den Rückgabewert nicht ändern; keinesfalls `any` einführen.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/comparison/JahresVerlauf.tsx
git commit -m "feat: jahresverlauf mit neon-linien, endpunkt-labels und dunklem tooltip"
```

---

### Task 7: SchnellwahlLeiste (kompakt + einklappbar)

**Files:**
- Create: `frontend/src/components/activities/SchnellwahlLeiste.tsx`
- Test: `frontend/src/components/activities/SchnellwahlLeiste.test.tsx`

- [ ] **Step 1: Failing Test schreiben** — `frontend/src/components/activities/SchnellwahlLeiste.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SchnellwahlLeiste from './SchnellwahlLeiste'

vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      {
        id: 1, name: 'Joggen', factor: 4, color: '#fff',
        icon: 'laufen', default_km: 5, is_active: true,
      },
    ]),
    createActivity: vi.fn(),
  },
}))

function renderLeiste() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SchnellwahlLeiste />
    </QueryClientProvider>,
  )
}

describe('SchnellwahlLeiste', () => {
  beforeEach(() => localStorage.clear())

  it('ist standardmäßig offen und zeigt die kompakte Schnellwahl', async () => {
    renderLeiste()
    expect(await screen.findByTestId('km-wert')).toBeInTheDocument()
  })

  it('einklappen versteckt die Karte und merkt sich den Zustand', async () => {
    renderLeiste()
    await screen.findByTestId('km-wert')
    await userEvent.click(screen.getByRole('button', { name: /Schnellwahl/ }))
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
    expect(localStorage.getItem('schnellwahl-leiste-offen')).toBe('zu')
  })

  it('startet eingeklappt, wenn zuletzt eingeklappt', () => {
    localStorage.setItem('schnellwahl-leiste-offen', 'zu')
    renderLeiste()
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Test läuft rot**

Run: `cd frontend && npx vitest run src/components/activities/SchnellwahlLeiste.test.tsx`
Expected: FAIL — `Cannot find module './SchnellwahlLeiste'`

- [ ] **Step 3: Komponente implementieren** — `frontend/src/components/activities/SchnellwahlLeiste.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import Icon from '../ui/Icon'
import { useToast } from '../ui/Toast'
import SchnellwahlCard from './SchnellwahlCard'

const KEY = 'schnellwahl-leiste-offen'

export default function SchnellwahlLeiste() {
  const [offen, setOffen] = useState(localStorage.getItem(KEY) !== 'zu')
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const save = useMutation({
    mutationFn: api.createActivity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activities'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
    onError: (e) => toast(e.message),
  })

  function toggle() {
    const neu = !offen
    setOffen(neu)
    localStorage.setItem(KEY, neu ? 'offen' : 'zu')
  }

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        className="mb-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute hover:text-accent"
      >
        <Icon name="blitz" size={12} />
        Schnellwahl
        <Icon name="chevron" size={12} className={offen ? 'rotate-180' : ''} />
      </button>
      {offen && categories.length > 0 && (
        <SchnellwahlCard
          variant="kompakt"
          categories={categories}
          onSubmit={(input) => save.mutateAsync(input)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Tests laufen grün**

Run: `cd frontend && npx vitest run src/components/activities/SchnellwahlLeiste.test.tsx`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/activities/SchnellwahlLeiste.tsx frontend/src/components/activities/SchnellwahlLeiste.test.tsx
git commit -m "feat: einklappbare schnellwahl-leiste fuer die vergleichsseite"
```

---

### Task 8: Vergleichsseite mit Pill-Tabs

**Files:**
- Modify: `frontend/src/pages/Vergleich.tsx` (komplett ersetzen)

- [ ] **Step 1: Vergleich ersetzen** — `frontend/src/pages/Vergleich.tsx` komplett ersetzen durch:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import SchnellwahlLeiste from '../components/activities/SchnellwahlLeiste'
import JahresVerlauf from '../components/comparison/JahresVerlauf'
import RaceBahnen from '../components/comparison/RaceBahnen'
import WanderKarte from '../components/comparison/WanderKarte'
import Icon from '../components/ui/Icon'
import Select from '../components/ui/Select'

const ANSICHTEN = [
  { key: 'karte', label: 'Karte', icon: 'karte' },
  { key: 'rennen', label: 'Rennen', icon: 'fahne' },
  { key: 'verlauf', label: 'Verlauf', icon: 'chart' },
] as const
type Ansicht = (typeof ANSICHTEN)[number]['key']

export default function Vergleich() {
  const [ansicht, setAnsicht] = useState<Ansicht>('karte')
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [year, setYear] = useState(new Date().getFullYear())
  const { data, error } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
  })

  return (
    <div className="space-y-4">
      <SchnellwahlLeiste />
      <div className="flex flex-wrap items-end gap-2">
        {ANSICHTEN.map((a) => (
          <button
            key={a.key}
            onClick={() => setAnsicht(a.key)}
            className={`flex items-center gap-1.5 rounded-full px-4 py-1 text-sm transition ${
              ansicht === a.key
                ? 'border border-accent font-bold text-accent shadow-glow'
                : 'border border-line text-ink-mute hover:text-ink'
            }`}
          >
            <Icon name={a.icon} size={14} />
            {a.label}
          </button>
        ))}
        <Select
          label="Jahr"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
          className="ml-auto w-24"
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.year}>
              {s.year}
            </option>
          ))}
        </Select>
      </div>
      {error && <p className="text-sm text-danger">{error.message}</p>}
      {data && ansicht === 'karte' && <WanderKarte data={data} />}
      {data && ansicht === 'rennen' && <RaceBahnen data={data} />}
      {data && ansicht === 'verlauf' && <JahresVerlauf data={data} />}
    </div>
  )
}
```

- [ ] **Step 2: Verifizieren**

Run: `cd frontend && npm test && npm run build`
Expected: alle Tests grün, Build ohne TS-Fehler

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Vergleich.tsx
git commit -m "feat: vergleichsseite mit pill-tabs und schnellwahl-leiste"
```

---

### Task 9: Gesamtverifikation + PR

- [ ] **Step 1: Komplette Test-Suite, Lint und Build**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: alle Tests grün, kein Lint-Fehler, Build ohne Fehler

- [ ] **Step 2: Visuelle Stichprobe (optional, falls Backend lauffähig)**

Dev-Server starten (`cd frontend && npm run dev`, Backend per `cd backend && uv run uvicorn app.main:app`), Vergleichsseite öffnen: alle drei Tabs durchschalten, Schnellwahl-Leiste ein-/ausklappen, hell/dunkel toggeln.

- [ ] **Step 3: Push + Stacked PR**

```bash
git push -u origin feature/neon-redesign-2
gh pr create --base feature/neon-redesign-1 --title "feat: Neon-Night-Redesign Plan 2 — Visualisierungen + Vergleichsseite" --body "Plan 2 des Neon-Night-Redesigns (Spec: docs/superpowers/specs/2026-06-13-frontend-redesign-neon-design.md §6–§7, §10.2):

- userColor-Helper: feste Neon-Palette, identische Personenfarbe in allen drei Ansichten
- Race-Bahnen: Glow-Fortschrittsbalken (Verlauf transparent→Personenfarbe), Rang/Avatar/Name, Abstand zu P1, Meilenstein-Marker mit Piktogramm
- Wanderkarte: dunkle Vignette, leuchtende Cyan-Route, Glow-Badges für erreichte Meilensteine, dunkle Namens-Chips
- Jahresverlauf: dezentes Grid, Neon-Linien mit Glow, Endpunkt-Dot + Namens-Label statt Legende, dunkler Tooltip
- Vergleichsseite: Pill-Tabs mit Piktogramm, kompakte einklappbare Schnellwahl-Leiste (localStorage)
- Schnellwahl-Polish: Press-and-hold am Stepper, Glow-Puls beim Speichern, freie-km-Eingabe als String-State (Komma + Zwischenzustände)

Nur Frontend, keine Backend-Änderungen. Stacked auf feature/neon-redesign-1 (PR #3)."
```

Wichtig: Base ist `feature/neon-redesign-1` (Plan 1 noch offen, PR #3). Sobald PR #3 gemerged ist, stellt GitHub die Base automatisch auf `main` um (bzw. manuell retargeten).
