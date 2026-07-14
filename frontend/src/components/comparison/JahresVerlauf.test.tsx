import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Comparison } from '../../api/client'
import JahresVerlauf from './JahresVerlauf'

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
    { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, km_factor: 1, by_category: [], segments: [], cumulative: [{ date: '2026-03-01', scaled_km: 20 }] },
  ],
  start_date: null,
  phase: 'challenge',
}

function renderVerlauf() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <JahresVerlauf data={data} />
    </QueryClientProvider>,
  )
}

describe('JahresVerlauf Detailansicht', () => {
  it('öffnet über die anklickbare Personen-Legende die Detailansicht', async () => {
    renderVerlauf()
    fireEvent.click(screen.getByLabelText('Details zu Erik'))
    expect(await screen.findByText('Morgenlauf', { exact: false })).toBeInTheDocument()
  })
})
