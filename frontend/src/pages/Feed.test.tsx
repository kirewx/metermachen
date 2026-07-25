import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Feed from './Feed'

const { events } = vi.hoisted(() => ({
  events: [
    {
      id: 2, type: 'activity', user_id: 1, display_name: 'Anna', avatar: '🦊',
      created_at: new Date().toISOString(),
      payload: { category: { name: 'Rad', icon: 'rad', color: '#60a5fa' }, distance_km: 42.3, mm: 38, titel: 'Feierabendrunde' },
      reactions: [{ emoji: '👏', count: 3, mine: false, users: ['Ben'] }],
    },
    {
      id: 1, type: 'rank_change', user_id: 1, display_name: 'Anna', avatar: '🦊',
      created_at: new Date().toISOString(),
      payload: { name: 'Anna', ueberholt_name: 'Ben', neuer_rang: 2 },
      reactions: [],
    },
  ],
}))

vi.mock('../api/client', () => ({
  api: {
    seasons: vi.fn().mockResolvedValue([
      { id: 1, year: 2026, goal_km: 1000, milestones: [], start_date: '2026-07-20', end_date: '2027-05-16' },
    ]),
    feed: vi.fn().mockResolvedValue({ events, next_before: null }),
    feedUnseen: vi.fn().mockResolvedValue({ has_new: false }),
    markFeedSeen: vi.fn().mockResolvedValue(undefined),
    toggleFeedReaction: vi.fn(),
  },
}))

describe('Feed', () => {
  it('zeigt Aktivitaets- und Ueberholungs-Eintraege', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <Feed />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByText(/Feierabendrunde/)).toBeInTheDocument())
    expect(screen.getByText(/überholt/)).toBeInTheDocument()
    expect(screen.getByText(/Heute/)).toBeInTheDocument()
  })
})
