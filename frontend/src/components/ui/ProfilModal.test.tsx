import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import ProfilModal from './ProfilModal'

const me: Me = { id: 1, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

const stravaStatus = vi.fn()
vi.mock('../../api/client', () => ({
  api: { patchMe: vi.fn(), stravaStatus: () => stravaStatus(), disconnectStrava: vi.fn() },
}))
vi.mock('./Toast', () => ({ useToast: () => vi.fn() }))

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ProfilModal me={me} open onClose={vi.fn()} />
    </QueryClientProvider>,
  )
}

describe('ProfilModal Strava-Abschnitt', () => {
  it('zeigt Verbinden-Button, wenn nicht verbunden', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: false })
    renderModal()
    expect(await screen.findByRole('button', { name: /Mit Strava verbinden/ })).toBeInTheDocument()
  })

  it('zeigt Trennen-Button, wenn verbunden', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: true, athlete_id: 42 })
    renderModal()
    expect(await screen.findByRole('button', { name: /Strava trennen/ })).toBeInTheDocument()
  })

  it('zeigt nichts, wenn Feature deaktiviert', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    renderModal()
    await screen.findByLabelText('Anzeigename')
    expect(screen.queryByRole('button', { name: /Strava/ })).not.toBeInTheDocument()
  })
})
