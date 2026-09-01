import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MyMeters from './MyMeters'

vi.mock('../api/client', () => ({
  api: {
    seasons: vi.fn().mockResolvedValue([]),
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#fff', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
    ]),
    activities: vi.fn().mockResolvedValue([
      { id: 1, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, elevation_m: 340, note: null, scaled_km: 20, edited: false, source: 'strava', strava_url: 'https://www.strava.com/activities/1' },
      { id: 2, category_id: 1, date: '2026-03-02', distance_km: 3, duration_min: null, elevation_m: null, note: null, scaled_km: 12, edited: false, source: 'manual', strava_url: null },
    ]),
  },
}))

vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MyMeters />
    </QueryClientProvider>,
  )
}

describe('MyMeters', () => {
  it('groups by category, collapsed by default, expands on click', async () => {
    renderPage()
    expect(await screen.findByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText(/2 Einträge/)).toBeInTheDocument()
    expect(screen.getByText('32 km')).toBeInTheDocument()
    expect(screen.queryByText(/Strava/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Laufen'))
    expect(await screen.findByText('View on Strava')).toBeInTheDocument()
  })

  it('links the Strava badge to the activity and shows elevation', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    const link = await screen.findByText('View on Strava')
    expect(link).toHaveAttribute('href', 'https://www.strava.com/activities/1')
    expect(screen.getByText(/340 hm/)).toBeInTheDocument()
    // Only the one Strava activity carries a badge.
    expect(screen.getAllByText('View on Strava')).toHaveLength(1)
  })

  it('has no achievements block any more', async () => {
    renderPage()
    await screen.findByText('Laufen')
    expect(screen.queryByText('Achievements')).not.toBeInTheDocument()
  })
})
