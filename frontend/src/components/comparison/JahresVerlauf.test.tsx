import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Comparison } from '../../api/client'
import JahresVerlauf from './JahresVerlauf'

vi.mock('../../api/client', () => ({
  api: {
  },
}))

const data: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  users: [
    { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, total_real_km: 75, km_factor: 1, by_category: [], segments: [], cumulative: [{ date: '2026-03-01', scaled_km: 20, real_km: 5 }] },
  ],
  start_date: null,
  phase: 'challenge',
}

function renderVerlauf() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <JahresVerlauf data={data} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('JahresVerlauf Personen-Legende', () => {
  it('verlinkt die Person auf ihre Profilseite', () => {
    renderVerlauf()
    expect(screen.getByLabelText('Profil von Erik')).toHaveAttribute('href', '/profil/1?jahr=2026')
  })

  it('togglet eine Kurve über den Chip und schaltet mit Alle/Keine', () => {
    const zwei: Comparison = {
      year: 2026, goal_km: 1000, milestones: [], start_date: null, phase: 'challenge',
      users: [
        { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, total_real_km: 300, km_factor: 1,
          by_category: [], segments: [], cumulative: [{ date: '2026-01-01', scaled_km: 300, real_km: 300 }] },
        { user_id: 2, display_name: 'Lisa', avatar: 'icon:laufen', rank: 2, total_scaled_km: 200, total_real_km: 200, km_factor: 1,
          by_category: [], segments: [], cumulative: [{ date: '2026-01-01', scaled_km: 200, real_km: 200 }] },
      ],
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <JahresVerlauf data={zwei} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    // Toggle-Chip hat aria-pressed
    const chip = screen.getByRole('button', { name: 'Erik ein-/ausblenden' })
    expect(chip).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(chip)
    expect(chip).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Keine' }))
    expect(screen.getByRole('button', { name: 'Lisa ein-/ausblenden' })).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(screen.getByRole('button', { name: 'Alle' }))
    expect(screen.getByRole('button', { name: 'Lisa ein-/ausblenden' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('bietet den Profil-Link als eigenen i-Knopf neben dem Toggle an', () => {
    const zwei: Comparison = {
      year: 2026, goal_km: 1000, milestones: [], start_date: null, phase: 'challenge',
      users: [
        { user_id: 1, display_name: 'Erik', avatar: 'icon:laufen', rank: 1, total_scaled_km: 300, total_real_km: 300, km_factor: 1,
          by_category: [], segments: [], cumulative: [{ date: '2026-01-01', scaled_km: 300, real_km: 300 }] },
      ],
    }
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <JahresVerlauf data={zwei} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('link', { name: 'Profil von Erik' })).toHaveTextContent('i')
  })
})
