import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import SchnellwahlLeiste from './SchnellwahlLeiste'

vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      {
        id: 1, name: 'Joggen', factor: 4, color: '#fff',
        icon: 'laufen', default_km: 5, is_active: true,
      },
    ]),
    createActivity: vi.fn().mockResolvedValue({}),
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

  it('startet im sicheren Zustand mit nur einem Hinzufügen-Button', () => {
    renderLeiste()
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
  })

  it('Klick auf Hinzufügen öffnet die Schnellwahl-Karte', async () => {
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    expect(await screen.findByTestId('km-wert')).toBeInTheDocument()
  })

  it('Abbrechen klappt ohne Speichern zurück in den sicheren Zustand', async () => {
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    await screen.findByTestId('km-wert')
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
  })

  it('nach erfolgreichem Eintragen klappt die Leiste automatisch zurück', async () => {
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    await screen.findByTestId('km-wert')
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    await waitFor(() => expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
  })

  it('ohne geladene Kategorien bleibt der Trigger sichtbar (keine Sackgasse)', async () => {
    vi.mocked(api.categories).mockResolvedValueOnce([])
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
  })
})
