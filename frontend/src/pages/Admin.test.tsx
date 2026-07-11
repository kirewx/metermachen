import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Admin from './Admin'

const patchCategory = vi.fn().mockResolvedValue({})

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
      { id: 2, name: 'Radfahren', factor: 1, color: '#00f', icon: 'rad', default_km: 20, is_active: true, strava_sport_types: [] },
    ]),
    patchCategory: (...a: unknown[]) => patchCategory(...a),
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

beforeEach(() => patchCategory.mockClear())

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
