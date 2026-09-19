import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import type { Comparison } from '../../api/client'
import RaceBahnen from './RaceBahnen'

vi.mock('../../api/client', () => ({
  api: {
    lastSeenComparison: vi.fn().mockResolvedValue({
      seen_at: '2020-01-01T00:00:00Z',
      entries: [{ user_id: 1, scaled_km: 100, rank: 1 }],
    }),
    markComparisonSeen: vi.fn().mockResolvedValue({ seen_at: '2020-01-01T00:00:00Z', entries: [] }),
  },
}))

const data: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  users: [
    { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, total_real_km: 75, km_factor: 1, by_category: [], segments: [], cumulative: [], emojis: ['👑', '🎩'], auszeichnungen: [
      { emoji: '👑', title: 'Erster Gold', description: 'Als Erster ein Gold-Achievement geholt.' },
      { emoji: '🎩', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.' },
    ] },
    { user_id: 2, display_name: 'Mara', avatar: 'icon:rad', rank: 2, total_scaled_km: 111, total_real_km: 37, km_factor: 1, by_category: [], segments: [], cumulative: [], emojis: [], auszeichnungen: [] },
  ],
  start_date: null,
  phase: 'challenge',
}

function renderRace(mode?: 'mm' | 'km', d: Comparison = data) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RaceBahnen data={d} mode={mode} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('RaceBahnen Detailansicht', () => {
  it('verlinkt jede Person auf ihre Profilseite in derselben Saison', () => {
    renderRace()
    expect(screen.getByLabelText('Profil von Erik')).toHaveAttribute('href', '/profil/1?jahr=2026')
    expect(screen.getByLabelText('Profil von Mara')).toHaveAttribute('href', '/profil/2?jahr=2026')
  })

  it('zeigt im km-Modus die echten km statt der skalierten MM', () => {
    renderRace('km')
    expect(screen.getByText('75')).toBeInTheDocument()
    expect(screen.queryByText('300')).not.toBeInTheDocument()
  })

  it('zeigt das Seit-Besuch-Banner und das Delta, wenn der letzte Besuch alt genug ist', async () => {
    renderRace()
    expect(await screen.findByText(/Seit deinem letzten Besuch/)).toBeInTheDocument()
    // Exakter String: matcht nur das Balken-Label "+200" — das Banner enthält
    // "+200" ebenfalls, aber als Teil eines längeren Textes (kein exakter Match).
    expect(screen.getByText('+200')).toBeInTheDocument()
  })

  it('zeigt Platzierungen als nackte Zahl ohne P-Präfix und ohne Rückstand-Zeile', () => {
    renderRace()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.queryByText('P1')).toBeNull()
    expect(screen.queryByText('P2')).toBeNull()
    expect(screen.queryByText(/auf P1/)).toBeNull()
  })

  it('zeigt Special-Emojis neben dem Namen mit Popover beim Klick', async () => {
    renderRace()
    expect(await screen.findByText('👑')).toBeInTheDocument()
    expect(screen.queryByText('Hattrick')).toBeNull()
    fireEvent.click(screen.getByText('🎩'))
    expect(screen.getByText('Hattrick')).toBeInTheDocument()
    expect(screen.getByText('Drei Aktivitäten an einem Tag.')).toBeInTheDocument()
  })
})

describe('RaceBahnen Monatsmodus', () => {
  const monthData = {
    ...data,
    month: '2026-09',
    milestones: [{ km: 500, icon: 'berg', label: 'Halbzeit' }],
  } as Comparison

  it('zeigt weder Ziel noch Meilensteine', () => {
    renderRace('mm', monthData)
    expect(screen.queryByText('1000')).toBeNull()
    expect(screen.queryByText('500')).toBeNull()
  })

  it('zeigt im Jahresmodus Ziel und Meilensteine', () => {
    renderRace('mm', { ...monthData, month: null } as Comparison)
    expect(screen.getByText('1000')).toBeInTheDocument()
    expect(screen.getByText('500')).toBeInTheDocument()
  })

  it('zeigt kein Seit-Besuch-Banner und markiert nichts als gesehen', async () => {
    vi.mocked(api.lastSeenComparison).mockClear()
    renderRace('mm', monthData)
    await waitFor(() => expect(screen.getByText('300')).toBeInTheDocument())
    expect(screen.queryByText(/Seit deinem letzten Besuch/)).toBeNull()
    expect(api.lastSeenComparison).not.toHaveBeenCalled()
  })

  it('markiert den Besuch auch dann, wenn ein Monat-Umschalten den Timer abgebrochen hat', async () => {
    vi.mocked(api.markComparisonSeen).mockClear()
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const tree = (d: Comparison) => (
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <RaceBahnen data={d} />
        </MemoryRouter>
      </QueryClientProvider>
    )
    const view = render(tree(data))
    await screen.findByText(/Seit deinem letzten Besuch/)
    // Jahr → Monat → Jahr before the 1.6 s timer fires; the component stays mounted.
    view.rerender(tree(monthData))
    expect(screen.queryByText(/Seit deinem letzten Besuch/)).toBeNull()
    view.rerender(tree(data))
    await waitFor(() => expect(api.markComparisonSeen).toHaveBeenCalledTimes(1), { timeout: 3000 })
  })

  it('zeigt Rang – für Personen ohne Meter', () => {
    const zero = {
      ...monthData,
      users: monthData.users.map((u) => ({ ...u, total_scaled_km: 0, total_real_km: 0 })),
    } as Comparison
    renderRace('mm', zero)
    expect(screen.getAllByText('–')).toHaveLength(2)
    expect(screen.queryByText('1')).toBeNull()
  })
})
