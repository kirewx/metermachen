import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ChallengeDetail from './ChallengeDetail'

const { detail } = vi.hoisted(() => ({
  detail: {
    id: 1, title: 'August bis Stuttgartlauf', description: '', prize: 'Startplatz',
    creator_id: 1, mode: 'ziel', target: 300, top_n: 1, metric: 'mm',
    category_ids: [], streak_min_mm: 5, join_mode: 'auto',
    period_start: '2026-08-04', period_end: '2026-08-31', status: 'laufend',
    vorlaeufig: true, bin_dabei: true, kann_beitreten: false,
    standings: [
      { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
      { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 187, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
      { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 14, rank: 3, geschafft: false, nicht_mehr_schaffbar: true },
    ],
    mein_stand: { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
    gewinner_ids: [1], created_at: '2026-08-01T10:00:00Z', resolved_at: null,
  },
}))

vi.mock('../../api/client', () => ({
  api: {
    challenge: vi.fn().mockResolvedValue(detail),
    categories: vi.fn().mockResolvedValue([]),
    joinChallenge: vi.fn(),
    leaveChallenge: vi.fn(),
  },
}))

describe('ChallengeDetail', () => {
  it('zeigt Wertung, Vorlaeufig-Hinweis und alle drei Zustaende', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={['/challenges/1']}>
          <Routes>
            <Route path="/challenges/:id" element={<ChallengeDetail />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    await waitFor(() =>
      expect(screen.getByText('August bis Stuttgartlauf')).toBeInTheDocument(),
    )
    expect(screen.getByText('Ziel: 300 MM aus allen Sportarten')).toBeInTheDocument()
    expect(screen.getByText(/vorläufig/i)).toBeInTheDocument()
    expect(screen.getByText('geschafft')).toBeInTheDocument()
    expect(screen.getByText('noch 113')).toBeInTheDocument()
    expect(screen.getByText('nicht mehr')).toBeInTheDocument()
  })
})
