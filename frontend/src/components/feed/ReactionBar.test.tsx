import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { FeedEvent } from '../../api/client'
import { api } from '../../api/client'
import ReactionBar from './ReactionBar'

vi.mock('../../api/client', () => ({
  api: {
    toggleFeedReaction: vi.fn().mockResolvedValue([]),
  },
}))

const ev = {
  id: 1, type: 'activity', user_id: 1, display_name: 'Anna', avatar: '🦊',
  created_at: new Date().toISOString(), payload: {},
  reactions: [{ emoji: '🔥', count: 2, mine: true, users: ['Ben', 'Clara'] }],
} as FeedEvent

function mount() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <ReactionBar ev={ev} />
    </QueryClientProvider>,
  )
}

describe('ReactionBar', () => {
  it('zeigt Chips und oeffnet die Auswahl', () => {
    mount()
    expect(screen.getByText(/🔥/)).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Reagieren'))
    expect(screen.getByText('👏')).toBeInTheDocument()
  })

  it('togglet beim Klick auf einen Chip', async () => {
    mount()
    fireEvent.click(screen.getByText(/🔥/))
    await waitFor(() => expect(api.toggleFeedReaction).toHaveBeenCalledWith(1, '🔥'))
  })
})
