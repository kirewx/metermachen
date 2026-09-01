import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Arena from './Arena'

const addons = vi.fn()
vi.mock('../api/client', () => ({ api: { addons: () => addons() } }))

function renderArena(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/arena" element={<Arena />}>
            <Route path="challenges" element={<p>Challenges-Inhalt</p>} />
            <Route path="challenges/:id" element={<p>Detail-Inhalt</p>} />
            <Route path="wetten" element={<p>Wetten-Inhalt</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Arena', () => {
  it('shows both pills when both add-ons are active and marks the current one', async () => {
    addons.mockResolvedValue([
      { key: 'challenges', label: 'Challenges', active: true },
      { key: 'sidebets', label: 'Wetten', active: true },
    ])
    renderArena('/arena/wetten')
    const wetten = await screen.findByRole('link', { name: /Wetten/ })
    expect(wetten).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: /Challenges/ })).toHaveAttribute('href', '/arena/challenges')
    expect(screen.getByText('Wetten-Inhalt')).toBeInTheDocument()
  })

  it('hides the pill row when only one add-on is active', async () => {
    addons.mockResolvedValue([{ key: 'challenges', label: 'Challenges', active: true }])
    renderArena('/arena/challenges')
    expect(await screen.findByText('Challenges-Inhalt')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Challenges/ })).not.toBeInTheDocument()
  })

  it('keeps the Challenges pill active on a detail page', async () => {
    addons.mockResolvedValue([
      { key: 'challenges', label: 'Challenges', active: true },
      { key: 'sidebets', label: 'Wetten', active: true },
    ])
    renderArena('/arena/challenges/5')
    expect(await screen.findByRole('link', { name: /Challenges/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Detail-Inhalt')).toBeInTheDocument()
  })
})
