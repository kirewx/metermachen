import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Admin from './Admin'

const patchCategory = vi.fn().mockResolvedValue({})

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
      { id: 2, name: 'Radfahren', factor: 1, color: '#00f', icon: 'rad', default_km: 20, is_active: true, strava_sport_types: [] },
    ]),
    patchCategory: (...a: unknown[]) => patchCategory(...a),
    seasons: vi.fn().mockResolvedValue([]),
    listInvites: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAdmin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Admin />
    </QueryClientProvider>,
  )
}

beforeEach(() => patchCategory.mockClear())

describe('Admin Strava-Zuordnung', () => {
  it('weist einen Typ neu zu und entfernt ihn aus der alten Kategorie', async () => {
    renderAdmin()
    const select = await screen.findByLabelText('Zuordnung Run')
    fireEvent.change(select, { target: { value: '2' } })
    await waitFor(() => {
      expect(patchCategory).toHaveBeenCalledWith(1, { strava_sport_types: [] })
      expect(patchCategory).toHaveBeenCalledWith(2, { strava_sport_types: ['Run'] })
    })
  })
})
