import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import SettingsSection from './SettingsSection'

const me: Me = { id: 1, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

const stravaStatus = vi.fn()
const consentStrava = vi.fn()
const disconnectStrava = vi.fn()
const logout = vi.fn()
const toastSpy = vi.fn()
vi.mock('../../api/client', () => ({
  api: {
    patchMe: vi.fn(),
    achievements: vi.fn().mockResolvedValue([]),
    stravaStatus: () => stravaStatus(),
    consentStrava: () => consentStrava(),
    disconnectStrava: () => disconnectStrava(),
    logout: () => logout(),
  },
}))
vi.mock('../ui/Toast', () => ({ useToast: () => toastSpy }))

function renderSection() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData(['me'], me)
  const utils = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SettingsSection me={me} />
      </MemoryRouter>
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
  logout.mockReset()
  logout.mockResolvedValue(undefined)
})

describe('SettingsSection Strava section', () => {
  it('shows the connect button when not connected but consented', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: false, consent: true })
    renderSection()
    expect(await screen.findByRole('link', { name: /Connect with Strava/ })).toBeInTheDocument()
  })

  it('shows the consent checkbox instead of the connect button without consent', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: false, consent: false })
    renderSection()
    const cb = await screen.findByRole('checkbox')
    expect(screen.queryByRole('link', { name: /Connect with Strava/ })).not.toBeInTheDocument()
    fireEvent.click(cb)
    await waitFor(() => expect(consentStrava).toHaveBeenCalled())
  })

  it('shows the disconnect button when connected', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: true, athlete_id: 42 })
    renderSection()
    expect(await screen.findByRole('button', { name: /Strava trennen/ })).toBeInTheDocument()
  })

  it('disconnects only after confirmation (two clicks)', async () => {
    stravaStatus.mockResolvedValue({ enabled: true, connected: true, athlete_id: 42 })
    renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /Strava trennen/ }))
    expect(disconnectStrava).not.toHaveBeenCalled() // first click only warns
    fireEvent.click(await screen.findByRole('button', { name: /Wirklich trennen/ }))
    await waitFor(() => expect(disconnectStrava).toHaveBeenCalled())
  })

  it('shows nothing when the feature is disabled', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    renderSection()
    await screen.findByLabelText('Anzeigename')
    expect(screen.queryByRole('button', { name: /Strava/ })).not.toBeInTheDocument()
  })
})

describe('SettingsSection Strava backfill', () => {
  it('shows import progress while running', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'running', total: 52, done: 23 },
    })
    renderSection()
    expect(await screen.findByText(/Importiere… 23 von 52/)).toBeInTheDocument()
  })

  it('fires a toast on the running → done transition', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'running', total: 52, done: 50 },
    })
    const { qc } = renderSection()
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

  it('no toast when the section mounts already in the done state', async () => {
    stravaStatus.mockResolvedValue({
      enabled: true, connected: true, athlete_id: 42,
      backfill: { state: 'done', total: 52, done: 52 },
    })
    renderSection()
    await screen.findByRole('button', { name: /Strava trennen/ })
    expect(toastSpy).not.toHaveBeenCalled()
  })
})

describe('SettingsSection footer', () => {
  it('links to the rules', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    renderSection()
    expect(await screen.findByRole('link', { name: 'Regeln' })).toHaveAttribute('href', '/regeln')
  })

  it('logout calls the API and clears the me query', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    const { qc } = renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /Logout/ }))
    await waitFor(() => expect(logout).toHaveBeenCalled())
    await waitFor(() => expect(qc.getQueryData(['me'])).toBeNull())
  })
})
