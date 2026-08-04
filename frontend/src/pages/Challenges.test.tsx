import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Challenges from './Challenges'

const { challenges, joinChallenge } = vi.hoisted(() => ({
  joinChallenge: vi.fn().mockResolvedValue({}),
  challenges: [
    {
      id: 1, title: 'August bis Stuttgartlauf', description: '', prize: 'Startplatz',
      creator_id: 1, mode: 'ziel', target: 300, top_n: 1, metric: 'mm',
      category_ids: [], streak_min_mm: 5, join_mode: 'auto',
      period_start: '2026-08-04', period_end: '2026-08-31', status: 'laufend',
      vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
      standings: [
        { user_id: 1, display_name: 'Anna', avatar: '🦊', value: 187, rank: 1, geschafft: false, nicht_mehr_schaffbar: false },
      ],
      mein_stand: { user_id: 1, display_name: 'Anna', avatar: '🦊', value: 187, rank: 1, geschafft: false, nicht_mehr_schaffbar: false },
      gewinner_ids: [], created_at: '2026-08-01T10:00:00Z', resolved_at: null,
    },
    {
      id: 2, title: 'Radler-Monat', description: '', prize: 'Kuchen',
      creator_id: 1, mode: 'ziel', target: 200, top_n: 1, metric: 'mm',
      category_ids: [], streak_min_mm: 5, join_mode: 'opt_in',
      period_start: '2026-08-04', period_end: '2026-08-31', status: 'laufend',
      vorlaeufig: false, bin_dabei: false, kann_beitreten: true,
      standings: [], mein_stand: null, gewinner_ids: [],
      created_at: '2026-08-01T10:00:00Z', resolved_at: null,
    },
    {
      id: 3, title: 'Juli-Sprint', description: '', prize: null,
      creator_id: 1, mode: 'ziel', target: 100, top_n: 1, metric: 'mm',
      category_ids: [], streak_min_mm: 5, join_mode: 'auto',
      period_start: '2026-07-01', period_end: '2026-07-31', status: 'beendet',
      vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
      standings: [
        { user_id: 2, display_name: 'Ben', avatar: '🐻', value: 412, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
      ],
      mein_stand: null,
      gewinner_ids: [2], created_at: '2026-07-01T10:00:00Z',
      resolved_at: '2026-08-01T04:00:00Z',
    },
  ],
}))

vi.mock('../api/client', () => ({
  api: {
    challenges: vi.fn().mockResolvedValue(challenges),
    categories: vi.fn().mockResolvedValue([]),
    joinChallenge,
    leaveChallenge: vi.fn(),
  },
}))

function renderSeite() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Challenges />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Challenges', () => {
  it('trennt Teilnahme, Einladung und Beendetes', async () => {
    renderSeite()
    await waitFor(() =>
      expect(screen.getByText('August bis Stuttgartlauf')).toBeInTheDocument(),
    )
    expect(screen.getByText('Du bist dabei')).toBeInTheDocument()
    expect(screen.getByText('Mitmachen?')).toBeInTheDocument()
    expect(screen.getByText('Beendet')).toBeInTheDocument()
    expect(screen.getByText(/187/)).toBeInTheDocument()
    expect(screen.getByText(/Startplatz/)).toBeInTheDocument()
    // Gewinner der beendeten Challenge
    expect(screen.getByText(/Ben/)).toBeInTheDocument()
  })

  it('tritt einer offenen Challenge bei', async () => {
    renderSeite()
    await waitFor(() => expect(screen.getByText('Radler-Monat')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Beitreten' }))
    await waitFor(() => expect(joinChallenge).toHaveBeenCalledWith(2))
  })

  it('zeigt einen Hinweis, wenn es nichts gibt', async () => {
    const { api } = await import('../api/client')
    vi.mocked(api.challenges).mockResolvedValueOnce([])
    renderSeite()
    await waitFor(() =>
      expect(screen.getByText(/Noch keine Challenges/)).toBeInTheDocument(),
    )
  })
})
