import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Einladung from './Einladung'

const getInvite = vi.fn()
vi.mock('../api/client', () => ({
  api: { getInvite: () => getInvite(), acceptInvite: vi.fn() },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAt(token: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/einladung/${token}`]}>
        <Routes>
          <Route path="/einladung/:token" element={<Einladung />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => getInvite.mockReset())

describe('Einladung', () => {
  it('zeigt das Registrierungsformular bei gültigem Token', async () => {
    getInvite.mockResolvedValue({ valid: true, display_name: 'Lisa' })
    renderAt('abc')
    expect(await screen.findByLabelText('Benutzername')).toBeInTheDocument()
  })

  it('zeigt eine Fehlermeldung bei ungültigem Token', async () => {
    getInvite.mockResolvedValue({ valid: false })
    renderAt('weg')
    expect(await screen.findByText(/ungültig|abgelaufen|eingelöst/i)).toBeInTheDocument()
  })
})
