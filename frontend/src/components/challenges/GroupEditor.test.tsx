import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GroupEditor from './GroupEditor'

// Function declaration, not a const: vi.hoisted() below is lifted above this
// line, so an arrow-const helper would still be in the temporal dead zone.
function member(user_id: number, display_name: string, value = 0) {
  return {
    user_id, display_name, avatar: '🦊', value, rank: 0, geschafft: false, nicht_mehr_schaffbar: false,
  }
}

const { detail, seeding } = vi.hoisted(() => ({
  detail: {
    id: 1, title: 'Teams', status: 'geplant', team_mode: true, group_count: 2, seeding_days: 30,
    join_mode: 'opt_in', groups_drawn: true, kann_gruppen_bearbeiten: true,
    mode: 'ziel', target: 100, metric: 'mm', category_ids: [], top_n: 1, streak_min_mm: 5,
    period_start: '2026-10-01', period_end: '2026-10-31', description: '', prize: null,
    creator_id: 1, vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
    standings: [], mein_stand: null, gewinner_ids: [], sieger_id: null, sieger_group_id: null,
    kann_sieger_setzen: false, meine_gruppe_id: 1, created_at: '', resolved_at: null,
    groups: [
      { id: 1, name: 'Gruppe A', size: 2, sum: 0, value: 0, rank: 1, geschafft: false,
        members: [member(1, 'Rick'), member(2, 'Mia')] },
      { id: 2, name: 'Gruppe B', size: 1, sum: 0, value: 0, rank: 2, geschafft: false,
        members: [member(3, 'Lea')] },
    ],
    unassigned: [member(4, 'Tom')],
  },
  seeding: [
    { user_id: 1, display_name: 'Rick', avatar: '🦊', value: 120 },
    { user_id: 2, display_name: 'Mia', avatar: '🐻', value: 80 },
    { user_id: 3, display_name: 'Lea', avatar: '🦉', value: 60 },
    { user_id: 4, display_name: 'Tom', avatar: '🐸', value: 40 },
    { user_id: 5, display_name: 'Uli', avatar: '🐼', value: 10 },
  ],
}))

vi.mock('../../api/client', () => ({
  api: {
    challenge: vi.fn(),
    challengeSeeding: vi.fn(),
    saveChallengeGroups: vi.fn(),
    drawChallengeGroups: vi.fn(),
  },
}))
const toast = vi.hoisted(() => vi.fn())
vi.mock('../ui/Toast', () => ({ useToast: () => toast }))

function renderEditor() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/arena/challenges/1/gruppen']}>
        <Routes>
          <Route path="/arena/challenges/:id/gruppen" element={<GroupEditor />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('GroupEditor', () => {
  beforeEach(async () => {
    // The config keeps mocks between tests, so call counts would leak.
    vi.clearAllMocks()
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue(detail as never)
    vi.mocked(api.challengeSeeding).mockResolvedValue(seeding)
    vi.mocked(api.saveChallengeGroups).mockResolvedValue(detail as never)
    vi.mocked(api.drawChallengeGroups).mockResolvedValue(detail as never)
  })

  it('renders groups with seeding values and the unassigned block, pool members first', async () => {
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    const a = screen.getByTestId('editor-group-1')
    expect(a).toHaveTextContent('Rick')
    expect(a).toHaveTextContent('120')
    const frei = screen.getByTestId('editor-unassigned')
    const namen = within(frei).getAllByTestId('person-name').map((n) => n.textContent)
    expect(namen).toEqual(['Tom', 'Uli'])
    expect(screen.queryByText('ungespeichert')).toBeNull()
  })

  it('moves, removes, adds, renames and saves', async () => {
    const { api } = await import('../../api/client')
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())

    // move Mia from A to B
    fireEvent.change(screen.getByLabelText('Mia verschieben'), { target: { value: 'g:2' } })
    // remove Lea from B
    fireEvent.change(screen.getByLabelText('Lea verschieben'), { target: { value: 'remove' } })
    // add Tom to A
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    // rename A
    fireEvent.change(screen.getByDisplayValue('Gruppe A'), { target: { value: 'Flitzer' } })
    expect(screen.getByText('ungespeichert')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Speichern'))
    await waitFor(() => expect(api.saveChallengeGroups).toHaveBeenCalledWith(1, [
      { id: 1, name: 'Flitzer', member_ids: [1, 4] },
      { id: 2, name: 'Gruppe B', member_ids: [2] },
    ]))
    await waitFor(() => expect(screen.queryByText('ungespeichert')).toBeNull())
  })

  it('keeps "Speichern" disabled while nothing was edited', async () => {
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    expect(screen.getByText('Speichern')).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:2' } })
    expect(screen.getByText('Speichern')).toBeEnabled()
  })

  it('refuses to save while a group is empty', async () => {
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Lea verschieben'), { target: { value: 'remove' } })
    expect(screen.getByText('ungespeichert')).toBeInTheDocument()
    expect(screen.getByText(/eine Gruppe braucht mindestens eine Person/)).toBeInTheDocument()
    expect(screen.getByText('Speichern')).toBeDisabled()
  })

  it('reports a failed save via toast and keeps the edits', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.saveChallengeGroups).mockRejectedValue(new Error('kaputt'))
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:2' } })
    fireEvent.click(screen.getByText('Speichern'))
    await waitFor(() => expect(toast).toHaveBeenCalledWith('kaputt'))
    expect(screen.getByText('ungespeichert')).toBeInTheDocument()
  })

  it('still lets people be placed when the seeding list fails', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challengeSeeding).mockRejectedValue(new Error('nope'))
    renderEditor()
    await waitFor(() =>
      expect(screen.getByText(/Setzliste konnte nicht geladen werden: nope/)).toBeInTheDocument(),
    )
    // Tom comes from ch.unassigned, so the pool is still assignable.
    const frei = screen.getByTestId('editor-unassigned')
    expect(within(frei).getAllByTestId('person-name').map((n) => n.textContent)).toEqual(['Tom'])
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:2' } })
    expect(screen.getByText('ungespeichert')).toBeInTheDocument()
  })

  it('drops the redraw confirmation once the edits are undone', async () => {
    const { api } = await import('../../api/client')
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    fireEvent.click(screen.getByText('Neu auslosen'))
    expect(screen.getByText('Wirklich neu auslosen?')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'remove' } })
    expect(screen.getByText('Neu auslosen')).toBeInTheDocument()
    expect(api.drawChallengeGroups).not.toHaveBeenCalled()
  })

  it('warns when group sizes differ by more than one', async () => {
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    expect(screen.queryByText(/ungleich groß/)).toBeNull()
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    expect(screen.getByText(/ungleich groß/)).toBeInTheDocument()
  })

  it('asks twice before redrawing over unsaved edits', async () => {
    const { api } = await import('../../api/client')
    renderEditor()
    await waitFor(() => expect(screen.getByDisplayValue('Gruppe A')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('Tom verschieben'), { target: { value: 'g:1' } })
    fireEvent.click(screen.getByText('Neu auslosen'))
    expect(api.drawChallengeGroups).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Wirklich neu auslosen?'))
    await waitFor(() => expect(api.drawChallengeGroups).toHaveBeenCalledWith(1))
  })

  it('shows a notice when editing is not allowed', async () => {
    const { api } = await import('../../api/client')
    vi.mocked(api.challenge).mockResolvedValue({ ...detail, kann_gruppen_bearbeiten: false } as never)
    renderEditor()
    await waitFor(() =>
      expect(screen.getByText('Die Gruppen lassen sich hier nicht bearbeiten.')).toBeInTheDocument(),
    )
  })
})
