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
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear))
    expect(screen.queryByLabelText('Saison')).toBeNull()
    expect(screen.queryByText(/Schnell/i)).toBeNull()
  })

  it('opens in month mode on the first visit and steps through months', async () => {
    renderPage()
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear, current))
    expect(screen.getByText(monthLabel(current))).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    await waitFor(() => expect(api.comparison).toHaveBeenCalledWith(thisYear, months[0]))
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
    expect(api.comparison).not.toHaveBeenCalledWith(thisYear, current)
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
      Promise.resolve({ ...comparison(null), months: [], elevation_months: [] } as never),
    )
    renderPage()
    expect(await screen.findByRole('button', { name: 'Monat' })).toBeDisabled()
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
