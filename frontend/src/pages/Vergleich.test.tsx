import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { CURRENT_MONTH, monthKey, monthLabel } from '../components/comparison/period'
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
  // The server resolves 'current' to the season's default month.
  month: month === CURRENT_MONTH ? current : month,
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
    localStorage.clear()
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
    await waitFor(() => expect(api.comparison).toHaveBeenCalled())
    expect(screen.queryByLabelText('Saison')).toBeNull()
    expect(screen.queryByText(/Schnell/i)).toBeNull()
  })

  it('opens in month mode on the first visit and steps through months', async () => {
    renderPage()
    await screen.findByText(monthLabel(current))
    // One request: the server picks the default month, the season is not loaded on top.
    expect(api.comparison).toHaveBeenCalledTimes(1)
    expect(api.comparison).toHaveBeenCalledWith(thisYear, CURRENT_MONTH)
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear, months[0]))
  })

  it('shows a waiting month stepper while loading, not the season one', async () => {
    let resolve: (v: never) => void = () => {}
    vi.mocked(api.comparison).mockImplementation(
      () => new Promise<never>((r) => (resolve = r)),
    )
    renderPage()
    const pill = await screen.findByRole('button', { name: 'Monat' })
    await waitFor(() => expect(api.comparison).toHaveBeenCalled())
    expect(pill).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Vorherige Saison' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Vorheriger Monat' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächster Monat' })).toBeDisabled()
    resolve(comparison(CURRENT_MONTH) as never)
    expect(await screen.findByText(monthLabel(current))).toBeInTheDocument()
  })

  it('does not keep another season on screen while a month loads', async () => {
    vi.mocked(api.seasons).mockResolvedValue([
      { id: 1, year: thisYear - 1, goal_km: 1000, milestones: [], start_date: null, end_date: `${thisYear - 1}-12-31` },
      { id: 2, year: thisYear, goal_km: 1000, milestones: [], start_date: null, end_date: null },
    ])
    const user = { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 42, total_real_km: 42, km_factor: 1, by_category: [], segments: [], cumulative: [] }
    let resolveOld: (v: never) => void = () => {}
    vi.mocked(api.comparison).mockImplementation((y: number, m?: string) =>
      y === thisYear
        ? Promise.resolve({ ...comparison(m ?? null), users: [user] } as never)
        : m === undefined
          ? Promise.resolve({ ...comparison(null), year: y, users: [] } as never)
          : new Promise<never>((r) => (resolveOld = r)),
    )
    renderPage()
    await screen.findByLabelText('Profil von Erik')
    fireEvent.click(screen.getByRole('button', { name: 'Jahr' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Vorherige Saison' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Monat' })).toBeEnabled())
    expect(api.comparison).toHaveBeenCalledWith(thisYear - 1)
    fireEvent.click(screen.getByRole('button', { name: 'Monat' }))
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear - 1, CURRENT_MONTH))
    // The old season's month is still pending: this season's numbers must be gone.
    expect(screen.queryByLabelText('Profil von Erik')).toBeNull()
    resolveOld({ ...comparison(null), year: thisYear - 1, month: months[0], users: [] } as never)
  })

  it('remembers the chosen mode in the browser', async () => {
    const first = renderPage()
    await screen.findByText(monthLabel(current))
    fireEvent.click(screen.getByRole('button', { name: 'Jahr' }))
    expect(localStorage.getItem('mm_period_mode')).toBe('year')
    first.unmount()
    vi.mocked(api.comparison).mockClear()
    renderPage()
    await screen.findByRole('button', { name: 'Vorherige Saison' })
    expect(screen.queryByText(monthLabel(current))).toBeNull()
    expect(api.comparison).not.toHaveBeenCalledWith(thisYear, CURRENT_MONTH)
  })

  it('remembers the last view tab in the browser', async () => {
    const first = renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Höhenmeter/ }))
    expect(localStorage.getItem('mm_vergleich_view')).toBe('hoehenmeter')
    first.unmount()
    renderPage()
    // Höhenmeter is year-only: no Monat pill means the stored tab was restored.
    await screen.findByRole('button', { name: 'Vorherige Saison' })
    expect(screen.queryByRole('button', { name: 'Monat' })).toBeNull()
  })

  it('ignores an unknown stored view', async () => {
    localStorage.setItem('mm_vergleich_view', 'quatsch')
    renderPage()
    expect(await screen.findByRole('button', { name: 'Monat' })).toBeInTheDocument()
  })

  it('falls back to the season while it has no months', async () => {
    vi.mocked(api.comparison).mockImplementation(() =>
      Promise.resolve({ ...comparison(null), months: [] } as never),
    )
    renderPage()
    const pill = await screen.findByRole('button', { name: 'Monat' })
    await waitFor(() => expect(pill).toBeDisabled())
    expect(screen.getByRole('button', { name: 'Vorherige Saison' })).toBeInTheDocument()
  })

  it('keeps month mode on Verlauf', async () => {
    renderPage()
    const pill = await screen.findByRole('button', { name: 'Monat' })
    await waitFor(() => expect(pill).toBeEnabled())
    fireEvent.click(pill)
    fireEvent.click(screen.getByRole('button', { name: /Verlauf/ }))
    expect(screen.getByRole('button', { name: 'Monat' })).toBeInTheDocument()
    expect(screen.getByText(monthLabel(current))).toBeInTheDocument()
  })

  it('hides the Monat pill on Höhenmeter and restores month mode on return', async () => {
    renderPage()
    const pill = await screen.findByRole('button', { name: 'Monat' })
    await waitFor(() => expect(pill).toBeEnabled())
    fireEvent.click(pill)
    fireEvent.click(screen.getByRole('button', { name: /Höhenmeter/ }))
    expect(screen.queryByRole('button', { name: 'Monat' })).toBeNull()
    expect(screen.queryByText(monthLabel(current))).toBeNull()
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
