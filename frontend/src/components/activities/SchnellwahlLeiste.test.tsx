import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SchnellwahlLeiste from './SchnellwahlLeiste'

vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      {
        id: 1, name: 'Joggen', factor: 4, color: '#fff',
        icon: 'laufen', default_km: 5, is_active: true,
      },
    ]),
    createActivity: vi.fn(),
  },
}))

function renderLeiste() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SchnellwahlLeiste />
    </QueryClientProvider>,
  )
}

describe('SchnellwahlLeiste', () => {
  beforeEach(() => localStorage.clear())

  it('ist standardmäßig offen und zeigt die kompakte Schnellwahl', async () => {
    renderLeiste()
    expect(await screen.findByTestId('km-wert')).toBeInTheDocument()
  })

  it('einklappen versteckt die Karte und merkt sich den Zustand', async () => {
    renderLeiste()
    await screen.findByTestId('km-wert')
    await userEvent.click(screen.getByRole('button', { name: /Schnellwahl/ }))
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
    expect(localStorage.getItem('schnellwahl-leiste-offen')).toBe('zu')
  })

  it('startet eingeklappt, wenn zuletzt eingeklappt', () => {
    localStorage.setItem('schnellwahl-leiste-offen', 'zu')
    renderLeiste()
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
  })
})
