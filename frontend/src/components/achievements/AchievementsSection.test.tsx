import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Achievement } from '../../api/client'
import AchievementsSection from './AchievementsSection'

const base = {
  hidden: false,
  tier: null,
  discipline: null,
  unlocked_at: null,
  emoji: null,
  showcased: null,
  claimed_by: null,
} satisfies Partial<Achievement>

const FIXTURES: Achievement[] = [
  {
    ...base,
    key: 'startschuss', title: 'Startschuss', description: 'Deine erste Aktivität ist im Kasten.',
    icon: 'fahne', achieved: true, progress: 1,
    parts: [{ label: 'Gesamt', current_km: 0.01, target_km: 0.01 }],
  },
  {
    ...base,
    key: 'ironman', title: 'Ironman', description: '190 km Rad, 42 km Laufen und 4 km Schwimmen — die volle Distanz.',
    icon: 'pokal', achieved: false, progress: 0.5,
    parts: [
      { label: 'Rad', current_km: 95, target_km: 190 },
      { label: 'Laufen', current_km: 30, target_km: 42 },
      { label: 'Schwimmen', current_km: 2, target_km: 4 },
    ],
  },
  { ...base, key: 'stufe_rad_bronze', title: 'Rad Bronze', description: '1000 km Rad insgesamt.', icon: 'rad',
    achieved: true, progress: 1, parts: [{ label: 'Rad', current_km: 1000, target_km: 1000 }],
    tier: 'bronze', discipline: 'rad', unlocked_at: '2026-08-01T10:00:00Z' },
  { ...base, key: 'stufe_rad_silber', title: 'Rad Silber', description: '2500 km Rad insgesamt.', icon: 'rad',
    achieved: false, progress: 0.5, parts: [{ label: 'Rad', current_km: 1250, target_km: 2500 }],
    tier: 'silber', discipline: 'rad' },
  { ...base, key: 'stufe_rad_gold', title: 'Rad Gold', description: '4000 km Rad insgesamt.', icon: 'rad',
    achieved: false, progress: 0.3125, parts: [{ label: 'Rad', current_km: 1250, target_km: 4000 }],
    tier: 'gold', discipline: 'rad' },
  { ...base, key: 'erster_gold_rad', title: 'Erster: Rad Gold', description: 'Bekommt nur, wer die Gold-Stufe Rad als erste Person knackt.', icon: 'rad',
    achieved: false, progress: 0, parts: [], emoji: '🚴', claimed_by: 'Lisa' },
  { ...base, key: 'fruehstarter', title: 'Frühstarter', description: 'Über 100 MM in der Warm-up-Phase getrackt.', icon: 'medaille',
    achieved: false, progress: 0.5, parts: [{ label: 'Warm-up', current_km: 50, target_km: 100 }], emoji: '🔥' },
  { ...base, key: 'early_bird', title: 'Early Bird', description: 'Schon am ersten Tag der Saison eine Aktivität eingetragen.', icon: 'fahne',
    achieved: false, progress: 0, parts: [], emoji: '🐦' },
  { ...base, key: 'zeit_an_der_spitze', title: 'Zeit an der Spitze', description: 'Deine Gesamtzeit als alleiniger Platz 1 der Saison.', icon: 'pokal',
    achieved: true, progress: 1, parts: [], timer_hours: 60, timer_running: true },
  { ...base, key: 'kletterkoenig', title: '???', description: '', icon: 'medaille',
    achieved: false, progress: 0, parts: [], hidden: true },
  { ...base, key: 'hattrick', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.', icon: 'blitz',
    achieved: true, progress: 1, parts: [], hidden: true, unlocked_at: '2026-08-02T10:00:00Z', emoji: '🎩', showcased: true },
]

describe('AchievementsSection', () => {
  it('shows achieved and open achievements with progress', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Startschuss')).toBeInTheDocument()
    expect(screen.getByText('Ironman')).toBeInTheDocument()
    expect(screen.getByText(/Rad: 95\/190 km/)).toBeInTheDocument()
    expect(screen.queryByText(/Gesamt: 0\/0 km/)).not.toBeInTheDocument()
  })

  it('groups tiers into one card per discipline', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Rad')).toBeInTheDocument()
    expect(screen.getByText('Bronze')).toBeInTheDocument()
    expect(screen.getByText('Gold')).toBeInTheDocument()
    expect(screen.queryByText('Rad Silber')).not.toBeInTheDocument()
  })

  it('shows claimed one-time achievements with the owner name', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText(/vergeben an Lisa/)).toBeInTheDocument()
  })

  it('shows Frühstarter with warm-up progress instead of the race hint', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Frühstarter')).toBeInTheDocument()
    expect(screen.getByText(/50\/100 MM/)).toBeInTheDocument()
    expect(screen.queryByText(/bekommt nur die erste Person/)).not.toBeInTheDocument()
  })

  it('shows time at the top as a timer, in days from 24 h', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Zeit an der Spitze')).toBeInTheDocument()
    expect(screen.getByText(/2,5 Tage/)).toBeInTheDocument()
  })

  it('never renders locked hidden achievements, only unlocked ones', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.queryByText('???')).not.toBeInTheDocument()
    expect(screen.queryByText(/Verstecktes Achievement/)).not.toBeInTheDocument()
    expect(screen.getByText('Hattrick')).toBeInTheDocument()
    expect(screen.getAllByText('🎩').length).toBeGreaterThan(0)
  })

  it('offers the showcase toggle only when onToggle is given', () => {
    const onToggle = vi.fn()
    const { unmount } = render(<AchievementsSection achievements={FIXTURES} onToggle={onToggle} />)
    fireEvent.click(screen.getByRole('button', { name: /wird getragen/ }))
    expect(onToggle).toHaveBeenCalledWith(expect.objectContaining({ key: 'hattrick' }))
    unmount()
    render(<AchievementsSection achievements={FIXTURES} />)
    expect(screen.queryByRole('button', { name: /wird getragen/ })).not.toBeInTheDocument()
  })

  it('says so when the list is empty', () => {
    render(<AchievementsSection achievements={[]} />)
    expect(screen.getByText(/Noch keine Achievements/)).toBeInTheDocument()
  })
})
