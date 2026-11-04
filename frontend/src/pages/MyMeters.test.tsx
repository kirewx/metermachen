import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MyMeters from './MyMeters'

const addons = vi.fn()
const togetherSuggestions = vi.fn()
const togetherDecline = vi.fn()
const togetherConfirm = vi.fn()
const createActivity = vi.fn()
const together = vi.hoisted(() => ({
  session_id: 7,
  participant_id: 70,
  status: 'confirmed',
  partners: [{ user_id: 2, display_name: 'Anna', avatar: 'icon:laufen' }],
  pending: [],
  km_together: 4.2,
}))
vi.mock('../api/client', () => ({
  api: {
    addons: () => addons(),
    togetherMembers: vi.fn().mockResolvedValue([
      { user_id: 2, display_name: 'Anna', avatar: 'icon:laufen' },
    ]),
    togetherSuggestions: () => togetherSuggestions(),
    togetherDecline: (id: number) => togetherDecline(id),
    togetherConfirm: (id: number, activityId?: number) => togetherConfirm(id, activityId),
    createActivity: (b: unknown) => createActivity(b),
    seasons: vi.fn().mockResolvedValue([]),
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#fff', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
    ]),
    activities: vi.fn().mockResolvedValue([
      { id: 1, category_id: 1, date: '2026-03-01', distance_km: 5, duration_min: null, elevation_m: 340, note: null, scaled_km: 20, edited: false, source: 'strava', strava_url: 'https://www.strava.com/activities/1', together },
      { id: 2, category_id: 1, date: '2026-03-02', distance_km: 3, duration_min: null, elevation_m: null, note: null, scaled_km: 12, edited: false, source: 'manual', strava_url: null },
    ]),
  },
}))

vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderPage(url = '/mymeters') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <MyMeters />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const togetherAn = [{ key: 'together', active: true }]

beforeEach(() => {
  addons.mockReset()
  addons.mockResolvedValue([])
  togetherSuggestions.mockReset()
  togetherSuggestions.mockResolvedValue([])
  togetherDecline.mockReset()
  togetherDecline.mockResolvedValue(undefined)
  togetherConfirm.mockReset()
  togetherConfirm.mockResolvedValue(undefined)
  createActivity.mockReset()
  createActivity.mockResolvedValue({ id: 99 })
})

describe('MyMeters', () => {
  it('groups by category, collapsed by default, expands on click', async () => {
    renderPage()
    expect(await screen.findByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText(/2 Einträge/)).toBeInTheDocument()
    expect(screen.getByText('32 MM')).toBeInTheDocument()
    expect(screen.queryByText(/Strava/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Laufen'))
    expect(await screen.findByText('View on Strava')).toBeInTheDocument()
  })

  it('links the Strava badge to the activity and shows elevation', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    const link = await screen.findByText('View on Strava')
    expect(link).toHaveAttribute('href', 'https://www.strava.com/activities/1')
    expect(screen.getByText(/340 hm/)).toBeInTheDocument()
    // Only the one Strava activity carries a badge.
    expect(screen.getAllByText('View on Strava')).toHaveLength(1)
  })

  it('has no achievements block any more', async () => {
    renderPage()
    await screen.findByText('Laufen')
    expect(screen.queryByText('Achievements')).not.toBeInTheDocument()
  })

  it('shows no together badge when the add-on is off', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    await screen.findByText('View on Strava')
    expect(screen.queryByRole('button', { name: 'Zusammen mit Anna' })).not.toBeInTheDocument()
  })

  it('expands the badge and declines the own participation', async () => {
    addons.mockResolvedValue(togetherAn)
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    fireEvent.click(await screen.findByRole('button', { name: 'Zusammen mit Anna' }))
    expect(screen.getByText('4,2 km gemeinsam')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'War ich nicht dabei' }))
    await waitFor(() => expect(togetherDecline).toHaveBeenCalledWith(70))
  })

  it('creates an activity from a tag and links it', async () => {
    addons.mockResolvedValue(togetherAn)
    togetherSuggestions.mockResolvedValue([
      {
        participant_id: 55,
        session_id: 5,
        source: 'manual',
        partners: [{ user_id: 3, display_name: 'Tom', avatar: 'icon:laufen' }],
        km_together: 0,
        share: null,
        my_activity: null,
        partner_activity: {
          category_id: 1, category_name: 'Laufen', date: '2026-03-05', duration_min: 40, distance_km: 7.5,
        },
        candidates: [],
      },
    ])
    renderPage('/mymeters?verknuepfen=55')
    expect(await screen.findByText(/gemeinsame Einheit mit/)).toBeInTheDocument()
    expect(screen.getByLabelText('Datum')).toHaveValue('2026-03-05')
    fireEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    await waitFor(() => expect(togetherConfirm).toHaveBeenCalledWith(55, 99))
    expect(createActivity).toHaveBeenCalledWith(
      expect.objectContaining({ category_id: 1, date: '2026-03-05', distance_km: 7.5, duration_min: 40 }),
    )
  })
})
