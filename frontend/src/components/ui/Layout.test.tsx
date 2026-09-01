import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import Layout from './Layout'

vi.mock('../../api/client', () => ({
  api: {
    seasons: vi.fn().mockResolvedValue([]),
    addons: vi.fn().mockResolvedValue([{ key: 'sidebets', label: 'Wetten', active: true }]),
    feedUnseen: vi.fn().mockResolvedValue({ has_new: false }),
  },
}))

const member: Me = { id: 2, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

function renderLayout(me: Me) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<Layout me={me} />}>
            <Route path="/" element={<p>Inhalt</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Layout', () => {
  it('links the avatar to the own profile and has no logout button', async () => {
    renderLayout(member)
    expect(await screen.findByRole('link', { name: /Mein Profil/ })).toHaveAttribute('href', '/profil/2')
    expect(screen.queryByRole('button', { name: /Logout/ })).not.toBeInTheDocument()
  })

  it('shows the gear only for admins', async () => {
    const { unmount } = renderLayout(member)
    await screen.findByText('Inhalt')
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
    unmount()
    renderLayout({ ...member, is_admin: true })
    expect(await screen.findByRole('link', { name: 'Admin' })).toHaveAttribute('href', '/admin')
  })

  it('renders the new tabs and the Regeln footer link', async () => {
    renderLayout(member)
    expect((await screen.findAllByText('MyMeters')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Arena')).length).toBeGreaterThan(0)
    expect(screen.queryByText('Aktivitäten')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Regeln' })).toHaveAttribute('href', '/regeln')
  })
})
