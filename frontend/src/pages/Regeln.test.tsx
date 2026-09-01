import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import Regeln from './Regeln'

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Schwimmen', factor: 25, base_factor: 30, color: '#0af', icon: 'schwimmen', default_km: 1, is_active: true, strava_sport_types: [],
        pending_changes: [{ id: 9, factor: 20, valid_from: '2026-10-01' }], history: [] },
      { id: 2, name: 'Laufen', factor: 4, base_factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: [],
        pending_changes: [], history: [] },
    ]),
    addons: vi.fn().mockResolvedValue([]),
  },
}))

function renderRegeln() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Regeln />
    </QueryClientProvider>,
  )
}

describe('Regeln Faktor-Tabelle', () => {
  it('zeigt den heute gültigen Faktor und kündigt Änderungen an', async () => {
    renderRegeln()
    expect(await screen.findByText('×25')).toBeInTheDocument()
    expect(screen.getByText('ab 01.10.2026: ×20')).toBeInTheDocument()
  })

  it('zeigt ohne anstehende Änderung keinen Hinweis', async () => {
    renderRegeln()
    expect(await screen.findByText('×4')).toBeInTheDocument()
    expect(screen.getAllByText(/^ab \d\d\./)).toHaveLength(1)
  })
})
