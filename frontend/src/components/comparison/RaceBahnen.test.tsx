import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Comparison } from '../../api/client'
import RaceBahnen from './RaceBahnen'

vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
    ]),
    userActivities: vi.fn().mockResolvedValue([
      { id: 7, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, elevation_m: 120, note: 'Morgenlauf', scaled_km: 20, edited: false, source: 'strava', strava_url: 'https://www.strava.com/activities/42' },
    ]),
  },
}))

const data: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  users: [
    { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, km_factor: 1, by_category: [], segments: [], cumulative: [] },
  ],
  start_date: null,
  phase: 'challenge',
}

function renderRace() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <RaceBahnen data={data} />
    </QueryClientProvider>,
  )
}

describe('RaceBahnen Detailansicht', () => {
  it('öffnet beim Klick auf eine Person deren Aktivitäten mit Datum, Höhenmetern und Strava-Link', async () => {
    renderRace()
    fireEvent.click(screen.getByLabelText('Details zu Erik'))
    expect(await screen.findByText('Morgenlauf', { exact: false })).toBeInTheDocument()
    expect(screen.getByText(/120 hm/)).toBeInTheDocument()
    expect(screen.getByText('01.03.')).toBeInTheDocument()
    expect(screen.getByLabelText('Auf Strava öffnen')).toHaveAttribute(
      'href',
      'https://www.strava.com/activities/42',
    )
  })
})
