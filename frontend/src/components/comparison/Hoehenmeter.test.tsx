import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Comparison, ComparisonUser } from '../../api/client'
import Hoehenmeter from './Hoehenmeter'

vi.mock('../../api/client', () => ({
  api: {
    me: vi.fn().mockResolvedValue({
      id: 6, username: 'erik', display_name: 'P6', avatar: 'icon:laufen', is_admin: false,
    }),
    categories: vi.fn().mockResolvedValue([]),
    userActivities: vi.fn().mockResolvedValue([]),
  },
}))

function user(id: number, hm: number): ComparisonUser {
  return {
    user_id: id,
    display_name: `P${id}`,
    avatar: 'icon:laufen',
    rank: id,
    total_scaled_km: 0,
    total_real_km: 0,
    total_elevation_m: hm,
    km_factor: 1,
    by_category: [],
    segments: [],
    cumulative: [{ date: '2026-07-05', scaled_km: 10, real_km: 10, elevation_m: hm }],
    elevation_by_month: hm > 0 ? [{ month: '2026-07', meters: hm }] : [],
  }
}

function daten(users: ComparisonUser[]): Comparison {
  return {
    year: 2026,
    goal_km: 1000,
    milestones: [],
    users,
    start_date: '2026-07-01',
    phase: 'challenge',
    elevation_months: ['2026-07'],
  }
}

const feld = daten(Array.from({ length: 10 }, (_, i) => user(i + 1, 1000 - i * 100)))

function renderHm(data: Comparison) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Hoehenmeter data={data} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Hoehenmeter', () => {
  it('startet mit allen Personen im Panorama', async () => {
    renderHm(feld)
    expect(await screen.findByRole('button', { name: 'Alle' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText('Personen (10/10)')).toBeInTheDocument()
  })

  it('engt über das Nachbarschafts-Preset auf sechs Personen ein', async () => {
    renderHm(feld)
    // Erst warten, bis die eigene Person bekannt ist — sonst gäbe es keine Nachbarschaft
    await screen.findByText(/Platz 6 von 10/)
    fireEvent.click(screen.getByRole('button', { name: 'Nachbarschaft' }))
    // Führender plus zwei über und unter mir (Platz 6)
    expect(screen.getByText('Personen (6/10)')).toBeInTheDocument()
  })

  it('schaltet über "Nur ich" auf die eigene Säule', async () => {
    renderHm(feld)
    await screen.findByText(/Platz 6 von 10/)
    fireEvent.click(screen.getByRole('button', { name: 'Nur ich' }))
    expect(screen.getByText('Personen (1/10)')).toBeInTheDocument()
    expect(screen.getByLabelText('Details zu P6')).toBeInTheDocument()
  })

  it('nimmt einzelne Personen über die Liste raus', async () => {
    renderHm(feld)
    fireEvent.click(await screen.findByRole('button', { name: 'P3 ein-/ausblenden' }))
    expect(screen.getByText('Personen (9/10)')).toBeInTheDocument()
  })

  it('wechselt zwischen Säulen und Verlauf', async () => {
    renderHm(feld)
    const verlauf = await screen.findByRole('button', { name: 'Verlauf' })
    fireEvent.click(verlauf)
    expect(verlauf).toHaveAttribute('aria-pressed', 'true')
    // Panorama ist weg — keine Säulen-Buttons mehr
    expect(screen.queryByLabelText('Details zu P1')).not.toBeInTheDocument()
  })

  it('erklärt den leeren Zustand statt ein leeres Diagramm zu zeigen', () => {
    renderHm(daten([user(1, 0), user(2, 0)]))
    expect(screen.getByText(/Noch keine Höhenmeter/)).toBeInTheDocument()
  })
})
