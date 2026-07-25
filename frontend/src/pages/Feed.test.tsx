import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Feed from './Feed'

const { events } = vi.hoisted(() => ({
  events: [
    {
      id: 3, type: 'activity', user_id: 1, display_name: 'Anna', avatar: '🦊',
      created_at: new Date().toISOString(),
      payload: {
        category: { name: 'Rad', icon: 'rad', color: '#60a5fa' },
        distance_km: 42.3, mm: 38, titel: 'Feierabendrunde',
        strava_url: 'https://www.strava.com/activities/99',
      },
      reactions: [{ emoji: '👏', count: 3, mine: false, users: ['Ben'] }],
    },
    {
      id: 2, type: 'rank_change', user_id: 1, display_name: 'Anna', avatar: '🦊',
      created_at: new Date().toISOString(),
      payload: {
        name: 'Anna', alter_rang: 4, neuer_rang: 2,
        ueberholte: [{ user_id: 2, name: 'Ben' }, { user_id: 3, name: 'Clara' }],
      },
      reactions: [],
    },
    {
      id: 1, type: 'achievement', user_id: 1, display_name: 'Anna', avatar: '🦊',
      created_at: new Date().toISOString(),
      payload: {
        key: 'hattrick', title: 'Hattrick', emoji: '🎩',
        description: 'Drei Aktivitäten an einem Tag.',
      },
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
    // Gebündelte Überholung mit altem → neuem Platz
    expect(screen.getByText('Ben und Clara')).toBeInTheDocument()
    expect(screen.getByText(/Platz 4 →/)).toBeInTheDocument()
    // Strava-Link an der Aktivität
    expect(screen.getByRole('link', { name: /View on Strava/i })).toHaveAttribute(
      'href',
      'https://www.strava.com/activities/99',
    )
  })

  it('zeigt die Achievement-Beschreibung beim Klick', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <Feed />
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByText(/Hattrick/)).toBeInTheDocument())
    expect(screen.queryByText(/Drei Aktivitäten an einem Tag/)).toBeNull()
    fireEvent.click(screen.getByText(/Hattrick/))
    expect(screen.getByText(/Drei Aktivitäten an einem Tag/)).toBeInTheDocument()
  })
})
