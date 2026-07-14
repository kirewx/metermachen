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
      { id: 1, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, elevation_m: 340, note: null, scaled_km: 20, edited: false, source: 'strava', strava_url: 'https://www.strava.com/activities/1' },
      { id: 2, category_id: 1, date: '2026-03-02', distance_km: 3, duration_min: null, elevation_m: null, note: null, scaled_km: 12, edited: false, source: 'manual', strava_url: null },
    ]),
    achievements: vi.fn().mockResolvedValue([
      {
        key: 'startschuss', title: 'Startschuss', description: 'Deine erste Aktivität ist im Kasten.',
        icon: 'fahne', achieved: true, progress: 1,
        parts: [{ label: 'Gesamt', current_km: 0.01, target_km: 0.01 }],
      },
      {
        key: 'ironman', title: 'Ironman', description: '190 km Rad, 42 km Laufen und 4 km Schwimmen — die volle Distanz.',
        icon: 'pokal', achieved: false, progress: 0.5,
        parts: [
          { label: 'Rad', current_km: 95, target_km: 190 },
          { label: 'Laufen', current_km: 30, target_km: 42 },
          { label: 'Schwimmen', current_km: 2, target_km: 4 },
        ],
      },
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
    expect(screen.queryByText(/Strava/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Laufen'))
    expect(await screen.findByText('Strava ↗')).toBeInTheDocument()
  })

  it('verlinkt das Strava-Badge auf die Aktivität und zeigt Höhenmeter', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    const link = await screen.findByText('Strava ↗')
    expect(link).toHaveAttribute('href', 'https://www.strava.com/activities/1')
    expect(screen.getByText(/340 hm/)).toBeInTheDocument()
    // Nur die eine Strava-Aktivität hat ein Badge.
    expect(screen.getAllByText('Strava ↗')).toHaveLength(1)
  })
})

describe('Achievements', () => {
  it('zeigt erreichte und offene Achievements mit Fortschritt', async () => {
    renderPage()
    expect(await screen.findByText('Startschuss')).toBeInTheDocument()
    expect(screen.getByText('Ironman')).toBeInTheDocument()
    // Offenes Achievement zeigt die Teil-Fortschritte, erreichtes nicht.
    expect(screen.getByText(/Rad: 95\/190 km/)).toBeInTheDocument()
    expect(screen.queryByText(/Gesamt: 0\/0 km/)).not.toBeInTheDocument()
  })
})
