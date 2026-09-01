import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Admin from './Admin'

const patchCategory = vi.fn().mockResolvedValue({})
const createFactorChange = vi.fn().mockResolvedValue({})
const deleteFactorChange = vi.fn().mockResolvedValue(undefined)

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, base_factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'],
        pending_changes: [{ id: 7, factor: 3, valid_from: '2026-10-01' }], history: [] },
      { id: 2, name: 'Radfahren', factor: 1, base_factor: 1, color: '#00f', icon: 'rad', default_km: 20, is_active: true, strava_sport_types: [],
        pending_changes: [], history: [] },
    ]),
    patchCategory: (...a: unknown[]) => patchCategory(...a),
    createFactorChange: (...a: unknown[]) => createFactorChange(...a),
    deleteFactorChange: (...a: unknown[]) => deleteFactorChange(...a),
    seasons: vi.fn().mockResolvedValue([]),
    listInvites: vi.fn().mockResolvedValue([]),
    me: vi.fn().mockResolvedValue({
      id: 1, username: 'chef', display_name: 'Chef', avatar: 'icon:laufen', is_admin: true,
    }),
    listUsers: vi.fn().mockResolvedValue([
      { id: 1, username: 'chef', display_name: 'Chef', avatar: 'icon:laufen', is_admin: true, is_active: true, created_at: '2026-01-01T00:00:00Z' },
      { id: 2, username: 'lisa', display_name: 'Lisa', avatar: 'icon:rad', is_admin: false, is_active: true, created_at: '2026-02-01T00:00:00Z' },
      { id: 3, username: 'tom', display_name: 'Tom', avatar: 'icon:rad', is_admin: false, is_active: false, created_at: '2026-03-01T00:00:00Z' },
    ]),
    patchUser: vi.fn().mockResolvedValue({}),
    deleteUser: vi.fn().mockResolvedValue(undefined),
    addons: vi.fn().mockResolvedValue([]),
    createAddon: vi.fn().mockResolvedValue({}),
    patchAddon: vi.fn().mockResolvedValue({}),
    deleteAddon: vi.fn().mockResolvedValue(undefined),
    hiddenAchievementsAdmin: vi.fn().mockResolvedValue([
      { key: 'kletterkoenig', title: 'Kletterkönig', description: '1000 Höhenmeter an einem Tag.', emoji: '🏔️', unlocks: [] },
      { key: 'hattrick', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.', emoji: '🎩',
        unlocks: [{ user_id: 2, display_name: 'Lisa', avatar: 'icon:rad', unlocked_at: '2026-08-02T10:00:00Z' }] },
    ]),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAdmin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Admin />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  patchCategory.mockClear()
  createFactorChange.mockClear()
  deleteFactorChange.mockClear()
})

describe('Admin Mitglieder', () => {
  it('listet Mitglieder mit Name und Username, ohne Aktionen für sich selbst', async () => {
    renderAdmin()
    const section = (await screen.findByText('@lisa')).closest('section')!
    const s = within(section)
    expect(s.getByText('Lisa')).toBeInTheDocument()
    expect(s.getByText('@chef')).toBeInTheDocument()
    expect(s.getByText('deaktiviert')).toBeInTheDocument() // Tom
    // Für Lisa (aktiv) + Tom (inaktiv) gibt es Aktionen, für chef (selbst) nicht.
    expect(s.getAllByText('Deaktivieren')).toHaveLength(1)
    expect(s.getAllByText('Aktivieren')).toHaveLength(1)
    expect(s.queryByLabelText('Account chef löschen')).not.toBeInTheDocument()
    expect(s.getByLabelText('Account lisa löschen')).toBeInTheDocument()
  })
})

describe('Admin Faktor-Änderungen', () => {
  it('zeigt aktuellen Faktor und anstehende Änderung, legt neue an', async () => {
    renderAdmin()
    expect(await screen.findByText('×4')).toBeInTheDocument()
    expect(screen.getByText(/ab 01\.10\.2026 ×3/)).toBeInTheDocument()
    fireEvent.click(screen.getAllByText('Faktor ändern')[0])
    fireEvent.change(screen.getByLabelText('Neuer Faktor'), { target: { value: '3.5' } })
    fireEvent.change(screen.getByLabelText('Gültig ab'), { target: { value: '2026-11-01' } })
    fireEvent.click(screen.getByText('Änderung anlegen'))
    await waitFor(() =>
      expect(createFactorChange).toHaveBeenCalledWith(1, { factor: 3.5, valid_from: '2026-11-01' }),
    )
  })

  it('löscht eine anstehende Änderung', async () => {
    renderAdmin()
    fireEvent.click((await screen.findAllByText('Faktor ändern'))[0])
    fireEvent.click(screen.getByLabelText('Änderung ab 01.10.2026 löschen'))
    await waitFor(() => expect(deleteFactorChange).toHaveBeenCalledWith(1, 7))
  })
})

describe('Admin Strava-Zuordnung', () => {
  it('weist einen Typ neu zu und entfernt ihn aus der alten Kategorie', async () => {
    renderAdmin()
    const select = await screen.findByLabelText('Zuordnung Run')
    fireEvent.change(select, { target: { value: '2' } })
    await waitFor(() => {
      expect(patchCategory).toHaveBeenCalledWith(1, { strava_sport_types: [] })
      expect(patchCategory).toHaveBeenCalledWith(2, { strava_sport_types: ['Run'] })
    })
  })
})

describe('Admin hidden achievements', () => {
  it('lists every hidden achievement with its unlockers', async () => {
    renderAdmin()
    const section = (await screen.findByText('Kletterkönig')).closest('section')!
    const s = within(section)
    expect(s.getByText('noch niemand')).toBeInTheDocument()
    expect(s.getByText('Hattrick')).toBeInTheDocument()
    expect(s.getByText(/Lisa · 2\.8\.2026/)).toBeInTheDocument()
  })
})
