import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import ChallengesAdmin from './ChallengesAdmin'

vi.mock('../../api/client', () => ({
  api: {
    challenges: vi.fn().mockResolvedValue([
      { id: 5, title: 'Teams', status: 'geplant', team_mode: true },
      { id: 6, title: 'Solo', status: 'geplant', team_mode: false },
    ]),
    categories: vi.fn().mockResolvedValue([]),
    createChallenge: vi.fn().mockResolvedValue({}),
    cancelChallenge: vi.fn(),
  },
}))
vi.mock('../ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAdmin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ChallengesAdmin />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('ChallengesAdmin group fields', () => {
  it('reveals group fields, hides streak and posts the group settings', async () => {
    const { api } = await import('../../api/client')
    renderAdmin()
    expect(screen.queryByLabelText('Anzahl Gruppen')).toBeNull()
    expect(screen.getByRole('option', { name: 'Streak (Tage am Stück)' })).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Gruppen-Challenge'))
    expect(screen.getByLabelText('Anzahl Gruppen')).toHaveValue(3)
    expect(screen.getByLabelText('Setzliste: letzte N Tage')).toHaveValue(30)
    expect(screen.queryByRole('option', { name: 'Streak (Tage am Stück)' })).toBeNull()
    expect(screen.getByLabelText('Ziel pro Kopf')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Anzahl Gruppen'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Titel'), { target: { value: 'Teams' } })
    fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2026-10-01' } })
    fireEvent.change(screen.getByLabelText('Ende'), { target: { value: '2026-10-31' } })
    fireEvent.click(screen.getByText('Challenge anlegen'))
    await waitFor(() => expect(api.createChallenge).toHaveBeenCalled())
    expect(vi.mocked(api.createChallenge).mock.calls[0][0]).toMatchObject({
      team_mode: true, group_count: 4, seeding_days: 30,
    })
  })

  it('links planned group challenges to the editor', async () => {
    renderAdmin()
    await waitFor(() => expect(screen.getByText('Teams')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: 'Gruppen' })
    expect(link).toHaveAttribute('href', '/arena/challenges/5/gruppen')
    expect(screen.getAllByRole('link', { name: 'Gruppen' })).toHaveLength(1)
  })

  it('resets a selected streak metric to mm when switching to group mode', () => {
    renderAdmin()
    fireEvent.change(screen.getByLabelText('Wertung'), { target: { value: 'streak' } })
    fireEvent.click(screen.getByLabelText('Gruppen-Challenge'))
    expect(screen.getByLabelText('Wertung')).toHaveValue('mm')
  })

  it('does not send group settings for a solo challenge', async () => {
    const { api } = await import('../../api/client')
    renderAdmin()
    fireEvent.change(screen.getByLabelText('Titel'), { target: { value: 'Solo' } })
    fireEvent.change(screen.getByLabelText('Start'), { target: { value: '2026-10-01' } })
    fireEvent.change(screen.getByLabelText('Ende'), { target: { value: '2026-10-31' } })
    fireEvent.click(screen.getByText('Challenge anlegen'))
    await waitFor(() => expect(api.createChallenge).toHaveBeenCalled())
    const calls = vi.mocked(api.createChallenge).mock.calls
    const payload = calls[calls.length - 1][0]
    expect(payload).not.toHaveProperty('group_count', 3)
    expect(payload.group_count).toBeUndefined()
    expect(payload.seeding_days).toBeUndefined()
  })
})
