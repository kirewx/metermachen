import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import PasswortReset from './PasswortReset'

const resetPassword = vi.fn()
vi.mock('../api/client', () => ({
  api: {
    resetPassword: async (token: string, pw: string) => await resetPassword(token, pw),
  },
}))

function renderAt(token: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/passwort-reset/${token}`]}>
        <Routes>
          <Route path="/passwort-reset/:token" element={<PasswortReset />} />
          <Route path="/" element={<p>Startseite</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function ausfuellen(pw1: string, pw2: string) {
  fireEvent.change(screen.getByLabelText('Neues Passwort (min. 4 Zeichen)'), {
    target: { value: pw1 },
  })
  fireEvent.change(screen.getByLabelText('Passwort wiederholen'), {
    target: { value: pw2 },
  })
}

describe('PasswortReset', () => {
  it('setzt das Passwort und navigiert zur Startseite', async () => {
    resetPassword.mockResolvedValue({ id: 1, username: 'lisa' })
    renderAt('tok123')
    ausfuellen('neu1234', 'neu1234')
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))
    await waitFor(() => expect(resetPassword).toHaveBeenCalledWith('tok123', 'neu1234'))
    expect(await screen.findByText('Startseite')).toBeInTheDocument()
  })

  it('blockt ungleiche Passwörter ohne API-Aufruf', async () => {
    renderAt('tok123')
    ausfuellen('neu1234', 'anders99')
    expect(screen.getByRole('button', { name: 'Passwort setzen' })).toBeDisabled()
  })

  it('zeigt die Fehlermeldung des Servers an', async () => {
    resetPassword.mockImplementation(() =>
      Promise.reject(new Error('Link ungültig oder abgelaufen')),
    )
    renderAt('kaputt')
    ausfuellen('neu1234', 'neu1234')
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))
    expect(await screen.findByText('Link ungültig oder abgelaufen')).toBeInTheDocument()
  })
})
