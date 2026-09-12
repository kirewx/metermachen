import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    setChallengeSieger: vi.fn().mockResolvedValue({}),
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

  it('laesst den Admin den Sieger eintragen', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...detail,
      status: 'beendet',
      vorlaeufig: false,
      gewinner_ids: [1, 2],
      sieger_id: null,
      kann_sieger_setzen: true,
      standings: [
        { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
        { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 320, rank: 2, geschafft: true, nicht_mehr_schaffbar: false },
      ],
    })
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
      expect(screen.getByRole('button', { name: 'Sieger eintragen' })).toBeInTheDocument(),
    )
    fireEvent.change(screen.getByLabelText('Sieger'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sieger eintragen' }))
    await waitFor(() => expect(api.setChallengeSieger).toHaveBeenCalledWith(1, { user_id: 2 }))
  })

  it('zeigt den eingetragenen Sieger allen', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...detail,
      status: 'beendet',
      vorlaeufig: false,
      gewinner_ids: [1],
      sieger_id: 1,
      kann_sieger_setzen: false,
    })
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
    await waitFor(() => expect(screen.getByText(/Sieger: Rick/)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Sieger eintragen' })).toBeNull()
  })
})
