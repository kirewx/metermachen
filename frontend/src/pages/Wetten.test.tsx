import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Wetten from './Wetten'

const { respondBet, duell } = vi.hoisted(() => ({
  respondBet: vi.fn().mockResolvedValue({}),
  duell: {
  id: 1,
  type: 'duell',
  creator_id: 2,
  title: 'Lisa vs. Chef',
  stake: 20,
  period_start: '2099-01-02',
  period_end: '2099-01-09',
  status: 'offen',
  jackpot: 0,
  created_at: '2026-07-20T00:00:00Z',
  resolved_at: null,
  params: { opponent_id: 1 },
  result: {},
  participants: [
    {
      user_id: 2, display_name: 'Lisa', avatar: 'icon:rad',
      role: 'ersteller', stake: 20, payout: null, choice: {},
    },
  ],
    standing: {},
    my_role: null,
  },
}))

vi.mock('../api/client', () => ({
  api: {
    me: vi.fn().mockResolvedValue({
      id: 1, username: 'chef', display_name: 'Chef', avatar: 'icon:laufen', is_admin: true,
    }),
    points: vi.fn().mockResolvedValue({ balance: 80, transactions: [] }),
    bets: vi.fn().mockResolvedValue([duell]),
    betAchievements: vi.fn().mockResolvedValue([]),
    pointsRanking: vi.fn().mockResolvedValue([
      { user_id: 2, display_name: 'Lisa', avatar: 'icon:rad', balance: 100, rank: 1 },
      { user_id: 1, display_name: 'Chef', avatar: 'icon:laufen', balance: 80, rank: 2 },
    ]),
    comparison: vi.fn().mockResolvedValue({
      year: 2026, goal_km: 1000, milestones: [], start_date: '2026-07-20',
      phase: 'challenge',
      users: [
        { user_id: 1, display_name: 'Chef', avatar: 'icon:laufen', rank: 1, total_scaled_km: 0, km_factor: 1, by_category: [], segments: [], cumulative: [] },
        { user_id: 2, display_name: 'Lisa', avatar: 'icon:rad', rank: 2, total_scaled_km: 0, km_factor: 1, by_category: [], segments: [], cumulative: [] },
      ],
    }),
    respondBet: (...a: unknown[]) => respondBet(...a),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderWetten() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Wetten />
    </QueryClientProvider>,
  )
}

describe('Wetten', () => {
  it('zeigt Kontostand, offenes Duell und Punkte-Ranking', async () => {
    renderWetten()
    expect(await screen.findByText('80')).toBeInTheDocument()
    expect(screen.getByText('Offen für dich')).toBeInTheDocument()
    expect(screen.getByText('Lisa vs. Chef')).toBeInTheDocument()
    expect(screen.getByText('Punkte-Ranking')).toBeInTheDocument()
  })

  it('nimmt ein Duell an', async () => {
    renderWetten()
    fireEvent.click(await screen.findByText('Annehmen (20 P)'))
    await waitFor(() => {
      expect(respondBet).toHaveBeenCalledWith(1, { action: 'accept' })
    })
  })
})
