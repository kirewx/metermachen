# Vergleich Month Race Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Monat/Jahr toggle with a month stepper to the Vergleich page (Rennen and Sport-Mix), backed by a `month` query param on the comparison endpoint, and remove the quick-entry bar.

**Architecture:** `compute_comparison` gets an optional `month` filter applied after the season filters; the response echoes `month` and exposes the season's `months` axis. The frontend adds a presentational `PeriodControl` plus pure helpers in `period.ts`; `Vergleich` owns the state and queries `['comparison', year]` (year) or `['comparison', year, month]` (month). `RaceBahnen` switches to a goal-less, leader-scaled race when `data.month` is set.

**Tech Stack:** FastAPI + SQLModel + pytest (backend, run with `backend/.venv/Scripts/python.exe`), React + TanStack Query + Tailwind + Vitest/RTL (frontend).

**Spec:** `docs/superpowers/specs/2026-09-19-vergleich-month-race-design.md`

**Environment gotchas:** no `python` on PATH, use `backend/.venv/Scripts/python.exe -m pytest` from `backend/`. Bash heredocs mangle quotes on this machine; create files with the Write tool. Pre-existing ESLint errors in `Feed.tsx`/`ReactionBar.tsx` are not ours. UI copy is German, everything else English.

---

## File structure

| File | Responsibility |
| --- | --- |
| `backend/app/routers/comparison.py` | month filter, validation, `month`/`months` in the response |
| `backend/app/schemas.py` | `ComparisonOut.month`, `ComparisonOut.months` |
| `backend/tests/test_comparison.py` | month tests |
| `frontend/src/api/client.ts` | `api.comparison(year, month?)`, type fields |
| `frontend/src/components/comparison/period.ts` | pure month helpers |
| `frontend/src/components/comparison/PeriodControl.tsx` | Monat/Jahr pill + stepper + Endstand tag |
| `frontend/src/components/comparison/RaceBahnen.tsx` | month mode, rank "–" at zero |
| `frontend/src/pages/Vergleich.tsx` | state, queries, archive link, no quick-entry bar |
| `frontend/src/components/activities/SchnellwahlLeiste.tsx` (+ test) | deleted |

---

### Task 1: Backend month param

**Files:**
- Modify: `backend/app/schemas.py` (`ComparisonOut`)
- Modify: `backend/app/routers/comparison.py`
- Test: `backend/tests/test_comparison.py`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_comparison.py`)

```python
def _sept_lisa(session, lisa):
    """Lisa overtakes Erik in September only (year: Erik 30, Lisa 35)."""
    from sqlmodel import select

    from app.models import Category

    cat = session.exec(select(Category)).first()
    session.add(Activity(user_id=lisa.id, category_id=cat.id,
                         date=date(2026, 9, 10), distance_km=25))
    session.commit()


def test_month_filter_totals_and_ranks(client, session):
    _, lisa = _hm_setup(session)
    _sept_lisa(session, lisa)
    login(client)
    body = client.get("/api/comparison/2026?month=2026-09").json()
    assert body["month"] == "2026-09"
    assert [(u["display_name"], u["total_scaled_km"], u["rank"]) for u in body["users"]] == [
        ("Lisa", 25.0, 1),
        ("Erik", 10.0, 2),
    ]
    erik = body["users"][1]
    assert erik["total_elevation_m"] == 450.0
    assert [s["date"] for s in erik["segments"]] == ["2026-09-02"]
    assert [p["scaled_km"] for p in erik["cumulative"]] == [10.0]
    assert [b["scaled_km"] for b in erik["by_category"]] == [10.0]
    july = client.get("/api/comparison/2026?month=2026-07").json()
    assert [(u["display_name"], u["total_scaled_km"]) for u in july["users"]] == [
        ("Erik", 20.0),
        ("Lisa", 10.0),
    ]


def test_month_partial_first_month_respects_start(client, session):
    user = make_user(session)
    cat = make_category(session, factor=1.0)
    session.add(Season(year=2026, goal_km=1000, milestones_json="[]",
                       start_date=date(2026, 7, 10), end_date=date(2026, 12, 31)))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 7, 5), distance_km=10))  # before the start
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 7, 12), distance_km=7))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 3), distance_km=3))  # other month
    session.commit()
    login(client)
    body = client.get("/api/comparison/2026?month=2026-07").json()
    assert body["users"][0]["total_scaled_km"] == 7.0


def test_months_axis_with_and_without_month(client, session):
    _hm_setup(session)
    login(client)
    year = client.get("/api/comparison/2026").json()
    assert year["month"] is None
    assert year["months"] == year["elevation_months"]
    assert year["months"][:3] == ["2026-07", "2026-08", "2026-09"]
    month = client.get("/api/comparison/2026?month=2026-08").json()
    assert month["months"] == year["months"]  # axis ignores the month filter
    assert all(u["total_scaled_km"] == 0 for u in month["users"])  # empty month lists everyone


def test_month_malformed_is_422(client, session):
    _hm_setup(session)
    login(client)
    assert client.get("/api/comparison/2026?month=2026-13").status_code == 422
    assert client.get("/api/comparison/2026?month=september").status_code == 422


def test_month_outside_season_is_404(client, session):
    _hm_setup(session)
    login(client)
    r = client.get("/api/comparison/2026?month=2026-05")
    assert r.status_code == 404
    assert r.json()["detail"] == "Monat liegt nicht in der Saison"


def test_month_with_warmup_is_422(client, session):
    _hm_setup(session)
    login(client)
    r = client.get("/api/comparison/2026?phase=warmup&month=2026-07")
    assert r.status_code == 422


def test_month_uses_factor_by_date(client, session):
    from app.models import CategoryFactorChange

    user = make_user(session)
    cat = make_category(session, name="Schwimmen", factor=30.0)
    session.add(Season(year=2026, goal_km=1000, milestones_json="[]",
                       start_date=date(2026, 7, 1), end_date=date(2026, 12, 31)))
    session.add(CategoryFactorChange(category_id=cat.id, factor=25.0,
                                     valid_from=date(2026, 9, 1)))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 31), distance_km=2))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 9, 1), distance_km=2))
    session.commit()
    login(client)
    aug = client.get("/api/comparison/2026?month=2026-08").json()["users"][0]
    sep = client.get("/api/comparison/2026?month=2026-09").json()["users"][0]
    assert aug["total_scaled_km"] == 60.0
    assert sep["total_scaled_km"] == 50.0
```

- [ ] **Step 2: Run to verify they fail**

Run (from `backend/`): `.venv/Scripts/python.exe -m pytest tests/test_comparison.py -k "month" -q`
Expected: 7 failed (KeyError `month`, wrong totals, 200 instead of 422/404).

- [ ] **Step 3: Implement**

`backend/app/schemas.py`, `ComparisonOut`, after `elevation_months`:

```python
    month: str | None = None
    months: list[str] = []
```

`backend/app/routers/comparison.py`:

1. Import `Query` from fastapi.
2. Below `router = ...`:

```python
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
```

3. Signature: `def compute_comparison(session, year, phase="challenge", month: str | None = None)`. Right after the season 404:

```python
    if month is not None and phase == "warmup":
        raise HTTPException(status_code=422, detail="Monatsansicht gibt es nur für die Saison")
```

4. Move the `by_user` grouping block from before the emoji query to after the `elevation_months` computation, preceded by the month filter:

```python
    # The month axis above is built from the whole season; the month filter only
    # narrows what is aggregated per user.
    if month is not None:
        if month not in elevation_months:
            raise HTTPException(status_code=404, detail="Monat liegt nicht in der Saison")
        rows = [(a, c) for a, c in rows if _monatsschluessel(a.date) == month]

    by_user: dict[int, list[tuple[Activity, Category]]] = defaultdict(list)
    for a, c in rows:
        by_user[a.user_id].append((a, c))
```

5. Return: add `month=month, months=elevation_months`.
6. Endpoint:

```python
def comparison(
    year: int,
    phase: Literal["challenge", "warmup"] = "challenge",
    month: str | None = Query(default=None, pattern=MONTH_PATTERN),
    session: Session = Depends(get_session),
):
    return compute_comparison(session, year, phase, month)
```

- [ ] **Step 4: Run the whole backend suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/comparison.py backend/tests/test_comparison.py
git commit -m "feat(comparison): month query param with season month axis"
```

---

### Task 2: API client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Extend the type and the method**

`Comparison` gains, after `elevation_months`:

```ts
  /** Requested month ('YYYY-MM') or null for the whole season. */
  month: string | null
  /** Month axis of the season, 'YYYY-MM' each; drives the month stepper. */
  months: string[]
```

Replace `comparison`:

```ts
  comparison: (year: number, month?: string) =>
    request<Comparison>(`/api/comparison/${year}${month ? `?month=${month}` : ''}`),
```

- [ ] **Step 2: Type-check**

Run (from `frontend/`): `npx tsc -b`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(api): comparison month param and month axis type"
```

---

### Task 3: period helpers

**Files:**
- Create: `frontend/src/components/comparison/period.ts`
- Test: `frontend/src/components/comparison/period.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from 'vitest'
import { defaultMonth, isFinishedMonth, monthKey, monthLabel } from './period'

const today = new Date(2026, 8, 19) // 19 Sep 2026

describe('period helpers', () => {
  it('monthKey formats a date as YYYY-MM', () => {
    expect(monthKey(today)).toBe('2026-09')
    expect(monthKey(new Date(2027, 0, 1))).toBe('2027-01')
  })

  it('defaultMonth prefers the current month', () => {
    expect(defaultMonth(['2026-07', '2026-08', '2026-09'], today)).toBe('2026-09')
  })

  it('defaultMonth falls back to the last month of a past season', () => {
    expect(defaultMonth(['2025-07', '2025-08'], today)).toBe('2025-08')
  })

  it('defaultMonth is null without months', () => {
    expect(defaultMonth([], today)).toBeNull()
  })

  it('monthLabel uses German short names', () => {
    expect(monthLabel('2026-09')).toBe('Sep 2026')
    expect(monthLabel('2027-03')).toBe('Mär 2027')
  })

  it('isFinishedMonth is true only for months before the current one', () => {
    expect(isFinishedMonth('2026-08', today)).toBe(true)
    expect(isFinishedMonth('2026-09', today)).toBe(false)
    expect(isFinishedMonth('2026-10', today)).toBe(false)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/components/comparison/period.test.ts`
Expected: FAIL, cannot resolve `./period`.

- [ ] **Step 3: Implement `period.ts`**

```ts
export type PeriodMode = 'month' | 'year'

const MONTHS_SHORT = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']

/** 'YYYY-MM' key of a local date, same format as the backend month axis. */
export function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** Month to show when entering month mode: the current one if the season has it, else the last. */
export function defaultMonth(months: string[], today: Date): string | null {
  if (months.length === 0) return null
  const current = monthKey(today)
  return months.includes(current) ? current : months[months.length - 1]
}

export function monthLabel(key: string): string {
  const [year, month] = key.split('-')
  return `${MONTHS_SHORT[Number(month) - 1]} ${year}`
}

/** Keys sort lexicographically, so a plain string compare is enough. */
export function isFinishedMonth(key: string, today: Date): boolean {
  return key < monthKey(today)
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npx vitest run src/components/comparison/period.test.ts`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/period.ts frontend/src/components/comparison/period.test.ts
git commit -m "feat(vergleich): month period helpers"
```

---

### Task 4: PeriodControl

**Files:**
- Create: `frontend/src/components/comparison/PeriodControl.tsx`
- Test: `frontend/src/components/comparison/PeriodControl.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PeriodControl from './PeriodControl'

const years = [
  { year: 2025, label: '2025' },
  { year: 2026, label: '2026/27' },
]
const months = ['2026-07', '2026-08', '2026-09']
const today = new Date(2026, 8, 19)

function setup(props: Partial<Parameters<typeof PeriodControl>[0]> = {}) {
  const handlers = { onModeChange: vi.fn(), onYearChange: vi.fn(), onMonthChange: vi.fn() }
  render(
    <PeriodControl
      mode="year"
      showModeToggle
      years={years}
      year={2026}
      months={months}
      month={null}
      today={today}
      {...handlers}
      {...props}
    />,
  )
  return handlers
}

describe('PeriodControl', () => {
  it('switches the mode through the pill', () => {
    const h = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Monat' }))
    expect(h.onModeChange).toHaveBeenCalledWith('month')
  })

  it('steps through seasons in year mode and disables the last end', () => {
    const h = setup()
    expect(screen.getByText('2026/27')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nächste Saison' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Vorherige Saison' }))
    expect(h.onYearChange).toHaveBeenCalledWith(2025)
  })

  it('steps through months in month mode', () => {
    const h = setup({ mode: 'month', month: '2026-08' })
    expect(screen.getByText('Aug 2026')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    expect(h.onMonthChange).toHaveBeenCalledWith('2026-07')
    fireEvent.click(screen.getByRole('button', { name: 'Nächster Monat' }))
    expect(h.onMonthChange).toHaveBeenCalledWith('2026-09')
  })

  it('disables the arrows at the month ends', () => {
    setup({ mode: 'month', month: '2026-07' })
    expect(screen.getByRole('button', { name: 'Vorheriger Monat' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächster Monat' })).toBeEnabled()
  })

  it('tags finished months with Endstand, not the running one', () => {
    setup({ mode: 'month', month: '2026-08' })
    expect(screen.getByText('Endstand')).toBeInTheDocument()
  })

  it('shows no Endstand for the current month', () => {
    setup({ mode: 'month', month: '2026-09' })
    expect(screen.queryByText('Endstand')).toBeNull()
  })

  it('hides the pill and shows the season when the toggle is off', () => {
    setup({ mode: 'month', month: '2026-08', showModeToggle: false })
    expect(screen.queryByRole('button', { name: 'Monat' })).toBeNull()
    expect(screen.getByText('2026/27')).toBeInTheDocument()
  })

  it('disables the Monat pill without a month axis', () => {
    setup({ months: [] })
    expect(screen.getByRole('button', { name: 'Monat' })).toBeDisabled()
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/components/comparison/PeriodControl.test.tsx`
Expected: FAIL, cannot resolve `./PeriodControl`.

- [ ] **Step 3: Implement `PeriodControl.tsx`**

```tsx
import { isFinishedMonth, monthLabel, type PeriodMode } from './period'

type Props = {
  mode: PeriodMode
  /** Only Rennen and Sport-Mix can be viewed per month. */
  showModeToggle: boolean
  /** Seasons in ascending order. */
  years: { year: number; label: string }[]
  year: number
  months: string[]
  month: string | null
  today?: Date
  onModeChange: (mode: PeriodMode) => void
  onYearChange: (year: number) => void
  onMonthChange: (month: string) => void
}

const PILLS: { key: PeriodMode; label: string }[] = [
  { key: 'month', label: 'Monat' },
  { key: 'year', label: 'Jahr' },
]

export default function PeriodControl({
  mode,
  showModeToggle,
  years,
  year,
  months,
  month,
  today = new Date(),
  onModeChange,
  onYearChange,
  onMonthChange,
}: Props) {
  const monthly = showModeToggle && mode === 'month' && month !== null
  const index = monthly ? months.indexOf(month) : years.findIndex((y) => y.year === year)
  const count = monthly ? months.length : years.length
  const label = monthly ? monthLabel(month) : (years[index]?.label ?? String(year))
  const step = (delta: number) => {
    const next = index + delta
    if (index < 0 || next < 0 || next >= count) return
    if (monthly) onMonthChange(months[next])
    else onYearChange(years[next].year)
  }
  const arrow =
    'grid h-7 w-7 place-items-center rounded-full border border-line text-accent transition hover:bg-accent/10 disabled:opacity-30 disabled:hover:bg-transparent'

  return (
    <div className="flex flex-wrap items-center gap-2">
      {showModeToggle && (
        <div className="flex overflow-hidden rounded-full border border-line text-xs">
          {PILLS.map((p) => (
            <button
              key={p.key}
              type="button"
              disabled={p.key === 'month' && months.length === 0}
              onClick={() => {
                if (mode !== p.key) onModeChange(p.key)
              }}
              className={`px-3 py-1 font-bold transition disabled:opacity-40 ${
                mode === p.key ? 'bg-accent text-accent-ink' : 'text-ink-mute hover:text-ink'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          aria-label={monthly ? 'Vorheriger Monat' : 'Vorherige Saison'}
          disabled={index <= 0}
          onClick={() => step(-1)}
          className={arrow}
        >
          ‹
        </button>
        <span className="min-w-[4.5rem] text-center text-sm font-bold tabular-nums text-ink">
          {label}
        </span>
        <button
          type="button"
          aria-label={monthly ? 'Nächster Monat' : 'Nächste Saison'}
          disabled={index < 0 || index >= count - 1}
          onClick={() => step(1)}
          className={arrow}
        >
          ›
        </button>
      </div>
      {monthly && isFinishedMonth(month, today) && (
        <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-mute">
          Endstand
        </span>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npx vitest run src/components/comparison/PeriodControl.test.tsx`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/PeriodControl.tsx frontend/src/components/comparison/PeriodControl.test.tsx
git commit -m "feat(vergleich): PeriodControl with Monat/Jahr pill and stepper"
```

---

### Task 5: RaceBahnen month mode and zero rank

**Files:**
- Modify: `frontend/src/components/comparison/RaceBahnen.tsx`
- Test: `frontend/src/components/comparison/RaceBahnen.test.tsx`

- [ ] **Step 1: Write the failing tests**

In `RaceBahnen.test.tsx`: import `api` (`import { api } from '../../api/client'`) and `waitFor`, leave the existing fixture untouched, let `renderRace` take the data (`function renderRace(mode?: 'mm' | 'km', d: Comparison = data)` and render `<RaceBahnen data={d} mode={mode} />`), then append:

```tsx
describe('RaceBahnen Monatsmodus', () => {
  const monthData = {
    ...data,
    month: '2026-09',
    milestones: [{ km: 500, icon: 'berg', label: 'Halbzeit' }],
  } as Comparison

  it('zeigt weder Ziel noch Meilensteine', () => {
    renderRace('mm', monthData)
    expect(screen.queryByText('1000')).toBeNull()
    expect(screen.queryByText('500')).toBeNull()
  })

  it('zeigt im Jahresmodus Ziel und Meilensteine', () => {
    renderRace('mm', { ...monthData, month: null } as Comparison)
    expect(screen.getByText('1000')).toBeInTheDocument()
    expect(screen.getByText('500')).toBeInTheDocument()
  })

  it('zeigt kein Seit-Besuch-Banner und markiert nichts als gesehen', async () => {
    vi.mocked(api.lastSeenComparison).mockClear()
    renderRace('mm', monthData)
    await waitFor(() => expect(screen.getByText('300')).toBeInTheDocument())
    expect(screen.queryByText(/Seit deinem letzten Besuch/)).toBeNull()
    expect(api.lastSeenComparison).not.toHaveBeenCalled()
  })

  it('zeigt Rang – für Personen ohne Meter', () => {
    const zero = {
      ...monthData,
      users: monthData.users.map((u) => ({ ...u, total_scaled_km: 0, total_real_km: 0 })),
    } as Comparison
    renderRace('mm', zero)
    expect(screen.getAllByText('–')).toHaveLength(2)
    expect(screen.queryByText('1')).toBeNull()
  })
})
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run src/components/comparison/RaceBahnen.test.tsx`
Expected: the new month tests fail (goal 1000 rendered, banner query called, rank 1 shown); the year test passes.

- [ ] **Step 3: Implement**

In `RaceBahnen.tsx`:

```tsx
  const monthly = data.month != null
  const { data: lastSeen } = useQuery({
    queryKey: ['comparison-last-seen', data.year],
    queryFn: () => api.lastSeenComparison(data.year),
    // Since-last-seen is a season feature; a month race has no snapshot.
    enabled: !monthly,
  })
  ...
  const since = computeSinceLastSeen(data.users, monthly ? null : (lastSeen ?? null), nowMs)
  ...
  const milestones = monthly ? [] : data.milestones
  // Month race has no goal: the leader sets the scale.
  const maxKm = Math.max(monthly ? 1 : data.goal_km, ...data.users.map((u) => u.total_scaled_km))
```

Replace both `data.milestones.map` with `milestones.map`, wrap the goal flag `<span>` in `{!monthly && (...)}`, and per user:

```tsx
          const hasMeters = u.total_scaled_km > 0
          const fuehrt = u.rank === 1 && hasMeters
          ...
                  {hasMeters ? u.rank : '–'}
```

`computeSinceLastSeen` with `null` returns an inactive result (as today before the query resolves), so the banner, the animation and the `markComparisonSeen` effect all stay off.

- [ ] **Step 4: Run to verify it passes**

Run: `npx vitest run src/components/comparison/RaceBahnen.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/comparison/RaceBahnen.tsx frontend/src/components/comparison/RaceBahnen.test.tsx
git commit -m "feat(vergleich): goal-less month race, rank dash at zero"
```

---

### Task 6: Vergleich page

**Files:**
- Modify: `frontend/src/pages/Vergleich.tsx`
- Create: `frontend/src/pages/Vergleich.test.tsx`
- Delete: `frontend/src/components/activities/SchnellwahlLeiste.tsx`, `frontend/src/components/activities/SchnellwahlLeiste.test.tsx`

- [ ] **Step 1: Write the failing test** (`Vergleich.test.tsx`)

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { monthKey, monthLabel } from '../components/comparison/period'
import { ToastProvider } from '../components/ui/Toast'
import Vergleich from './Vergleich'

const thisYear = new Date().getFullYear()
const current = monthKey(new Date())
const months = [`${thisYear - 1}-12`, current]

const comparison = (month: string | null) => ({
  year: thisYear,
  goal_km: 1000,
  milestones: [],
  users: [],
  start_date: null,
  phase: 'challenge',
  elevation_months: months,
  month,
  months,
})

vi.mock('../api/client', () => ({
  api: {
    seasons: vi.fn(),
    comparison: vi.fn(),
    lastSeenComparison: vi.fn().mockResolvedValue(null),
    markComparisonSeen: vi.fn(),
  },
}))
vi.mock('../components/comparison/WarmupArchiv', () => ({
  default: () => <p>Warmup-Inhalt</p>,
}))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter>
          <Vergleich />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  )
}

describe('Vergleich', () => {
  beforeEach(() => {
    vi.mocked(api.seasons).mockResolvedValue([
      { id: 1, year: thisYear, goal_km: 1000, milestones: [], start_date: null, end_date: null },
    ])
    vi.mocked(api.comparison).mockReset()
    vi.mocked(api.comparison).mockImplementation((_y: number, m?: string) =>
      Promise.resolve(comparison(m ?? null) as never),
    )
  })

  it('has no quick-entry bar and no Saison select', async () => {
    renderPage()
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear, undefined))
    expect(screen.queryByLabelText('Saison')).toBeNull()
    expect(screen.queryByText(/Schnell/i)).toBeNull()
  })

  it('requests the current month after switching to Monat', async () => {
    renderPage()
    const pill = await screen.findByRole('button', { name: 'Monat' })
    await waitFor(() => expect(pill).toBeEnabled())
    fireEvent.click(pill)
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear, current))
    expect(screen.getByText(monthLabel(current))).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear, months[0]))
  })

  it('hides the Monat pill on Verlauf and restores month mode on return', async () => {
    renderPage()
    const pill = await screen.findByRole('button', { name: 'Monat' })
    await waitFor(() => expect(pill).toBeEnabled())
    fireEvent.click(pill)
    fireEvent.click(screen.getByRole('button', { name: /Verlauf/ }))
    expect(screen.queryByRole('button', { name: 'Monat' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Rennen/ }))
    expect(screen.getByText(monthLabel(current))).toBeInTheDocument()
  })

  it('opens and closes the warm-up archive through links', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Warm-up-Archiv' }))
    expect(screen.getByText('Warmup-Inhalt')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Monat' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Zurück zum Vergleich' }))
    expect(screen.queryByText('Warmup-Inhalt')).toBeNull()
  })
})
```

If `ToastProvider` is not the export name in `components/ui/Toast`, use the provider that file exports (check with `grep -n "export" frontend/src/components/ui/Toast.tsx`).

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/pages/Vergleich.test.tsx`
Expected: FAIL (Saison select present, no Monat pill, no archive link).

- [ ] **Step 3: Implement `Vergleich.tsx`**

Remove the `SchnellwahlLeiste` and `Select` imports; add:

```tsx
import PeriodControl from '../components/comparison/PeriodControl'
import { defaultMonth, type PeriodMode } from '../components/comparison/period'
```

Replace the component body:

```tsx
const MONTH_VIEWS: Ansicht[] = ['rennen', 'sportmix']

export default function Vergleich() {
  const [ansicht, setAnsicht] = useState<Ansicht>('rennen')
  const { mode, toggle: toggleUnit } = useUnitMode()
  useStravaRedirectHinweis()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [gewaehlt, setGewaehlt] = useState<number | null>(null)
  const [archiv, setArchiv] = useState(false)
  const [period, setPeriod] = useState<PeriodMode>('year')
  const [month, setMonth] = useState<string | null>(null)
  const aktive = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const year = gewaehlt ?? aktive
  // The season query is always loaded: it carries the month axis for the stepper.
  const seasonQuery = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
    enabled: !archiv,
  })
  const months = seasonQuery.data?.months ?? []
  const monthly = period === 'month' && MONTH_VIEWS.includes(ansicht) && month !== null
  const monthQuery = useQuery({
    queryKey: ['comparison', year, month],
    queryFn: () => api.comparison(year, month ?? undefined),
    enabled: !archiv && monthly,
  })
  const { data, error } = monthly ? monthQuery : seasonQuery
  const years = [...seasons]
    .sort((a, b) => a.year - b.year)
    .map((s) => ({ year: s.year, label: saisonLabel(s) }))

  const changeMode = (next: PeriodMode) => {
    setPeriod(next)
    if (next === 'month') setMonth(defaultMonth(months, new Date()))
  }
  const changeYear = (next: number) => {
    setGewaehlt(next)
    // Months belong to one season; the effect below picks the new default.
    setMonth(null)
  }
  useEffect(() => {
    if (period === 'month' && month === null && months.length > 0) {
      setMonth(defaultMonth(months, new Date()))
    }
  }, [period, month, months])
```

JSX: drop `<SchnellwahlLeiste />`; when `archiv`, render only

```tsx
      <button type="button" onClick={() => setArchiv(false)}
        className="text-sm text-ink-mute underline hover:text-ink">
        Zurück zum Vergleich
      </button>
      <WarmupArchiv year={aktive} />
```

otherwise row 1 = the view tabs (unchanged buttons, in their own `flex flex-wrap` div), row 2:

```tsx
      <div className="flex flex-wrap items-center gap-2">
        <PeriodControl
          mode={period}
          showModeToggle={MONTH_VIEWS.includes(ansicht)}
          years={years}
          year={year}
          months={months}
          month={month}
          onModeChange={changeMode}
          onYearChange={changeYear}
          onMonthChange={setMonth}
        />
        {ansicht !== 'hoehenmeter' && ( /* existing MM/km pill, with ml-auto */ )}
      </div>
```

then the error line and the four views as today (without the `!archiv` guards), and at the bottom:

```tsx
      <div className="pt-2 text-center">
        <button type="button" onClick={() => setArchiv(true)}
          className="text-xs text-ink-mute underline hover:text-ink">
          Warm-up-Archiv
        </button>
      </div>
```

If the `react-hooks/set-state-in-effect` lint rule rejects the effect, derive instead: keep `month` as the user's explicit choice and compute `const shownMonth = month ?? defaultMonth(months, today)` with a `today` frozen via `useState(() => new Date())`, using `shownMonth` everywhere `month` is read.

- [ ] **Step 4: Delete the quick-entry bar**

```bash
git rm frontend/src/components/activities/SchnellwahlLeiste.tsx frontend/src/components/activities/SchnellwahlLeiste.test.tsx
```

Then `grep -rn "SchnellwahlLeiste" frontend/src` must return nothing.

- [ ] **Step 5: Run to verify it passes**

Run: `npx vitest run src/pages/Vergleich.test.tsx`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src
git commit -m "feat(vergleich): Monat/Jahr period row, archive link, quick-entry bar removed"
```

---

### Task 7: Full verification and PR

- [ ] **Step 1:** `cd frontend && npm test` — all pass.
- [ ] **Step 2:** `npm run lint` — no new errors (pre-existing ones in `Feed.tsx`/`ReactionBar.tsx` are known).
- [ ] **Step 3:** `npx tsc -b` — clean.
- [ ] **Step 4:** `cd ../backend && .venv/Scripts/python.exe -m pytest -q` — all pass.
- [ ] **Step 5:** Start backend and frontend locally, open Vergleich, check year mode, month mode, stepping, Sport-Mix per month, Verlauf without pill, archive link.
- [ ] **Step 6:** `git push -u origin feature/vergleich-month-race` and open the PR with `gh pr create`.
