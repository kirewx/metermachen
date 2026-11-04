import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import type { Challenge, ChallengeGroup } from '../../api/client'
import { ToastProvider } from '../ui/Toast'
import TeamEinstellungen from './TeamEinstellungen'

vi.mock('../../api/client', () => ({
  api: { updateChallengeGroup: vi.fn() },
}))

const gruppe = (id: number, name: string, color: string): ChallengeGroup => ({
  id, name, color, size: 1, sum: 0, value: 0, rank: id, geschafft: false, members: [],
})

const ch = {
  id: 4,
  groups: [gruppe(1, 'Team Blau', '#60a5fa'), gruppe(2, 'Team Pink', '#f472b6')],
} as unknown as Challenge

function mount(onClose = vi.fn()) {
  const qc = new QueryClient()
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <TeamEinstellungen ch={ch} g={ch.groups[0]} onClose={onClose} />
      </ToastProvider>
    </QueryClientProvider>,
  )
  return onClose
}

describe('TeamEinstellungen', () => {
  it('blocks the colour another team already has', () => {
    mount()
    expect(screen.getByRole('radio', { name: 'Blau' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('radio', { name: 'Pink (schon vergeben)' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: 'Orange' })).toBeEnabled()
  })

  it('saves the new name and colour', async () => {
    vi.mocked(api.updateChallengeGroup).mockResolvedValue(ch)
    const onClose = mount()
    fireEvent.change(screen.getByLabelText('Teamname'), { target: { value: 'Die Blitze' } })
    fireEvent.click(screen.getByRole('radio', { name: 'Grün' }))
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    await waitFor(() =>
      expect(api.updateChallengeGroup).toHaveBeenCalledWith(4, 1, { name: 'Die Blitze', color: '#4ade80' }),
    )
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })
})

describe('TeamEinstellungen with every colour taken', () => {
  it('allows any colour so a change is still possible', () => {
    const farben = ['#60a5fa', '#f472b6', '#fb923c', '#4ade80', '#a78bfa', '#facc15']
    const voll = { id: 4, groups: farben.map((f, i) => gruppe(i + 1, `G${i + 1}`, f)) } as unknown as Challenge
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <TeamEinstellungen ch={voll} g={voll.groups[0]} onClose={vi.fn()} />
        </ToastProvider>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('radio', { name: 'Pink' })).toBeEnabled()
  })
})
