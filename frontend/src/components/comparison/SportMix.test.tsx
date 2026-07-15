import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Comparison } from '../../api/client'
import SportMix from './SportMix'

vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: [] },
    ]),
    userActivities: vi.fn().mockResolvedValue([
      { id: 7, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, elevation_m: null, note: 'Morgenlauf', scaled_km: 20, edited: false, source: 'manual', strava_url: null },
    ]),
  },
}))

const data: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  users: [
    {
      user_id: 1,
      display_name: 'Erik',
      avatar: 'icon:laufen',
      rank: 1,
      total_scaled_km: 300,
      total_real_km: 150,
      km_factor: 1,
      by_category: [
        { category_id: 1, name: 'Laufen', color: '#f00', icon: 'laufen', scaled_km: 200, real_km: 50 },
        { category_id: 2, name: 'Radfahren', color: '#00f', icon: 'rad', scaled_km: 100, real_km: 100 },
      ],
      segments: [],
      cumulative: [],
    },
  ],
  start_date: null,
  phase: 'challenge',
}

function renderMix() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SportMix data={data} />
    </QueryClientProvider>,
  )
}

describe('SportMix', () => {
  it('zeigt Person, gewertete Gesamtsumme und Kategorie-Legende', () => {
    renderMix()
    expect(screen.getByText('Erik')).toBeInTheDocument()
    expect(screen.getByText(/^300/)).toBeInTheDocument()
    expect(screen.getByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText('Radfahren')).toBeInTheDocument()
  })

  it('zeigt im km-Modus die echten km statt der skalierten MM', () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <SportMix data={data} mode="km" />
      </QueryClientProvider>,
    )
    // echte km: 50 (Laufen) + 100 (Radfahren) = 150, nicht 300 MM
    expect(screen.getByText(/^150/)).toBeInTheDocument()
    expect(screen.queryByText(/^300/)).not.toBeInTheDocument()
  })

  it('öffnet beim Klick auf eine Person deren Detailansicht', async () => {
    renderMix()
    fireEvent.click(screen.getByLabelText('Details zu Erik'))
    expect(await screen.findByText('Morgenlauf', { exact: false })).toBeInTheDocument()
  })

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
            { category_id: 1, name: 'Laufen', color: '#f00', icon: 'laufen', scaled_km: 195, real_km: 48.75 },
            { category_id: 2, name: 'Radfahren', color: '#00f', icon: 'rad', scaled_km: 5, real_km: 5 }, // 2,5 % < 9 %
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
})
