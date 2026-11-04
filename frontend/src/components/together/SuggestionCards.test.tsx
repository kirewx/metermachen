import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Suggestion } from '../../api/client'
import SuggestionCards from './SuggestionCards'

const addons = vi.fn()
const togetherSuggestions = vi.fn()
const togetherConfirm = vi.fn()
const togetherDecline = vi.fn()
vi.mock('../../api/client', () => ({
  api: {
    addons: () => addons(),
    categories: vi.fn().mockResolvedValue([{ id: 1, name: 'Laufen' }]),
    togetherSuggestions: () => togetherSuggestions(),
    togetherConfirm: (id: number, activityId?: number) => togetherConfirm(id, activityId),
    togetherDecline: (id: number) => togetherDecline(id),
  },
}))
vi.mock('../ui/Toast', () => ({ useToast: () => vi.fn() }))

const anna = { user_id: 2, display_name: 'Anna', avatar: 'icon:laufen' }
const aktivitaet = (id: number, date: string) => ({
  id, category_id: 1, date, distance_km: 5, duration_min: null, start_time: null,
  elevation_m: null, note: null, scaled_km: 5, edited: false, source: 'manual', strava_url: null,
})
const vorschlag: Suggestion = {
  participant_id: 11,
  session_id: 1,
  source: 'auto',
  partners: [anna],
  km_together: 7.1,
  share: 0.64,
  my_activity: aktivitaet(1, '2026-11-03'),
  partner_activity: null,
  candidates: [],
}
const tag: Suggestion = {
  participant_id: 12,
  session_id: 2,
  source: 'manual',
  partners: [{ user_id: 3, display_name: 'Tom', avatar: 'icon:rad' }],
  km_together: 0,
  share: null,
  my_activity: null,
  partner_activity: {
    category_id: 1, category_name: 'Wandern', date: '2026-11-02', duration_min: 220, distance_km: 14,
  },
  candidates: [aktivitaet(5, '2026-11-02'), aktivitaet(6, '2026-11-01')],
}

function renderCards() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SuggestionCards />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  addons.mockReset()
  addons.mockResolvedValue([{ key: 'together', active: true }])
  togetherSuggestions.mockReset()
  togetherConfirm.mockReset()
  togetherConfirm.mockResolvedValue(undefined)
  togetherDecline.mockReset()
  togetherDecline.mockResolvedValue(undefined)
})

describe('SuggestionCards', () => {
  it('renders nothing when the add-on is off', async () => {
    addons.mockResolvedValue([])
    togetherSuggestions.mockResolvedValue([vorschlag])
    const { container } = renderCards()
    await waitFor(() => expect(addons).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
    expect(togetherSuggestions).not.toHaveBeenCalled()
  })

  it('confirms and declines a detected suggestion', async () => {
    togetherSuggestions.mockResolvedValue([vorschlag])
    renderCards()
    expect(await screen.findByText('Warst du mit Anna unterwegs?')).toBeInTheDocument()
    expect(screen.getByText(/\(64 %\)/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Ja, zusammen' }))
    await waitFor(() => expect(togetherConfirm).toHaveBeenCalledWith(11, undefined))
    fireEvent.click(screen.getByRole('button', { name: 'War ich nicht dabei' }))
    await waitFor(() => expect(togetherDecline).toHaveBeenCalledWith(11))
  })

  it('links the chosen candidate of a tag', async () => {
    togetherSuggestions.mockResolvedValue([tag])
    renderCards()
    expect(await screen.findByText('Tom sagt, ihr wart zusammen unterwegs')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Neu anlegen/ })).toHaveAttribute(
      'href',
      '/mymeters?verknuepfen=12',
    )
    fireEvent.click(screen.getAllByRole('radio')[1])
    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfen' }))
    await waitFor(() => expect(togetherConfirm).toHaveBeenCalledWith(12, 6))
  })
})
