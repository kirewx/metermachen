import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import MeineAktivitaeten from './MeineAktivitaeten'

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#fff', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
    ]),
    activities: vi.fn().mockResolvedValue([
      { id: 1, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, note: null, scaled_km: 20, edited: false, source: 'strava' },
      { id: 2, category_id: 1, date: '2026-03-02', distance_km: 3, duration_min: null, note: null, scaled_km: 12, edited: false, source: 'manual' },
    ]),
  },
}))

vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MeineAktivitaeten />
    </QueryClientProvider>,
  )
}

describe('MeineAktivitaeten', () => {
  it('gruppiert nach Kategorie, default eingeklappt, klappt auf Klick auf', async () => {
    renderPage()
    expect(await screen.findByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText(/2 Einträge/)).toBeInTheDocument()
    expect(screen.getByText('32 km')).toBeInTheDocument()
    expect(screen.queryByText('Strava')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Laufen'))
    expect(await screen.findByText('Strava')).toBeInTheDocument()
  })

  it('zeigt genau ein Strava-Badge (nur für die Strava-Aktivität)', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    const badges = screen.getAllByText('Strava')
    expect(badges).toHaveLength(1)
  })
})
