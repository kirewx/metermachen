import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { CategoryShare, Comparison, ComparisonUser } from '../api/client'
import Profil from './Profil'

function kat(id: number, name: string, icon: string, km: number): CategoryShare {
  return { category_id: id, name, color: '#123456', icon, scaled_km: km, real_km: km / 2 }
}

function person(
  id: number,
  display_name: string,
  cats: CategoryShare[],
  hm = 0,
): ComparisonUser {
  return {
    user_id: id,
    display_name,
    avatar: 'icon:laufen',
    rank: id,
    total_scaled_km: cats.reduce((s, c) => s + c.scaled_km, 0),
    total_real_km: cats.reduce((s, c) => s + c.real_km, 0),
    total_elevation_m: hm,
    km_factor: 1,
    by_category: cats,
    segments: [],
    cumulative: [],
    elevation_by_month: [],
    emojis: ['🎩'],
    auszeichnungen: [
      { emoji: '🎩', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.' },
    ],
  }
}

const kira = person(
  1,
  'Kira',
  [kat(2, 'Radfahren', 'rad', 600), kat(4, 'Wandern', 'wandern', 300), kat(1, 'Joggen', 'laufen', 100)],
  2000, // unter der Bergziegen-Schwelle — hier soll der Rad-Schwerpunkt gewinnen
)
const erik = person(2, 'Erik', [kat(3, 'Schwimmen', 'schwimmen', 500)], 100)

const daten: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  users: [kira, erik],
  start_date: null,
  phase: 'challenge',
  elevation_months: [],
}

vi.mock('../api/client', () => ({
  api: {
    me: vi.fn().mockResolvedValue({
      id: 2, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false,
    }),
    seasons: vi.fn().mockResolvedValue([
      { id: 1, year: 2026, goal_km: 1000, milestones: [], start_date: null, end_date: null },
    ]),
    // Lazy: vi.mock wird hochgezogen, `daten` gibt es erst danach.
    comparison: vi.fn(() => Promise.resolve(daten)),
    categories: vi.fn().mockResolvedValue([
      { id: 2, name: 'Radfahren', factor: 1, color: '#00f', icon: 'rad', default_km: 20, is_active: true, strava_sport_types: [] },
    ]),
    userActivities: vi.fn().mockResolvedValue([
      { id: 7, category_id: 2, date: '2026-03-01', distance_km: 40, duration_min: null, start_time: null, elevation_m: 780, note: 'Feierabendrunde', scaled_km: 40, edited: false, source: 'manual', strava_url: null },
    ]),
    achievements: vi.fn().mockResolvedValue([
      { key: 'hattrick', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.', icon: 'blitz',
        achieved: true, progress: 1, parts: [], hidden: true, tier: null, discipline: null,
        unlocked_at: '2026-08-02T10:00:00Z', emoji: '🎩', showcased: true, claimed_by: null },
    ]),
    userAchievements: vi.fn().mockResolvedValue([
      { key: 'startschuss', title: 'Startschuss', description: 'Deine erste Aktivität ist im Kasten.',
        icon: 'fahne', achieved: true, progress: 1, parts: [{ label: 'Gesamt', current_km: 0.01, target_km: 0.01 }],
        hidden: false, tier: null, discipline: null, unlocked_at: null, emoji: null, showcased: null, claimed_by: null },
    ]),
    patchAchievement: vi.fn().mockResolvedValue({}),
    stravaStatus: vi.fn().mockResolvedValue({ enabled: false, connected: false }),
    patchMe: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderProfil(pfad = '/profil/1?jahr=2026') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[pfad]}>
        <Routes>
          <Route path="/profil/:userId" element={<Profil />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Profilseite', () => {
  it('zeigt Name, Platz und den abgeleiteten Sportler-Typ', async () => {
    renderProfil()
    expect(await screen.findByText('Kira')).toBeInTheDocument()
    expect(screen.getByText(/Platz 1 · Saison 2026/)).toBeInTheDocument()
    // 600 von 1000 MM im Sattel → Kilometerfresser
    expect(screen.getByText(/KILOMETERFRESSER/)).toBeInTheDocument()
    expect(screen.getByText(/60 % der Meter im Sattel/)).toBeInTheDocument()
  })

  it('zeichnet das Spinnennetz mit den fünf Achsen', async () => {
    renderProfil()
    const netz = await screen.findByRole('img', { name: /Sportprofil von Kira/ })
    expect(netz).toBeInTheDocument()
    // Legende unter dem Netz: Kernachsen plus persönliche Spezialdisziplin
    for (const label of ['Laufen', 'Rad', 'Schwimmen', 'Höhe', 'Wandern'])
      expect(screen.getAllByText(label).length).toBeGreaterThan(0)
  })

  it('legt auf fremden Profilen das eigene Netz darüber und lässt es abschalten', async () => {
    renderProfil()
    const toggle = await screen.findByRole('button', { name: /Mit mir vergleichen/ })
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/Gestrichelt: Erik/)).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByText(/Gestrichelt: Erik/)).not.toBeInTheDocument()
  })

  it('bietet auf dem eigenen Profil keinen Vergleich mit sich selbst an', async () => {
    renderProfil('/profil/2?jahr=2026')
    expect(await screen.findByText('Erik')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Mit mir vergleichen/ })).not.toBeInTheDocument()
  })

  it('zeigt Kennzahlen, Sportarten und die letzten Aktivitäten', async () => {
    renderProfil()
    expect(await screen.findByText('1000 MM')).toBeInTheDocument()
    expect(screen.getByText('2.000 m')).toBeInTheDocument()
    expect(await screen.findByText(/Feierabendrunde/)).toBeInTheDocument()
    expect(screen.getByText(/780 hm/)).toBeInTheDocument()
  })

  it('zeigt die Auszeichnungen der Person', async () => {
    renderProfil()
    fireEvent.click(await screen.findByText('🎩'))
    expect(screen.getByText('Hattrick')).toBeInTheDocument()
  })

  it('erklärt es, wenn es die Person in dieser Saison nicht gibt', async () => {
    renderProfil('/profil/99?jahr=2026')
    expect(await screen.findByText(/Dieses Mitglied gibt es/)).toBeInTheDocument()
  })

  it("shows another member's unlocked achievements without toggles or settings", async () => {
    renderProfil()
    expect(await screen.findByText('Startschuss')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /wird getragen/ })).not.toBeInTheDocument()
    expect(screen.queryByText('Einstellungen')).not.toBeInTheDocument()
  })

  it('shows the own trophy room with toggles and the settings section', async () => {
    renderProfil('/profil/2?jahr=2026')
    expect(await screen.findByText('Hattrick')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /wird getragen/ })).toBeInTheDocument()
    expect(await screen.findByLabelText('Anzeigename')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Logout/ })).toBeInTheDocument()
  })
})
