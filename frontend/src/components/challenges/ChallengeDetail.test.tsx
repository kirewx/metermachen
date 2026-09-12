import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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

function renderDetail() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/challenges/1']}>
        <Routes>
          <Route path="/challenges/:id" element={<ChallengeDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ChallengeDetail', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue(detail as never)
  })

  it('zeigt Wertung, Vorlaeufig-Hinweis und alle drei Zustaende', async () => {
    renderDetail()
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
    renderDetail()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Sieger eintragen' })).toBeInTheDocument(),
    )
    fireEvent.change(screen.getByLabelText('Sieger'), { target: { value: 'u:2' } })
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
    renderDetail()
    await waitFor(() => expect(screen.getByText(/Sieger: Rick/)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Sieger eintragen' })).toBeNull()
  })

  const teamDetail = {
    ...detail,
    title: 'Team-Oktober',
    target: 100,
    team_mode: true,
    group_count: 2,
    seeding_days: 30,
    groups_drawn: true,
    meine_gruppe_id: 2,
    sieger_group_id: null,
    kann_gruppen_bearbeiten: false,
    unassigned: [],
    standings: [
      { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 150, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
      { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 70, rank: 3, geschafft: false, nicht_mehr_schaffbar: false },
      { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 90, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
    ],
    mein_stand: { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 90, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
    groups: [
      { id: 1, name: 'Gruppe A', size: 2, sum: 220, value: 110, rank: 1, geschafft: true,
        members: [
          { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 150, rank: 1, geschafft: true, nicht_mehr_schaffbar: false },
          { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 70, rank: 3, geschafft: false, nicht_mehr_schaffbar: false },
        ] },
      { id: 2, name: 'Gruppe B', size: 1, sum: 90, value: 90, rank: 2, geschafft: false,
        members: [
          { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 90, rank: 2, geschafft: false, nicht_mehr_schaffbar: false },
        ] },
    ],
    gewinner_ids: [1, 2],
  }

  it('shows group cards with the own group first', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue(teamDetail as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Team-Oktober')).toBeInTheDocument())
    const karten = screen.getAllByTestId('group-card')
    expect(karten[0]).toHaveTextContent('Gruppe B')
    expect(karten[0]).toHaveTextContent('noch 10 pro Kopf')
    expect(karten[1]).toHaveTextContent('Gruppe A')
    expect(karten[1]).toHaveTextContent('geschafft')
    expect(karten[1]).toHaveTextContent('220 MM · 110 pro Kopf')
    expect(karten[1]).toHaveTextContent('Rick')
    expect(screen.queryByRole('link', { name: /Gruppen bearbeiten/ })).toBeNull()
  })

  it('tells that groups are not drawn yet and links the admin to the editor', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'geplant', groups_drawn: false, groups: [], meine_gruppe_id: null,
      kann_gruppen_bearbeiten: true,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Gruppen werden noch ausgelost')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /Gruppen bearbeiten/ })).toHaveAttribute(
      'href', '/arena/challenges/1/gruppen',
    )
  })

  it('lets the admin pick a winning group or one of its members', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'beendet', vorlaeufig: false, sieger_id: null, kann_sieger_setzen: true,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByLabelText('Sieger')).toBeInTheDocument())
    const select = screen.getByLabelText('Sieger') as HTMLSelectElement
    const labels = Array.from(select.options).map((o) => o.textContent)
    expect(labels).toEqual(['– bitte wählen –', 'Gruppe A', 'Rick (Gruppe A)', 'Mia (Gruppe A)'])
    fireEvent.change(select, { target: { value: 'g:1' } })
    fireEvent.click(screen.getByText('Sieger eintragen'))
    await waitFor(() =>
      expect(api.setChallengeSieger).toHaveBeenNthCalledWith(1, 1, { group_id: 1 }),
    )
    fireEvent.change(select, { target: { value: 'u:2' } })
    fireEvent.click(screen.getByText('Sieger eintragen'))
    await waitFor(() =>
      expect(api.setChallengeSieger).toHaveBeenNthCalledWith(2, 1, { user_id: 2 }),
    )
  })

  it('shows the group winner band', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'beendet', vorlaeufig: false, sieger_group_id: 1, sieger_id: null,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText(/Sieger: Gruppe A/)).toBeInTheDocument())
  })

  it('shows a person winner with their group', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'beendet', vorlaeufig: false, sieger_group_id: null, sieger_id: 2,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText(/Sieger: Mia \(Gruppe A\)/)).toBeInTheDocument())
  })

  it('ranks the groups in ranking mode', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({ ...teamDetail, mode: 'rangliste' } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Platz 1')).toBeInTheDocument())
    expect(screen.getByText('Platz 2')).toBeInTheDocument()
  })

  it('puts a trophy on the winning group and on the winning person', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, sieger_group_id: 1, sieger_id: 1,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getAllByTestId('group-card')).toHaveLength(2))
    const karten = screen.getAllByTestId('group-card')
    expect(karten[1]).toHaveTextContent('Gruppe A')
    expect(within(karten[1]).getByText('🏆')).toBeInTheDocument()
    expect(within(karten[1]).getByText('Rick 🏆')).toBeInTheDocument()
  })

  it('marks the own group card', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue(teamDetail as never)
    renderDetail()
    await waitFor(() => expect(screen.getAllByTestId('group-card')).toHaveLength(2))
    const meine = screen.getAllByTestId('group-card')[0]
    expect(meine).toHaveTextContent('Gruppe B')
    expect(meine.className).toContain('border-accent')
    expect(within(meine).getByText('du')).toBeInTheDocument()
  })

  it('names people who are not placed yet while the challenge is planned', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, status: 'geplant',
      unassigned: [{ user_id: 9, display_name: 'Tom', avatar: '🐸', value: 0, rank: 0, geschafft: false, nicht_mehr_schaffbar: false }],
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText(/Noch nicht zugeordnet: Tom/)).toBeInTheDocument())
  })

  it('says when the groups are drawn but still empty', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, groups: [], meine_gruppe_id: null,
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Noch keine Gruppen.')).toBeInTheDocument())
  })

  it('hides Austreten once a group challenge is running', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({
      ...teamDetail, join_mode: 'opt_in', status: 'laufend',
    } as never)
    renderDetail()
    await waitFor(() => expect(screen.getByText('Team-Oktober')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Austreten' })).toBeNull()
  })
})
