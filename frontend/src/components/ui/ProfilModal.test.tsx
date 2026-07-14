import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import ProfilModal from './ProfilModal'

const me: Me = { id: 1, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

const stravaStatus = vi.fn()
const consentStrava = vi.fn()
const disconnectStrava = vi.fn()
const toastSpy = vi.fn()
vi.mock('../../api/client', () => ({
  api: {
    patchMe: vi.fn(),
    stravaStatus: () => stravaStatus(),
    consentStrava: () => consentStrava(),
    disconnectStrava: () => disconnectStrava(),
  },
}))
vi.mock('./Toast', () => ({ useToast: () => toastSpy }))

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={qc}>
      <ProfilModal me={me} open onClose={vi.fn()} />
    </QueryClientProvider>,
  )
  return { qc, ...utils }
}

beforeEach(() => {
  toastSpy.mockClear()
  stravaStatus.mockReset()
  consentStrava.mockReset()
  consentStrava.mockResolvedValue(undefined)
  disconnectStrava.mockReset()
  disconnectStrava.mockResolvedValue(undefined)
})

describe('ProfilModal Strava-Abschnitt', () => {
  it('zeigt Verbinden-Button, wenn nicht verbunden und zugestimmt', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: false, consent: true })
    renderModal()
    expect(await screen.findByRole('link', { name: /Connect with Strava/ })).toBeInTheDocument()
  })

  it('zeigt Zustimmungs-Checkbox statt Verbinden-Button ohne Consent', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: false, consent: false })
    renderModal()
    const cb = await screen.findByRole('checkbox')
    expect(screen.queryByRole('link', { name: /Connect with Strava/ })).not.toBeInTheDocument()
    fireEvent.click(cb)
    await waitFor(() => expect(consentStrava).toHaveBeenCalled())
  })

  it('zeigt Trennen-Button, wenn verbunden', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: true, athlete_id: 42 })
    renderModal()
    expect(await screen.findByRole('button', { name: /Strava trennen/ })).toBeInTheDocument()
  })

  it('trennt erst nach Bestätigung (Zwei-Klick)', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: true, athlete_id: 42 })
    renderModal()
    fireEvent.click(await screen.findByRole('button', { name: /Strava trennen/ }))
    expect(disconnectStrava).not.toHaveBeenCalled() // erster Klick warnt nur
    fireEvent.click(await screen.findByRole('button', { name: /Wirklich trennen/ }))
    await waitFor(() => expect(disconnectStrava).toHaveBeenCalled())
  })

  it('zeigt nichts, wenn Feature deaktiviert', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    renderModal()
    await screen.findByLabelText('Anzeigename')
    expect(screen.queryByRole('button', { name: /Strava/ })).not.toBeInTheDocument()
  })
})

describe('ProfilModal Strava-Backfill', () => {
  it('zeigt Importfortschritt bei state running', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'running', total: 52, done: 23 },
    })
    renderModal()
    expect(await screen.findByText(/Importiere… 23 von 52/)).toBeInTheDocument()
  })

  it('feuert Toast beim Übergang running → done', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'running', total: 52, done: 50 },
    })
    const { qc } = renderModal()
    await screen.findByText(/Importiere…/)
    toastSpy.mockClear()
    act(() => {
      qc.setQueryData(['strava-status'], {
        enabled: true, connected: true, athlete_id: 42,
        backfill: { state: 'done', total: 52, done: 52 },
      })
    })
    await waitFor(() => {
      expect(toastSpy).toHaveBeenCalledWith('52 Aktivitäten importiert', 'ok')
    })
  })

  it('kein Toast, wenn Modal erst im done-Zustand öffnet', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'done', total: 52, done: 52 },
    })
    renderModal()
    await screen.findByRole('button', { name: /Strava trennen/ })
    expect(toastSpy).not.toHaveBeenCalled()
  })
})
