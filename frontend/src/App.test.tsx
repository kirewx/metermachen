import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const me = vi.fn()
vi.mock('./api/client', () => ({
  api: {
    me: () => me(),
    addons: vi.fn().mockResolvedValue([
      { key: 'challenges', label: 'Challenges', active: true },
      { key: 'sidebets', label: 'Wetten', active: true },
    ]),
    seasons: vi.fn().mockResolvedValue([]),
    feedUnseen: vi.fn().mockResolvedValue({ has_new: false }),
  },
  isUnauthorized: () => false,
}))
vi.mock('./pages/Vergleich', () => ({ default: () => <p>Vergleich-Seite</p> }))
vi.mock('./pages/Feed', () => ({ default: () => <p>Feed-Seite</p> }))
vi.mock('./pages/MyMeters', () => ({ default: () => <p>MyMeters-Seite</p> }))
vi.mock('./pages/Challenges', () => ({ default: () => <p>Challenges-Seite</p> }))
vi.mock('./pages/Wetten', () => ({ default: () => <p>Wetten-Seite</p> }))
vi.mock('./pages/Admin', () => ({ default: () => <p>Admin-Seite</p> }))
vi.mock('./pages/Regeln', () => ({ default: () => <p>Regeln-Seite</p> }))
vi.mock('./pages/Profil', () => ({ default: () => <p>Profil-Seite</p> }))
vi.mock('./pages/Datenschutz', () => ({ default: () => <p>Datenschutz-Seite</p> }))
vi.mock('./pages/Login', () => ({ default: () => <p>Login-Seite</p> }))
vi.mock('./pages/Einladung', () => ({ default: () => <p>Einladung-Seite</p> }))
vi.mock('./pages/PasswortReset', () => ({ default: () => <p>Reset-Seite</p> }))
vi.mock('./components/challenges/ChallengeDetail', () => ({ default: () => <p>Detail-Seite</p> }))

const member = { id: 2, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => me.mockResolvedValue(member))

describe('App routes', () => {
  it('redirects /aktivitaeten to MyMeters', async () => {
    renderAt('/aktivitaeten')
    expect(await screen.findByText('MyMeters-Seite')).toBeInTheDocument()
  })

  it('redirects /wetten into the Arena', async () => {
    renderAt('/wetten')
    expect(await screen.findByText('Wetten-Seite')).toBeInTheDocument()
  })

  it('redirects /challenges/:id into the Arena detail', async () => {
    renderAt('/challenges/7')
    expect(await screen.findByText('Detail-Seite')).toBeInTheDocument()
  })

  it('/arena lands on challenges', async () => {
    renderAt('/arena')
    expect(await screen.findByText('Challenges-Seite')).toBeInTheDocument()
  })

  it('sends non-admins from /admin home and lets admins in', async () => {
    const first = renderAt('/admin')
    expect(await screen.findByText('Vergleich-Seite')).toBeInTheDocument()
    first.unmount()
    me.mockResolvedValue({ ...member, is_admin: true })
    renderAt('/admin')
    expect(await screen.findByText('Admin-Seite')).toBeInTheDocument()
  })
})
