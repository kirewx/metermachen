# Frontend-Redesign „Neon Night" — Plan 1: Fundament + Eingabe

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dunkles Neon-Design-System (Schwarz + Cyan, hell/dunkel umschaltbar), SVG-Piktogramme statt Emojis, neue Schnellwahl-Eingabe mit `default_km` pro Kategorie, Profil-Settings — Seiten Login/Meine Aktivitäten/Admin im neuen Look.

**Architektur:** Theme-Tokens als CSS-Variablen + Tailwind-v4-`@theme`; UI-Bausteine unter `frontend/src/components/ui/`; Backend bekommt drei Felderweiterungen (`Category.icon`, `Category.default_km`, `User.avatar`) mit Startup-Migration in `db.py` (kein Alembic). Spec: `docs/superpowers/specs/2026-06-13-frontend-redesign-neon-design.md`.

**Tech Stack:** FastAPI + SQLModel + SQLite (uv, pytest) · React 19 + TS + Tailwind v4 + TanStack Query (Vite, Vitest/RTL).

**Arbeitsbranch:** `feature/neon-redesign-1` (von `master`).

**Befehle:** Backend-Tests `cd backend && uv run pytest`, Frontend-Tests `cd frontend && npm test`, Lint `cd frontend && npm run lint`, Build `cd frontend && npm run build`.

---

## Verbindliche Namen (überall identisch verwenden)

- Theme-Utilityklassen: `bg-surface`, `bg-card`, `border-line`, `text-ink`, `text-ink-soft`, `text-ink-mute`, `text-accent`, `bg-accent`, `text-accent-ink`, `text-danger`, `border-danger`, `shadow-glow`, `shadow-glow-strong`
- Icon-Schlüssel (Sprite-IDs): `laufen gehen wandern rad schwimmen ski inline tanzen medaille plus minus blitz stift papierkorb chevron karte fahne chart zahnrad mond sonne logout kalender uhr notiz x berg pokal`
- Avatar-Werte: Emoji (z. B. `🦊`) **oder** `icon:<schlüssel>` (z. B. `icon:berg`); Backend-Default `icon:laufen`
- `localStorage`-Schlüssel: `theme` (`hell`/sonst dunkel), `schnellwahl-kategorie`

---

### Task 0: Branch anlegen

- [ ] **Step 1: Branch**

```bash
git checkout -b feature/neon-redesign-1 master
```

---

### Task 1: Theme-Tokens + Hell/Dunkel-Umschaltung

**Files:**
- Modify: `frontend/src/index.css` (komplett ersetzen)
- Modify: `frontend/index.html`
- Create: `frontend/src/components/ui/useTheme.ts`
- Test: `frontend/src/components/ui/useTheme.test.ts`

- [ ] **Step 1: Failing Test schreiben** — `frontend/src/components/ui/useTheme.test.ts`:

```tsx
import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('startet dunkel und setzt die dark-Klasse', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dunkel')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('toggle wechselt auf hell und persistiert', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.toggle())
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('hell')
  })

  it('liest gespeichertes hell beim Start', () => {
    localStorage.setItem('theme', 'hell')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('hell')
  })
})
```

- [ ] **Step 2: Test läuft rot**

Run: `cd frontend && npx vitest run src/components/ui/useTheme.test.ts`
Expected: FAIL — `Cannot find module './useTheme'`

- [ ] **Step 3: Hook implementieren** — `frontend/src/components/ui/useTheme.ts`:

```ts
import { useEffect, useState } from 'react'

export type Theme = 'dunkel' | 'hell'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem('theme') === 'hell' ? 'hell' : 'dunkel',
  )
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dunkel')
    localStorage.setItem('theme', theme)
  }, [theme])
  return { theme, toggle: () => setTheme((t) => (t === 'dunkel' ? 'hell' : 'dunkel')) }
}
```

- [ ] **Step 4: Test läuft grün**

Run: `cd frontend && npx vitest run src/components/ui/useTheme.test.ts`
Expected: 3 passed

- [ ] **Step 5: Theme-Tokens** — `frontend/src/index.css` komplett ersetzen durch:

```css
@import 'tailwindcss';

@custom-variant dark (&:where(.dark, .dark *));

:root {
  /* Heller Modus */
  --t-surface: #f4f7f9;
  --t-card: #ffffff;
  --t-line: #cfe1e8;
  --t-accent: #0891b2;
  --t-accent-ink: #ffffff;
  --t-ink: #0b1c24;
  --t-ink-soft: #33606f;
  --t-ink-mute: #7a99a6;
  --t-danger: #dc2626;
  --t-glow: 0 0 0 0 transparent;
  --t-glow-strong: 0 0 0 0 transparent;
}

.dark {
  /* Neon Night */
  --t-surface: #050508;
  --t-card: #0a0f12;
  --t-line: rgba(0, 229, 255, 0.3);
  --t-accent: #00e5ff;
  --t-accent-ink: #001014;
  --t-ink: #f2fbfd;
  --t-ink-soft: #bfeef7;
  --t-ink-mute: #5a8a96;
  --t-danger: #ff5470;
  --t-glow: 0 0 14px rgba(0, 229, 255, 0.35);
  --t-glow-strong: 0 0 18px rgba(0, 229, 255, 0.6);
}

@theme inline {
  --color-surface: var(--t-surface);
  --color-card: var(--t-card);
  --color-line: var(--t-line);
  --color-accent: var(--t-accent);
  --color-accent-ink: var(--t-accent-ink);
  --color-ink: var(--t-ink);
  --color-ink-soft: var(--t-ink-soft);
  --color-ink-mute: var(--t-ink-mute);
  --color-danger: var(--t-danger);
  --shadow-glow: var(--t-glow);
  --shadow-glow-strong: var(--t-glow-strong);
}

body {
  @apply bg-surface text-ink;
}
```

- [ ] **Step 6: Dark-Bootstrap vor dem ersten Paint** — `frontend/index.html`, im `<head>` nach dem `<title>` einfügen (verhindert hellen Blitz beim Laden):

```html
    <script>
      document.documentElement.classList.toggle(
        'dark',
        localStorage.getItem('theme') !== 'hell',
      )
    </script>
```

Außerdem `<html lang="en">` → `<html lang="de">`.

- [ ] **Step 7: Verifizieren + Commit**

Run: `cd frontend && npm test && npm run build`
Expected: alle Tests grün, Build ok (Seiten sehen jetzt dunkel/roh aus — wird in Folge-Tasks gestylt)

```bash
git add frontend/src/index.css frontend/index.html frontend/src/components/ui/useTheme.ts frontend/src/components/ui/useTheme.test.ts
git commit -m "feat: theme-tokens neon night mit hell/dunkel-umschaltung"
```

---

### Task 2: Icon-Sprite, Icon- und Avatar-Komponente

**Files:**
- Create: `frontend/public/icons.svg`
- Create: `frontend/src/components/ui/Icon.tsx`
- Create: `frontend/src/components/ui/icons.ts`
- Create: `frontend/src/components/ui/Avatar.tsx`
- Test: `frontend/src/components/ui/Icon.test.tsx`

- [ ] **Step 1: Failing Test** — `frontend/src/components/ui/Icon.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Avatar from './Avatar'
import Icon from './Icon'

describe('Icon', () => {
  it('referenziert das Sprite-Symbol', () => {
    const { container } = render(<Icon name="rad" />)
    expect(container.querySelector('use')?.getAttribute('href')).toBe('/icons.svg#rad')
  })
})

describe('Avatar', () => {
  it('rendert Emojis als Text', () => {
    render(<Avatar value="🦊" />)
    expect(screen.getByText('🦊')).toBeInTheDocument()
  })

  it('rendert icon:-Werte als Piktogramm', () => {
    const { container } = render(<Avatar value="icon:berg" />)
    expect(container.querySelector('use')?.getAttribute('href')).toBe('/icons.svg#berg')
  })
})
```

- [ ] **Step 2: Rot** — Run: `cd frontend && npx vitest run src/components/ui/Icon.test.tsx` → FAIL (Module fehlen)

- [ ] **Step 3: Sprite** — `frontend/public/icons.svg` (alle 28 Symbole, Stroke-Stil, `currentColor`):

```svg
<svg xmlns="http://www.w3.org/2000/svg">
  <defs>
    <symbol id="laufen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="14.5" cy="4.5" r="2"/><path d="M5 21l4-2 2-5-2-4 5 2 1.5 3H19M14 8l-4 2-4-1"/></symbol>
    <symbol id="gehen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4" r="2"/><path d="M12 7v5M12 12l-3 8M12 12l3 8M12 8l-3.5 2M12 8l3.5 2"/></symbol>
    <symbol id="wandern" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4" r="2"/><path d="M12 7l-1.5 6 1.5 8M10.5 13 7 21M12 8l3 2.5V21M17.5 11v10"/></symbol>
    <symbol id="rad" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5.5" cy="17" r="3.5"/><circle cx="18.5" cy="17" r="3.5"/><circle cx="15" cy="5" r="1.5"/><path d="M5.5 17l3.5-7h5l4 7M9 10l3 7M14 10l-1-3h3"/></symbol>
    <symbol id="schwimmen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="14" cy="7" r="2"/><path d="M4 12l5-3.5L13 12M2 17.5c2-1.6 4-1.6 6 0s4 1.6 6 0 4-1.6 6 0"/></symbol>
    <symbol id="ski" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="15" cy="4" r="2"/><path d="M14 7l-5 5 5 3v5M9 12l-4 4M3 19.5 21 15"/></symbol>
    <symbol id="inline" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 13h10l5-4M4 13v3.5h12"/><circle cx="7" cy="19.5" r="1.5"/><circle cx="13" cy="19.5" r="1.5"/></symbol>
    <symbol id="tanzen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4" r="2"/><path d="M12 7l-1.5 5 1 9M11 12l4 8M10.5 9l-4.5.5M13.5 9 18 6.5"/></symbol>
    <symbol id="medaille" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="14.5" r="4.5"/><path d="M9.5 10.5 6 3M14.5 10.5 18 3M9 3h6"/></symbol>
    <symbol id="plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12h14"/></symbol>
    <symbol id="minus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/></symbol>
    <symbol id="blitz" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 5 14h6l-1 8 8-12h-6l1-8z"/></symbol>
    <symbol id="stift" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3l4 4L8 20l-5 1 1-5L17 3z"/></symbol>
    <symbol id="papierkorb" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 11v6M14 11v6"/></symbol>
    <symbol id="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></symbol>
    <symbol id="karte" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/></symbol>
    <symbol id="fahne" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 21V4M5 4h13l-3.5 4L18 12H5"/></symbol>
    <symbol id="chart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 20h18M4 16l5-5 4 3 7-8"/></symbol>
    <symbol id="zahnrad" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.5 4.5l2 2M17.5 17.5l2 2M19.5 4.5l-2 2M6.5 17.5l-2 2"/></symbol>
    <symbol id="mond" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z"/></symbol>
    <symbol id="sonne" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9 6.3 6.3M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"/></symbol>
    <symbol id="logout" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/></symbol>
    <symbol id="kalender" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/></symbol>
    <symbol id="uhr" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></symbol>
    <symbol id="notiz" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2h9l5 5v15H6V2zM14 2v6h6"/></symbol>
    <symbol id="x" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6 6 18"/></symbol>
    <symbol id="berg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 20 10 6l4 7 3-4 4 11H3z"/></symbol>
    <symbol id="pokal" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3h8v7a4 4 0 0 1-8 0V3zM8 5H4c0 3 2 5 4 5M16 5h4c0 3-2 5-4 5M12 14v4M8 21h8l-1-3h-6l-1 3z"/></symbol>
  </defs>
</svg>
```

- [ ] **Step 4: Icon-Listen** — `frontend/src/components/ui/icons.ts`:

```ts
export const SPORT_ICONS = [
  'laufen', 'gehen', 'wandern', 'rad', 'schwimmen', 'ski', 'inline', 'tanzen', 'medaille',
] as const

export const MEILENSTEIN_ICONS = ['fahne', 'berg', 'pokal'] as const

export const AVATAR_PIKTOS = [...SPORT_ICONS, ...MEILENSTEIN_ICONS, 'blitz'] as const

export const AVATAR_EMOJIS = [
  '🦊', '🐺', '🦝', '🐻', '🐼', '🐸', '🦅', '🦉', '🐢', '🐙', '🦈', '🦄',
  '🐝', '🦋', '⚡', '🔥', '🌊', '🌙', '⭐', '🍀', '🌵', '🍕', '🎲', '🚀',
]
```

- [ ] **Step 5: Icon-Komponente** — `frontend/src/components/ui/Icon.tsx`:

```tsx
type Props = { name: string; size?: number; className?: string }

export default function Icon({ name, size = 20, className = '' }: Props) {
  return (
    <svg width={size} height={size} className={className} aria-hidden="true">
      <use href={`/icons.svg#${name}`} />
    </svg>
  )
}
```

- [ ] **Step 6: Avatar-Komponente** — `frontend/src/components/ui/Avatar.tsx`:

```tsx
import Icon from './Icon'

const box = { sm: 'h-6 w-6 text-sm', md: 'h-8 w-8 text-lg', lg: 'h-12 w-12 text-2xl' }
const icon = { sm: 14, md: 18, lg: 26 }

type Props = { value: string; size?: keyof typeof box }

export default function Avatar({ value, size = 'md' }: Props) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full border border-line bg-card ${box[size]}`}
    >
      {value.startsWith('icon:') ? (
        <Icon name={value.slice(5)} size={icon[size]} className="text-accent" />
      ) : (
        <span>{value}</span>
      )}
    </span>
  )
}
```

- [ ] **Step 7: Grün + Commit**

Run: `cd frontend && npx vitest run src/components/ui/Icon.test.tsx`
Expected: 3 passed

```bash
git add frontend/public/icons.svg frontend/src/components/ui/Icon.tsx frontend/src/components/ui/icons.ts frontend/src/components/ui/Avatar.tsx frontend/src/components/ui/Icon.test.tsx
git commit -m "feat: svg-piktogramm-sprite mit icon- und avatar-komponente"
```

---

### Task 3: UI-Bausteine Card, Button, Input, Select, Stepper, StatValue

**Files:**
- Create: `frontend/src/components/ui/Card.tsx`, `Button.tsx`, `Input.tsx`, `Select.tsx`, `Stepper.tsx`, `StatValue.tsx`
- Test: `frontend/src/components/ui/Stepper.test.tsx`

- [ ] **Step 1: Failing Test** — `frontend/src/components/ui/Stepper.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Stepper from './Stepper'

describe('Stepper', () => {
  it('erhöht und verringert um step', async () => {
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    expect(onChange).toHaveBeenCalledWith(11)
    await userEvent.click(screen.getByRole('button', { name: '1 km weniger' }))
    expect(onChange).toHaveBeenCalledWith(9)
  })

  it('geht nicht unter das Minimum', async () => {
    const onChange = vi.fn()
    render(<Stepper value={1} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km weniger' }))
    expect(onChange).toHaveBeenCalledWith(1)
  })
})
```

- [ ] **Step 2: Rot** — Run: `cd frontend && npx vitest run src/components/ui/Stepper.test.tsx` → FAIL

- [ ] **Step 3: Bausteine implementieren**

`frontend/src/components/ui/Card.tsx`:

```tsx
type Props = { className?: string; glow?: boolean; children: React.ReactNode }

export default function Card({ className = '', glow = false, children }: Props) {
  return (
    <section
      className={`rounded-2xl border border-line bg-card p-4 ${glow ? 'shadow-glow' : ''} ${className}`}
    >
      {children}
    </section>
  )
}
```

`frontend/src/components/ui/Button.tsx`:

```tsx
type Variant = 'primary' | 'ghost' | 'danger'

const styles: Record<Variant, string> = {
  primary:
    'bg-accent font-black text-accent-ink shadow-glow-strong hover:brightness-110 disabled:opacity-40 disabled:shadow-none',
  ghost: 'border border-line text-ink-soft hover:border-accent hover:text-accent',
  danger: 'border border-danger text-danger hover:bg-danger/10',
}

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }

export default function Button({ variant = 'primary', className = '', ...props }: Props) {
  return (
    <button
      className={`rounded-xl px-4 py-2 text-sm transition ${styles[variant]} ${className}`}
      {...props}
    />
  )
}
```

`frontend/src/components/ui/Input.tsx`:

```tsx
type Props = React.InputHTMLAttributes<HTMLInputElement> & { label: string }

export default function Input({ label, className = '', ...props }: Props) {
  return (
    <label className={`flex flex-col gap-1 text-xs font-semibold text-ink-mute ${className}`}>
      {label}
      <input
        className="rounded-xl border border-line bg-surface p-2 text-sm font-normal text-ink outline-none focus:border-accent"
        {...props}
      />
    </label>
  )
}
```

`frontend/src/components/ui/Select.tsx`:

```tsx
type Props = React.SelectHTMLAttributes<HTMLSelectElement> & { label: string }

export default function Select({ label, className = '', children, ...props }: Props) {
  return (
    <label className={`flex flex-col gap-1 text-xs font-semibold text-ink-mute ${className}`}>
      {label}
      <select
        className="rounded-xl border border-line bg-surface p-2 text-sm font-normal text-ink outline-none focus:border-accent"
        {...props}
      >
        {children}
      </select>
    </label>
  )
}
```

`frontend/src/components/ui/Stepper.tsx`:

```tsx
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
  return (
    <div className={`flex items-center justify-center ${hero ? 'gap-5' : 'gap-2'}`}>
      <button
        type="button"
        aria-label="1 km weniger"
        onClick={() => onChange(Math.max(min, value - step))}
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
        onClick={() => onChange(value + step)}
        className={`flex items-center justify-center rounded-full bg-accent text-accent-ink shadow-glow-strong ${btn}`}
      >
        <Icon name="plus" size={hero ? 24 : 14} />
      </button>
    </div>
  )
}
```

(Hinweis: `h-13`/`w-13` existieren in Tailwind v4 als dynamische Spacing-Werte.)

`frontend/src/components/ui/StatValue.tsx`:

```tsx
type Props = { label: string; value: string; glow?: boolean }

export default function StatValue({ label, value, glow = false }: Props) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">{label}</div>
      <div
        className={`text-2xl font-black tabular-nums text-ink ${glow ? '[text-shadow:var(--t-glow-strong)]' : ''}`}
      >
        {value}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Grün + Commit**

Run: `cd frontend && npx vitest run src/components/ui/Stepper.test.tsx`
Expected: 2 passed

```bash
git add frontend/src/components/ui/Card.tsx frontend/src/components/ui/Button.tsx frontend/src/components/ui/Input.tsx frontend/src/components/ui/Select.tsx frontend/src/components/ui/Stepper.tsx frontend/src/components/ui/StatValue.tsx frontend/src/components/ui/Stepper.test.tsx
git commit -m "feat: ui-bausteine card/button/input/select/stepper/statvalue"
```

---

### Task 4: Modal + Toast

**Files:**
- Create: `frontend/src/components/ui/Modal.tsx`, `frontend/src/components/ui/Toast.tsx`
- Modify: `frontend/src/main.tsx`
- Test: `frontend/src/components/ui/Toast.test.tsx`

- [ ] **Step 1: Failing Test** — `frontend/src/components/ui/Toast.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ToastProvider, useToast } from './Toast'

function Probe() {
  const toast = useToast()
  return <button onClick={() => toast('Kaputt', 'fehler')}>zeig</button>
}

describe('Toast', () => {
  it('zeigt gemeldete Fehler an', async () => {
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'zeig' }))
    expect(screen.getByText('Kaputt')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Rot** — Run: `cd frontend && npx vitest run src/components/ui/Toast.test.tsx` → FAIL

- [ ] **Step 3: Toast implementieren** — `frontend/src/components/ui/Toast.tsx`:

```tsx
/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useState } from 'react'

type Kind = 'fehler' | 'ok'
type ToastItem = { id: number; text: string; kind: Kind }

const ToastContext = createContext<(text: string, kind?: Kind) => void>(() => {})

export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const show = useCallback((text: string, kind: Kind = 'fehler') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, kind }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="fixed bottom-20 left-1/2 z-50 flex w-full max-w-sm -translate-x-1/2 flex-col gap-2 px-4 sm:bottom-6">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`rounded-xl border bg-card p-3 text-sm text-ink shadow-glow ${
              t.kind === 'fehler' ? 'border-danger' : 'border-accent'
            }`}
          >
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
```

- [ ] **Step 4: Modal implementieren** — `frontend/src/components/ui/Modal.tsx`:

```tsx
import Icon from './Icon'

type Props = { open: boolean; onClose: () => void; title: string; children: React.ReactNode }

export default function Modal({ open, onClose, title, children }: Props) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={title}
        className="w-full max-w-md rounded-2xl border border-line bg-card p-5 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-black text-ink">{title}</h2>
          <button aria-label="Schließen" onClick={onClose} className="text-ink-mute hover:text-ink">
            <Icon name="x" size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Provider einhängen** — `frontend/src/main.tsx`, App damit umschließen:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { ToastProvider } from './components/ui/Toast'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
```

- [ ] **Step 6: Grün + Commit**

Run: `cd frontend && npm test`
Expected: alle Tests grün

```bash
git add frontend/src/components/ui/Modal.tsx frontend/src/components/ui/Toast.tsx frontend/src/components/ui/Toast.test.tsx frontend/src/main.tsx
git commit -m "feat: modal- und toast-komponenten"
```

---

### Task 5: Backend — Modellfelder + Startup-Migration

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_migration.py`

- [ ] **Step 1: Modelle ändern** — `backend/app/models.py`:

In `User`: `avatar_emoji: str = "🏃"` → `avatar: str = "icon:laufen"`

In `Category`: `icon_emoji: str` → `icon: str = "medaille"` und neue Zeile darunter `default_km: float = 10.0`

In `Season`: Kommentar anpassen: `milestones_json: str = "[]"  # JSON-Liste [{"km":..,"label":..,"icon":..}]`

- [ ] **Step 2: Failing Test für die Migration** — `backend/tests/test_migration.py`:

```python
import json

from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app.db import migrate

OLD_SCHEMA = """
CREATE TABLE user (
    id INTEGER PRIMARY KEY, username VARCHAR, password_hash VARCHAR,
    display_name VARCHAR, avatar_emoji VARCHAR, is_admin BOOLEAN, created_at DATETIME
);
CREATE TABLE category (
    id INTEGER PRIMARY KEY, name VARCHAR, factor FLOAT, color VARCHAR,
    icon_emoji VARCHAR, is_active BOOLEAN
);
CREATE TABLE season (
    id INTEGER PRIMARY KEY, year INTEGER, goal_km FLOAT,
    milestones_json VARCHAR, map_image VARCHAR
);
"""


def make_old_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        for stmt in OLD_SCHEMA.strip().split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
        conn.execute(
            text(
                "INSERT INTO user (username, password_hash, display_name, avatar_emoji, is_admin)"
                " VALUES ('erik', 'x', 'Erik', '🏃', 1)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO category (name, factor, color, icon_emoji, is_active)"
                " VALUES ('Radfahren', 1.0, '#3498db', '🚴', 1), ('Kurios', 2.0, '#000000', '🦖', 1)"
            )
        )
        conn.execute(
            text("INSERT INTO season (year, goal_km, milestones_json) VALUES (2026, 1000, :m)"),
            {"m": json.dumps([{"km": 500, "label": "Halbzeit", "emoji": "🏔"}])},
        )
    return engine


def test_migration_benennt_um_und_mappt():
    engine = make_old_engine()
    migrate(engine)
    with engine.connect() as conn:
        user_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(user)"))]
        cat_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(category)"))]
        assert "avatar" in user_cols and "avatar_emoji" not in user_cols
        assert "icon" in cat_cols and "default_km" in cat_cols
        # Emojis bleiben als Avatar gültig
        assert conn.execute(text("SELECT avatar FROM user")).scalar() == "🏃"
        icons = [r[0] for r in conn.execute(text("SELECT icon FROM category ORDER BY id"))]
        assert icons == ["rad", "medaille"]  # bekannt gemappt, unbekannt → Fallback
        assert conn.execute(text("SELECT default_km FROM category")).scalar() == 10.0
        ms = json.loads(conn.execute(text("SELECT milestones_json FROM season")).scalar())
        assert ms == [{"km": 500, "label": "Halbzeit", "icon": "berg"}]


def test_migration_ist_idempotent():
    engine = make_old_engine()
    migrate(engine)
    migrate(engine)  # zweiter Lauf darf nichts kaputt machen
    with engine.connect() as conn:
        assert conn.execute(text("SELECT icon FROM category WHERE id = 1")).scalar() == "rad"
```

- [ ] **Step 3: Rot**

Run: `cd backend && uv run pytest tests/test_migration.py -v`
Expected: FAIL — `cannot import name 'migrate'`

- [ ] **Step 4: Migration implementieren** — `backend/app/db.py` komplett ersetzen:

```python
import json

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from . import config
from . import models  # noqa: F401  — Tabellen registrieren

engine = create_engine(config.database_url(), connect_args={"check_same_thread": False})

ICON_KEYS = {
    "laufen", "gehen", "wandern", "rad", "schwimmen", "ski", "inline", "tanzen",
    "medaille", "fahne", "berg", "pokal", "blitz",
}
EMOJI_TO_ICON = {
    "🏃": "laufen", "👟": "laufen", "🚶": "gehen", "🥾": "wandern", "🏊": "schwimmen",
    "🚴": "rad", "💃": "tanzen", "🎿": "ski", "⛸": "inline", "🏅": "medaille",
    "🚩": "fahne", "🏔": "berg", "⛰": "berg", "🏆": "pokal",
}


def _columns(conn, table: str) -> list[str]:
    return [row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))]


def _icon_for(value: str, fallback: str) -> str:
    if value in ICON_KEYS:
        return value
    return EMOJI_TO_ICON.get(value, fallback)


def migrate(target=engine) -> None:
    """Schema-Anpassungen für Bestands-DBs (es gibt kein Alembic)."""
    with target.begin() as conn:
        if "avatar_emoji" in _columns(conn, "user"):
            conn.execute(text('ALTER TABLE "user" RENAME COLUMN avatar_emoji TO avatar'))

        cat_cols = _columns(conn, "category")
        if "icon_emoji" in cat_cols:
            conn.execute(text("ALTER TABLE category RENAME COLUMN icon_emoji TO icon"))
            for id_, val in conn.execute(text("SELECT id, icon FROM category")).fetchall():
                conn.execute(
                    text("UPDATE category SET icon = :i WHERE id = :id"),
                    {"i": _icon_for(val, "medaille"), "id": id_},
                )
        if "default_km" not in cat_cols and "default_km" not in _columns(conn, "category"):
            conn.execute(
                text("ALTER TABLE category ADD COLUMN default_km FLOAT NOT NULL DEFAULT 10.0")
            )

        for id_, raw in conn.execute(text("SELECT id, milestones_json FROM season")).fetchall():
            milestones = json.loads(raw)
            if any("emoji" in m for m in milestones):
                for m in milestones:
                    m["icon"] = _icon_for(m.pop("emoji", ""), "fahne")
                conn.execute(
                    text("UPDATE season SET milestones_json = :m WHERE id = :id"),
                    {"m": json.dumps(milestones), "id": id_},
                )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    migrate(engine)
```

- [ ] **Step 5: Grün**

Run: `cd backend && uv run pytest tests/test_migration.py -v`
Expected: 2 passed (übrige Tests sind noch rot wegen der Renames — kommt in Task 6)

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/db.py backend/tests/test_migration.py
git commit -m "feat: category.icon/default_km und user.avatar mit startup-migration"
```

---

### Task 6: Backend — Schemas, Router, Seed + Test-Anpassungen

**Files:**
- Modify: `backend/app/schemas.py`, `backend/app/seed.py`, `backend/app/routers/auth_router.py`, `backend/app/routers/users.py`, `backend/app/routers/comparison.py`
- Modify: `backend/tests/*` (mechanische Renames) und `backend/tests/test_categories.py` (neuer Test)

- [ ] **Step 1: Schemas** — `backend/app/schemas.py`:

`Milestone`: `emoji: str = "🚩"` → `icon: str = "fahne"`

`CategoryCreate`: `icon_emoji: str = "🏅"` → ersetzen durch:

```python
    icon: str = "medaille"
    default_km: float = Field(default=10.0, gt=0)
```

`CategoryPatch`: `icon_emoji: str | None = None` → ersetzen durch:

```python
    icon: str | None = None
    default_km: float | None = Field(default=None, gt=0)
```

`CategoryShare`: `icon_emoji: str` → `icon: str`

`ComparisonUser`: `avatar_emoji: str` → `avatar: str`

- [ ] **Step 2: Router** —

`backend/app/routers/auth_router.py`, in `MeOut`: `avatar_emoji: str` → `avatar: str`

`backend/app/routers/users.py`: in `UserCreate`: `avatar_emoji: str = "🏃"` → `avatar: str = "icon:laufen"`; in `ProfilePatch`: `avatar_emoji: str | None = None` → `avatar: str | None = None`; in `create_user`: `avatar_emoji=data.avatar_emoji` → `avatar=data.avatar`; in `patch_me` beide Vorkommen `data.avatar_emoji`/`user.avatar_emoji` → `data.avatar`/`user.avatar`.

`backend/app/routers/comparison.py`: `icon_emoji=c.icon_emoji` → `icon=c.icon` und `avatar_emoji=user.avatar_emoji` → `avatar=user.avatar`.

- [ ] **Step 3: Seed** — `backend/app/seed.py`, Kategorienliste ersetzen:

```python
DEFAULT_CATEGORIES = [
    # (Name, Faktor, Farbe, Icon, Standard-km)
    ("Joggen", 4.0, "#e74c3c", "laufen", 5.0),
    ("Laufen", 4.0, "#c0392b", "laufen", 5.0),
    ("Spazieren", 3.0, "#f1c40f", "gehen", 5.0),
    ("Wandern", 3.0, "#27ae60", "wandern", 10.0),
    ("Schwimmen", 10.0, "#9b59b6", "schwimmen", 1.0),
    ("Radfahren", 1.0, "#3498db", "rad", 20.0),
    ("Tanzen", 3.0, "#e67e22", "tanzen", 5.0),
]
```

und die Schleife:

```python
        for name, factor, color, icon, default_km in DEFAULT_CATEGORIES:
            session.add(
                Category(name=name, factor=factor, color=color, icon=icon, default_km=default_km)
            )
```

- [ ] **Step 4: Tests mechanisch nachziehen**

```bash
cd backend
grep -rln "icon_emoji\|avatar_emoji" tests | xargs sed -i 's/icon_emoji/icon/g; s/avatar_emoji/avatar/g'
grep -rn '"emoji"\|emoji=' tests   # Meilenstein-Fixtures: Feld emoji → icon, Werte z. B. "🚩" → "fahne"
```

Danach in den Treffern Emoji-**Werte** durch Icon-Schlüssel ersetzen (z. B. `icon="🏃"` → `icon="laufen"`, Meilenstein `{"km": .., "label": .., "emoji": "🚩"}` → `{"km": .., "label": .., "icon": "fahne"}`). Test-Helfer (`make_category`/`make_user` in `tests/conftest.py`) ebenso.

- [ ] **Step 5: Neuer Test für default_km** — ans Ende von `backend/tests/test_categories.py`:

```python
def test_default_km_anlegen_und_patchen(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post(
        "/api/categories",
        json={"name": "Rudern", "factor": 2.0, "color": "#123456", "icon": "medaille", "default_km": 7.5},
    )
    assert r.status_code == 201
    assert r.json()["default_km"] == 7.5
    cat_id = r.json()["id"]
    r = client.patch(f"/api/categories/{cat_id}", json={"default_km": 12.0})
    assert r.json()["default_km"] == 12.0


def test_default_km_muss_positiv_sein(client, session):
    make_user(session, is_admin=True)
    login(client)
    r = client.post(
        "/api/categories",
        json={"name": "Kaputt", "factor": 1.0, "color": "#123456", "default_km": 0},
    )
    assert r.status_code == 422
```

(Falls `test_categories.py` andere Helfer-Signaturen nutzt: an die dortigen bestehenden Tests anlehnen — `make_user`/`login` so aufrufen wie im Rest der Datei.)

- [ ] **Step 6: Alles grün + Commit**

Run: `cd backend && uv run pytest`
Expected: alle Tests passed

```bash
git add backend/app backend/tests
git commit -m "feat: backend-schemas/router/seed auf icon, avatar und default_km umgestellt"
```

---

### Task 7: Frontend — API-Typen + mechanische Renames

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/ui/Layout.tsx:21`, `frontend/src/components/activities/ActivityForm.tsx:42`, `frontend/src/components/activities/ActivityForm.test.tsx:8-9`, `frontend/src/pages/MeineAktivitaeten.tsx:56`, `frontend/src/pages/Admin.tsx`, `frontend/src/components/comparison/RaceBahnen.tsx`, `frontend/src/components/comparison/WanderKarte.tsx`, `frontend/src/components/comparison/JahresVerlauf.tsx:45`

Ziel: Build bleibt grün; echtes Redesign der Seiten folgt in Task 8–13. Vergleichs-Komponenten werden nur kompiliersicher gemacht (Optik: Plan 2).

- [ ] **Step 1: Typen** — `frontend/src/api/client.ts`:

```ts
export type Me = {
  id: number
  username: string
  display_name: string
  avatar: string
  is_admin: boolean
}
export type Category = {
  id: number
  name: string
  factor: number
  color: string
  icon: string
  default_km: number
  is_active: boolean
}
export type Milestone = { km: number; label: string; icon: string }
```

`CategoryShare.icon_emoji` → `icon: string`; `ComparisonUser.avatar_emoji` → `avatar: string`; `createUser`-Parameter `avatar_emoji?: string` → `avatar?: string`; `patchMe`-Parameter `avatar_emoji?: string` → `avatar?: string`. `createCategory`-Signatur bleibt (`Omit<Category, 'id' | 'is_active'>` deckt `icon`/`default_km` jetzt mit ab).

- [ ] **Step 2: Komponenten kompiliersicher machen**

`Layout.tsx` Zeile 21: `{me.avatar_emoji} {me.display_name}` → `{me.avatar.startsWith('icon:') ? me.display_name : `${me.avatar} ${me.display_name}`}`

`ActivityForm.tsx` Zeile 42: `{c.icon_emoji} {c.name} ({c.factor}x)` → `{c.name} ({c.factor}x)`

`ActivityForm.test.tsx` Fixtures: `icon_emoji: '🏃'` → `icon: 'laufen', default_km: 5`, `icon_emoji: '🦖'` → `icon: 'medaille', default_km: 10`

`MeineAktivitaeten.tsx` Zeile 56: `<span className="text-xl">{cat?.icon_emoji}</span>` → `{cat && <Icon name={cat.icon} className="text-accent" />}` (Import oben: `import Icon from '../components/ui/Icon'`)

`Admin.tsx`: alle `icon_emoji` → `icon` (Startwert `'🏅'` → `'medaille'`), `avatar_emoji: '🏃'` → `avatar: 'icon:laufen'`, Meilenstein `m.emoji` → `m.icon` (zwei Stellen) und Default `{ km: 0, label: '', emoji: '🚩' }` → `{ km: 0, label: '', icon: 'fahne' }`

`RaceBahnen.tsx` Zeile 17: `{m.emoji} {m.km}` → `{m.km}`; Zeile 32: `{u.rank === 1 ? '👑 ' : ''}{u.avatar_emoji} {u.display_name}` → `{u.rank === 1 ? '★ ' : ''}{u.avatar.startsWith('icon:') ? '' : u.avatar} {u.display_name}`

`WanderKarte.tsx` Zeile 65: `{m.emoji}` → `▲`; Zeile 89: `{u.avatar_emoji}` → `{u.avatar.startsWith('icon:') ? u.display_name[0] : u.avatar}`; Zeile 101: `{selectedUser.avatar_emoji} {selectedUser.display_name}` → `{selectedUser.display_name}`; Zeile 108: `{b.icon_emoji} {b.name}` → `{b.name}`

`JahresVerlauf.tsx` Zeile 45: `` `${m.emoji} ${m.label}` `` → `m.label`

- [ ] **Step 3: Grün + Commit**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: alles grün

```bash
git add frontend/src
git commit -m "refactor: frontend auf icon/avatar/default_km-felder umgestellt"
```

---

### Task 8: Layout/Navigation neu (Glasleiste, Pills, Bottom-Bar, Theme-Toggle)

**Files:**
- Modify: `frontend/src/components/ui/Layout.tsx` (komplett ersetzen)
- Modify: `frontend/src/App.tsx` (Lade-Text stylen)

- [ ] **Step 1: Layout ersetzen** — `frontend/src/components/ui/Layout.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api, type Me } from '../../api/client'
import ProfilModal from './ProfilModal'
import Avatar from './Avatar'
import Icon from './Icon'
import { useTheme } from './useTheme'

const TABS = [
  { to: '/', label: 'Vergleich', icon: 'fahne', end: true, adminOnly: false },
  { to: '/aktivitaeten', label: 'Aktivitäten', icon: 'blitz', end: false, adminOnly: false },
  { to: '/admin', label: 'Admin', icon: 'zahnrad', end: false, adminOnly: true },
]

const pill = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition ${
    isActive
      ? 'border border-accent font-bold text-accent shadow-glow'
      : 'text-ink-mute hover:text-ink'
  }`

export default function Layout({ me }: { me: Me }) {
  const queryClient = useQueryClient()
  const { theme, toggle } = useTheme()
  const [profilOffen, setProfilOffen] = useState(false)
  const tabs = TABS.filter((t) => !t.adminOnly || me.is_admin)

  async function logout() {
    await api.logout()
    queryClient.setQueryData(['me'], null)
  }

  return (
    <div className="min-h-screen pb-20 sm:pb-0">
      <nav className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-card/80 px-4 py-2 backdrop-blur">
        <span className="mr-2 flex items-center gap-1 font-black tracking-wide text-ink">
          <Icon name="blitz" size={16} className="text-accent" />
          METER<span className="text-accent [text-shadow:var(--t-glow)]">MACHEN</span>
        </span>
        <div className="hidden gap-1 sm:flex">
          {tabs.map((t) => (
            <NavLink key={t.to} to={t.to} end={t.end} className={pill}>
              <Icon name={t.icon} size={14} />
              {t.label}
            </NavLink>
          ))}
        </div>
        <button
          aria-label="Farbmodus wechseln"
          onClick={toggle}
          className="ml-auto text-ink-mute hover:text-accent"
        >
          <Icon name={theme === 'dunkel' ? 'sonne' : 'mond'} size={18} />
        </button>
        <button
          onClick={() => setProfilOffen(true)}
          className="flex items-center gap-2 text-sm text-ink-soft hover:text-ink"
        >
          <Avatar value={me.avatar} size="sm" />
          <span className="hidden sm:inline">{me.display_name}</span>
        </button>
        <button aria-label="Logout" onClick={logout} className="text-ink-mute hover:text-danger">
          <Icon name="logout" size={18} />
        </button>
      </nav>
      <main className="mx-auto max-w-5xl p-4">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-line bg-card/95 py-2 backdrop-blur sm:hidden">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 text-[10px] font-bold ${
                isActive ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
              }`
            }
          >
            <Icon name={t.icon} size={20} />
            {t.label}
          </NavLink>
        ))}
      </nav>
      <ProfilModal me={me} open={profilOffen} onClose={() => setProfilOffen(false)} />
    </div>
  )
}
```

(`ProfilModal` entsteht in Task 9 — Task 8 und 9 zusammen committen, damit der Build grün ist.)

- [ ] **Step 2: App-Ladezustand** — `frontend/src/App.tsx` Zeile 15: `<p className="p-8">Lade…</p>` → `<p className="p-8 text-ink-mute">Lade…</p>`

---

### Task 9: ProfilModal + AvatarWahl + IconPicker

**Files:**
- Create: `frontend/src/components/ui/IconPicker.tsx`, `frontend/src/components/ui/AvatarWahl.tsx`, `frontend/src/components/ui/ProfilModal.tsx`
- Test: `frontend/src/components/ui/AvatarWahl.test.tsx`

- [ ] **Step 1: Failing Test** — `frontend/src/components/ui/AvatarWahl.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AvatarWahl from './AvatarWahl'

describe('AvatarWahl', () => {
  it('liefert Emojis direkt', async () => {
    const onChange = vi.fn()
    render(<AvatarWahl value="🦊" onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '🐸' }))
    expect(onChange).toHaveBeenCalledWith('🐸')
  })

  it('liefert Piktogramme mit icon:-Präfix', async () => {
    const onChange = vi.fn()
    render(<AvatarWahl value="🦊" onChange={onChange} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Piktogramme' }))
    await userEvent.click(screen.getByRole('button', { name: 'berg' }))
    expect(onChange).toHaveBeenCalledWith('icon:berg')
  })
})
```

- [ ] **Step 2: Rot** — Run: `cd frontend && npx vitest run src/components/ui/AvatarWahl.test.tsx` → FAIL

- [ ] **Step 3: IconPicker** — `frontend/src/components/ui/IconPicker.tsx`:

```tsx
import Icon from './Icon'

type Props = { auswahl: readonly string[]; value: string; onChange: (v: string) => void }

export default function IconPicker({ auswahl, value, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-1">
      {auswahl.map((name) => (
        <button
          key={name}
          type="button"
          aria-label={name}
          onClick={() => onChange(name)}
          className={`flex h-9 w-9 items-center justify-center rounded-xl border transition ${
            value === name
              ? 'border-accent text-accent shadow-glow'
              : 'border-line text-ink-mute hover:text-ink'
          }`}
        >
          <Icon name={name} />
        </button>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: AvatarWahl** — `frontend/src/components/ui/AvatarWahl.tsx`:

```tsx
import { useState } from 'react'
import IconPicker from './IconPicker'
import { AVATAR_EMOJIS, AVATAR_PIKTOS } from './icons'

type Props = { value: string; onChange: (v: string) => void }

const tab = (aktiv: boolean) =>
  `rounded-full px-3 py-1 text-xs font-bold ${
    aktiv ? 'border border-accent text-accent' : 'text-ink-mute'
  }`

export default function AvatarWahl({ value, onChange }: Props) {
  const [modus, setModus] = useState<'emoji' | 'pikto'>(
    value.startsWith('icon:') ? 'pikto' : 'emoji',
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
      </div>
      {modus === 'emoji' ? (
        <div className="flex flex-wrap gap-1">
          {AVATAR_EMOJIS.map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => onChange(e)}
              className={`flex h-9 w-9 items-center justify-center rounded-xl border text-lg ${
                value === e ? 'border-accent shadow-glow' : 'border-line'
              }`}
            >
              {e}
            </button>
          ))}
        </div>
      ) : (
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

- [ ] **Step 5: ProfilModal** — `frontend/src/components/ui/ProfilModal.tsx`:

```tsx
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Me } from '../../api/client'
import AvatarWahl from './AvatarWahl'
import Button from './Button'
import Input from './Input'
import Modal from './Modal'
import { useToast } from './Toast'

type Props = { me: Me; open: boolean; onClose: () => void }

export default function ProfilModal({ me, open, onClose }: Props) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState(me.display_name)
  const [avatar, setAvatar] = useState(me.avatar)
  const [passwort, setPasswort] = useState('')

  const save = useMutation({
    mutationFn: () =>
      api.patchMe({
        display_name: name,
        avatar,
        ...(passwort ? { password: passwort } : {}),
      }),
    onSuccess: (neu) => {
      queryClient.setQueryData(['me'], neu)
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
      setPasswort('')
      toast('Profil gespeichert', 'ok')
      onClose()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <Modal open={open} onClose={onClose} title="Profil">
      <div className="space-y-4">
        <Input label="Anzeigename" value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <div className="mb-1 text-xs font-semibold text-ink-mute">Avatar</div>
          <AvatarWahl value={avatar} onChange={setAvatar} />
        </div>
        <Input
          label="Neues Passwort (leer = unverändert)"
          type="password"
          value={passwort}
          onChange={(e) => setPasswort(e.target.value)}
        />
        <Button
          className="w-full"
          disabled={!name || (passwort.length > 0 && passwort.length < 4)}
          onClick={() => save.mutate()}
        >
          Speichern
        </Button>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 6: Grün + Commit (zusammen mit Task 8)**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: alles grün

```bash
git add frontend/src/components/ui frontend/src/App.tsx
git commit -m "feat: neue navigation mit bottom-bar, theme-toggle und profil-settings"
```

---

### Task 10: SchnellwahlCard (ersetzt ActivityForm)

**Files:**
- Create: `frontend/src/components/activities/SchnellwahlCard.tsx`
- Test: `frontend/src/components/activities/SchnellwahlCard.test.tsx`
- Delete: `frontend/src/components/activities/ActivityForm.tsx`, `frontend/src/components/activities/ActivityForm.test.tsx` (erst in Task 11, wenn die Seite umgestellt ist)

- [ ] **Step 1: Failing Tests** — `frontend/src/components/activities/SchnellwahlCard.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Category } from '../../api/client'
import SchnellwahlCard from './SchnellwahlCard'

const categories: Category[] = [
  { id: 1, name: 'Joggen', factor: 4, color: '#e74c3c', icon: 'laufen', default_km: 5, is_active: true },
  { id: 2, name: 'Radfahren', factor: 1, color: '#3498db', icon: 'rad', default_km: 20, is_active: true },
  { id: 3, name: 'Alt', factor: 2, color: '#000000', icon: 'medaille', default_km: 10, is_active: false },
]

const heute = () => new Date().toISOString().slice(0, 10)

describe('SchnellwahlCard', () => {
  beforeEach(() => localStorage.clear())

  it('zeigt nur aktive Kategorien', () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByRole('option', { name: /Joggen/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Alt/ })).not.toBeInTheDocument()
  })

  it('startet beim Standard-km der ersten Kategorie', () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByTestId('km-wert')).toHaveTextContent('5')
  })

  it('Kategoriewechsel setzt auf deren Standard und merkt die Wahl', async () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    await userEvent.selectOptions(screen.getByLabelText('Kategorie'), '2')
    expect(screen.getByTestId('km-wert')).toHaveTextContent('20')
    expect(localStorage.getItem('schnellwahl-kategorie')).toBe('2')
  })

  it('plus/minus in 1-km-Schritten, nicht unter 1', async () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    expect(screen.getByTestId('km-wert')).toHaveTextContent('6')
    for (let i = 0; i < 7; i++) {
      await userEvent.click(screen.getByRole('button', { name: '1 km weniger' }))
    }
    expect(screen.getByTestId('km-wert')).toHaveTextContent('1')
  })

  it('zeigt die gewertete Distanz', () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByText(/= 20\.0 km gewertet/)).toBeInTheDocument()
  })

  it('Submit ohne Details nutzt heute als Datum', async () => {
    const onSubmit = vi.fn()
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: heute(),
      distance_km: 5,
      duration_min: null,
      note: null,
    })
  })

  it('Details: Datum, Dauer, Notiz und freie km werden übernommen', async () => {
    const onSubmit = vi.fn()
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: 'Details' }))
    const datum = screen.getByLabelText('Datum')
    await userEvent.clear(datum)
    await userEvent.type(datum, '2026-03-01')
    await userEvent.type(screen.getByLabelText('Dauer (min)'), '42')
    await userEvent.type(screen.getByLabelText('Notiz'), 'Runde am Fluss')
    const frei = screen.getByLabelText('km (frei)')
    await userEvent.clear(frei)
    await userEvent.type(frei, '7.5')
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: '2026-03-01',
      distance_km: 7.5,
      duration_min: 42,
      note: 'Runde am Fluss',
    })
  })

  it('füllt beim Bearbeiten die Eintragswerte vor', () => {
    render(
      <SchnellwahlCard
        categories={categories}
        initial={{
          id: 9, category_id: 2, date: '2026-02-02', distance_km: 33,
          duration_min: 90, note: 'Tour', scaled_km: 33, edited: false,
        }}
        onSubmit={vi.fn()}
      />,
    )
    expect(screen.getByTestId('km-wert')).toHaveTextContent('33')
    expect(screen.getByLabelText('Datum')).toHaveValue('2026-02-02')
    expect(screen.getByLabelText('Notiz')).toHaveValue('Tour')
  })
})
```

- [ ] **Step 2: Rot** — Run: `cd frontend && npx vitest run src/components/activities/SchnellwahlCard.test.tsx` → FAIL

- [ ] **Step 3: Implementieren** — `frontend/src/components/activities/SchnellwahlCard.tsx`:

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
  onSubmit: (input: ActivityInput) => void
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
  const [km, setKm] = useState(initial?.distance_km ?? kategorie?.default_km ?? 10)
  const [details, setDetails] = useState(Boolean(initial))
  const [date, setDate] = useState(initial?.date ?? heute())
  const [duration, setDuration] = useState(initial?.duration_min ? String(initial.duration_min) : '')
  const [note, setNote] = useState(initial?.note ?? '')

  function wechselKategorie(id: number) {
    setCategoryId(id)
    localStorage.setItem('schnellwahl-kategorie', String(id))
    if (!initial) setKm(aktive.find((c) => c.id === id)?.default_km ?? 10)
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!categoryId || !Number.isFinite(km) || km <= 0 || !date) return
    onSubmit({
      category_id: categoryId,
      date,
      distance_km: km,
      duration_min: duration ? parseInt(duration, 10) : null,
      note: note || null,
    })
    if (!initial) {
      setKm(kategorie?.default_km ?? 10)
      setDetails(false)
      setDate(heute())
      setDuration('')
      setNote('')
    }
  }

  const gewertet = kategorie ? (km * kategorie.factor).toFixed(1) : '0.0'
  const datumText = date === heute() ? 'heute' : date

  return (
    <form onSubmit={submit}>
      <Card glow className={variant === 'hero' ? 'mx-auto max-w-md p-6 text-center' : 'p-3'}>
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
          <Stepper value={km} onChange={setKm} size={variant === 'hero' ? 'hero' : 'kompakt'} />
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
              type="number"
              step="0.1"
              min="0.1"
              value={km}
              onChange={(e) => setKm(parseFloat(e.target.value) || 0)}
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

- [ ] **Step 4: Grün + Commit**

Run: `cd frontend && npx vitest run src/components/activities/SchnellwahlCard.test.tsx`
Expected: 8 passed

```bash
git add frontend/src/components/activities/SchnellwahlCard.tsx frontend/src/components/activities/SchnellwahlCard.test.tsx
git commit -m "feat: schnellwahl-karte mit km-stepper, default_km und details-toggle"
```

---

### Task 11: Seite „Meine Aktivitäten" neu

**Files:**
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx` (komplett ersetzen)
- Delete: `frontend/src/components/activities/ActivityForm.tsx`, `frontend/src/components/activities/ActivityForm.test.tsx`

- [ ] **Step 1: Seite ersetzen** — `frontend/src/pages/MeineAktivitaeten.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Activity, type ActivityInput } from '../api/client'
import SchnellwahlCard from '../components/activities/SchnellwahlCard'
import Button from '../components/ui/Button'
import Icon from '../components/ui/Icon'
import Modal from '../components/ui/Modal'
import { useToast } from '../components/ui/Toast'

export default function MeineAktivitaeten() {
  const year = new Date().getFullYear()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<Activity | null>(null)
  const [loeschId, setLoeschId] = useState<number | null>(null)

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities = [] } = useQuery({
    queryKey: ['activities', year],
    queryFn: () => api.activities(year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))
  const gesamt = activities.reduce((s, a) => s + a.scaled_km, 0)

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['activities'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const save = useMutation({
    mutationFn: (input: ActivityInput) =>
      editing ? api.patchActivity(editing.id, input) : api.createActivity(input),
    onSuccess: () => {
      if (editing) toast('Eintrag aktualisiert', 'ok')
      setEditing(null)
      invalidate()
    },
    onError: (e) => toast(e.message),
  })
  const remove = useMutation({
    mutationFn: api.deleteActivity,
    onSuccess: () => {
      setLoeschId(null)
      invalidate()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <div className="space-y-6">
      <SchnellwahlCard
        key={editing?.id ?? 'neu'}
        categories={categories}
        initial={editing ?? undefined}
        onSubmit={save.mutate}
        onCancel={editing ? () => setEditing(null) : undefined}
      />
      <div className="flex items-baseline justify-between">
        <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
          Meine Einträge {year}
        </h2>
        <span className="text-sm font-black tabular-nums text-accent [text-shadow:var(--t-glow)]">
          {Math.round(gesamt)} km gewertet
        </span>
      </div>
      <ul className="space-y-2">
        {activities.map((a) => {
          const cat = catById.get(a.category_id)
          return (
            <li
              key={a.id}
              className="flex items-center gap-3 rounded-2xl border border-line bg-card p-3"
            >
              {cat && <Icon name={cat.icon} size={22} className="shrink-0 text-accent" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-ink">
                  {a.distance_km} km {cat?.name}{' '}
                  <span className="text-accent">→ {a.scaled_km} km</span>
                  {a.edited && <span className="ml-2 text-xs font-normal text-ink-mute">(bearbeitet)</span>}
                </p>
                <p className="truncate text-xs text-ink-mute">
                  {a.date}
                  {a.duration_min ? ` · ${a.duration_min} min` : ''}
                  {a.note ? ` · ${a.note}` : ''}
                </p>
              </div>
              <button
                aria-label="Bearbeiten"
                className="text-ink-mute hover:text-accent"
                onClick={() => setEditing(a)}
              >
                <Icon name="stift" size={16} />
              </button>
              <button
                aria-label="Löschen"
                className="text-ink-mute hover:text-danger"
                onClick={() => setLoeschId(a.id)}
              >
                <Icon name="papierkorb" size={16} />
              </button>
            </li>
          )
        })}
        {activities.length === 0 && <p className="text-sm text-ink-mute">Noch keine Einträge.</p>}
      </ul>
      <Modal open={loeschId !== null} onClose={() => setLoeschId(null)} title="Eintrag löschen?">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setLoeschId(null)}>
            Abbrechen
          </Button>
          <Button variant="danger" onClick={() => loeschId !== null && remove.mutate(loeschId)}>
            Löschen
          </Button>
        </div>
      </Modal>
    </div>
  )
}
```

- [ ] **Step 2: ActivityForm entfernen**

```bash
git rm frontend/src/components/activities/ActivityForm.tsx frontend/src/components/activities/ActivityForm.test.tsx
```

- [ ] **Step 3: Grün + Commit**

Run: `cd frontend && npm test && npm run lint && npm run build`
Expected: alles grün

```bash
git add frontend/src/pages/MeineAktivitaeten.tsx
git commit -m "feat: aktivitaeten-seite mit schnellwahl-hero, summenzeile und loesch-modal"
```

---

### Task 12: Login-Seite neu

**Files:**
- Modify: `frontend/src/pages/Login.tsx` (komplett ersetzen)

- [ ] **Step 1: Ersetzen** — `frontend/src/pages/Login.tsx`:

```tsx
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import Input from '../components/ui/Input'

export default function Login() {
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const me = await api.login(username, password)
      queryClient.setQueryData(['me'], me)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login fehlgeschlagen')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-xs">
        <Card glow className="space-y-4 p-7 text-center">
          <h1 className="flex items-center justify-center gap-1 text-2xl font-black tracking-wide text-ink">
            <Icon name="blitz" size={20} className="text-accent" />
            METER<span className="text-accent [text-shadow:var(--t-glow)]">MACHEN</span>
          </h1>
          <p className="text-xs text-ink-mute">Wer macht die Meter?</p>
          <Input
            label="Benutzername"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="text-left"
          />
          <Input
            label="Passwort"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="text-left"
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" className="w-full">
            Los geht's
          </Button>
        </Card>
      </form>
    </div>
  )
}
```

- [ ] **Step 2: Grün + Commit**

Run: `cd frontend && npm test && npm run build`

```bash
git add frontend/src/pages/Login.tsx
git commit -m "feat: login-seite im neon-look"
```

---

### Task 13: Admin-Seite neu

**Files:**
- Modify: `frontend/src/pages/Admin.tsx` (komplett ersetzen)

- [ ] **Step 1: Ersetzen** — `frontend/src/pages/Admin.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Milestone, type Season } from '../api/client'
import AvatarWahl from '../components/ui/AvatarWahl'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import IconPicker from '../components/ui/IconPicker'
import Input from '../components/ui/Input'
import { MEILENSTEIN_ICONS, SPORT_ICONS } from '../components/ui/icons'
import { useToast } from '../components/ui/Toast'

const H = ({ children }: { children: React.ReactNode }) => (
  <h2 className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">{children}</h2>
)

export default function Admin() {
  return (
    <div className="space-y-6">
      <Kategorien />
      <Jahr />
      <NeuerUser />
    </div>
  )
}

function Kategorien() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['categories'] })
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: number; factor?: number; default_km?: number; is_active?: boolean }) =>
      api.patchCategory(id, b),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
  const leer = { name: '', factor: '1', color: '#00b3cc', icon: 'medaille', default_km: '10' }
  const [neu, setNeu] = useState(leer)
  const create = useMutation({
    mutationFn: () =>
      api.createCategory({
        name: neu.name,
        factor: parseFloat(neu.factor),
        color: neu.color,
        icon: neu.icon,
        default_km: parseFloat(neu.default_km),
      }),
    onSuccess: () => {
      setNeu(leer)
      refresh()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <Card>
      <H>Kategorien & Faktoren</H>
      <div className="space-y-2">
        {categories.map((c) => (
          <div
            key={c.id}
            className={`flex flex-wrap items-center gap-3 rounded-xl border border-line p-2 ${
              c.is_active ? '' : 'opacity-40'
            }`}
          >
            <Icon name={c.icon} size={20} className="text-accent" />
            <span className="min-w-24 flex-1 text-sm font-bold text-ink">{c.name}</span>
            <Input
              label="Faktor"
              type="number"
              step="0.5"
              defaultValue={c.factor}
              className="w-20"
              onBlur={(e) => {
                const factor = parseFloat(e.target.value)
                if (factor > 0 && factor !== c.factor) patch.mutate({ id: c.id, factor })
              }}
            />
            <Input
              label="Standard-km"
              type="number"
              step="1"
              min="1"
              defaultValue={c.default_km}
              className="w-24"
              onBlur={(e) => {
                const default_km = parseFloat(e.target.value)
                if (default_km > 0 && default_km !== c.default_km)
                  patch.mutate({ id: c.id, default_km })
              }}
            />
            <Button
              variant="ghost"
              onClick={() => patch.mutate({ id: c.id, is_active: !c.is_active })}
            >
              {c.is_active ? 'Deaktivieren' : 'Aktivieren'}
            </Button>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-3 rounded-xl border border-dashed border-line p-3">
        <div className="flex flex-wrap gap-2">
          <Input label="Name" value={neu.name} onChange={(e) => setNeu({ ...neu, name: e.target.value })} />
          <Input
            label="Faktor"
            type="number"
            step="0.5"
            className="w-20"
            value={neu.factor}
            onChange={(e) => setNeu({ ...neu, factor: e.target.value })}
          />
          <Input
            label="Standard-km"
            type="number"
            className="w-24"
            value={neu.default_km}
            onChange={(e) => setNeu({ ...neu, default_km: e.target.value })}
          />
          <label className="flex flex-col gap-1 text-xs font-semibold text-ink-mute">
            Farbe
            <input
              type="color"
              className="h-9 w-12 rounded-xl border border-line bg-surface"
              value={neu.color}
              onChange={(e) => setNeu({ ...neu, color: e.target.value })}
            />
          </label>
        </div>
        <IconPicker auswahl={SPORT_ICONS} value={neu.icon} onChange={(icon) => setNeu({ ...neu, icon })} />
        <Button
          disabled={!neu.name || !(parseFloat(neu.factor) > 0) || !(parseFloat(neu.default_km) > 0)}
          onClick={() => create.mutate()}
        >
          Kategorie anlegen
        </Button>
      </div>
    </Card>
  )
}

function Jahr() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season: Season | undefined = seasons.find((s) => s.year === new Date().getFullYear())
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['seasons'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const [goal, setGoal] = useState('')
  const [milestones, setMilestones] = useState<Milestone[] | null>(null)
  if (!season) return null
  const ms = milestones ?? season.milestones

  return (
    <Card>
      <H>Jahr {season.year}</H>
      <Input
        label="Ziel (gewertete km)"
        type="number"
        className="w-36"
        defaultValue={season.goal_km}
        onChange={(e) => setGoal(e.target.value)}
      />
      <h3 className="mt-4 mb-1 text-xs font-semibold text-ink-mute">Meilensteine</h3>
      <div className="space-y-2">
        {ms.map((m, i) => (
          <div key={i} className="flex flex-wrap items-end gap-2">
            <Input
              label="km"
              type="number"
              className="w-24"
              value={m.km}
              onChange={(e) =>
                setMilestones(ms.map((x, j) => (j === i ? { ...x, km: Number(e.target.value) } : x)))
              }
            />
            <Input
              label="Bezeichnung"
              className="flex-1"
              value={m.label}
              onChange={(e) =>
                setMilestones(ms.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))
              }
            />
            <IconPicker
              auswahl={MEILENSTEIN_ICONS}
              value={m.icon}
              onChange={(icon) => setMilestones(ms.map((x, j) => (j === i ? { ...x, icon } : x)))}
            />
            <button
              aria-label="Meilenstein entfernen"
              className="pb-2 text-ink-mute hover:text-danger"
              onClick={() => setMilestones(ms.filter((_, j) => j !== i))}
            >
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Button
          variant="ghost"
          onClick={() => setMilestones([...ms, { km: 0, label: '', icon: 'fahne' }])}
        >
          + Meilenstein
        </Button>
        <Button
          onClick={() =>
            api
              .patchSeason(season.id, { goal_km: goal ? parseFloat(goal) : undefined, milestones: ms })
              .then(refresh)
              .catch((e) => toast(e.message))
          }
        >
          Speichern
        </Button>
      </div>
      <h3 className="mt-4 mb-1 text-xs font-semibold text-ink-mute">Kartenbild (Aquarell)</h3>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="text-sm text-ink-mute"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) api.uploadMapImage(season.id, file).then(refresh).catch((err) => toast(err.message))
        }}
      />
      {season.map_image && <p className="mt-1 text-xs text-ink-mute">Aktuell: {season.map_image}</p>}
    </Card>
  )
}

function NeuerUser() {
  const toast = useToast()
  const leer = { username: '', password: '', display_name: '', avatar: 'icon:laufen' }
  const [form, setForm] = useState(leer)
  const create = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: (u) => {
      toast(`${u.display_name} angelegt`, 'ok')
      setForm(leer)
    },
    onError: (e) => toast(e.message),
  })
  return (
    <Card>
      <H>Neues Mitglied</H>
      <div className="flex flex-wrap gap-2">
        <Input
          label="Benutzername"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        />
        <Input
          label="Anzeigename"
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
        <Input
          label="Passwort"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
      </div>
      <div className="mt-3">
        <div className="mb-1 text-xs font-semibold text-ink-mute">Avatar</div>
        <AvatarWahl value={form.avatar} onChange={(avatar) => setForm({ ...form, avatar })} />
      </div>
      <Button
        className="mt-3"
        disabled={!form.username || form.password.length < 4 || !form.display_name}
        onClick={() => create.mutate()}
      >
        Anlegen
      </Button>
    </Card>
  )
}
```

- [ ] **Step 2: Grün + Commit**

Run: `cd frontend && npm test && npm run lint && npm run build`

```bash
git add frontend/src/pages/Admin.tsx
git commit -m "feat: admin-seite mit piktogramm-picker, standard-km und avatar-wahl"
```

---

### Task 14: Abschluss-Verifikation

- [ ] **Step 1: Beide Test-Suiten + Lint + Build**

```bash
cd backend && uv run pytest
cd ../frontend && npm test && npm run lint && npm run build
```

Expected: alles grün.

- [ ] **Step 2: App im Browser prüfen** (Backend `uv run uvicorn app.main:app --reload`, Frontend `npm run dev`):
  - Login dunkel mit Glow-Karte; Theme-Toggle wechselt hell/dunkel und überlebt Reload
  - Schnellwahl: Kategorie wechseln → km springt auf Standard; +/− min. 1; Details mit Datum/Dauer/Notiz; Eintrag erscheint in Liste
  - Profil-Modal: Avatar (Emoji + Piktogramm) speichern, erscheint in Nav
  - Admin: Kategorie mit Piktogramm + Standard-km anlegen; Meilenstein-Icons
  - Mobil (DevTools): Bottom-Bar sichtbar und bedienbar
  - Bestands-DB: `backend/data/meter.db` einmal mit altem Stand starten → Migration läuft ohne Fehler, Daten intakt

- [ ] **Step 3: Letzter Commit (falls Restdateien) — danach Branch fertig melden**

```bash
git status --short
git add -A backend/app backend/tests frontend/src frontend/public docs
git commit -m "chore: redesign plan 1 abgeschlossen"
```

---

## Nicht in diesem Plan (→ Plan 2)

Vergleichsseite inkl. kompakter Schnellwahl-Einbettung, RaceBahnen/WanderKarte/JahresVerlauf im Neon-Look, `userColor`-Palette. Die Vergleichs-Komponenten sind nach Task 7 nur kompiliersicher, aber noch alt gestylt — das ist gewollt.
