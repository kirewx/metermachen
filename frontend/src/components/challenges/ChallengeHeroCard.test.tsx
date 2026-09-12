import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Challenge, ChallengeStanding } from '../../api/client'
import ChallengeHeroCard from './ChallengeHeroCard'

function standing(user_id: number, display_name: string, value: number, rank: number): ChallengeStanding {
  return { user_id, display_name, avatar: '🦊', value, rank, geschafft: false, nicht_mehr_schaffbar: false }
}

const basis: Challenge = {
  id: 1, title: 'Oktober-Ziel', description: '', prize: null, creator_id: 1,
  mode: 'ziel', target: 300, top_n: 1, metric: 'mm', category_ids: [],
  streak_min_mm: 5, join_mode: 'auto',
  period_start: '2026-10-01', period_end: '2026-10-31',
  status: 'laufend', vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
  standings: [standing(1, 'Rick', 412, 1), standing(2, 'Mia', 187, 2), standing(3, 'Lea', 14, 3)],
  mein_stand: standing(2, 'Mia', 187, 2),
  gewinner_ids: [], sieger_id: null, kann_sieger_setzen: false,
  team_mode: false, group_count: null, seeding_days: 30, groups_drawn: false,
  groups: [], unassigned: [], meine_gruppe_id: null, sieger_group_id: null,
  kann_gruppen_bearbeiten: false,
  created_at: '2026-09-28T10:00:00Z', resolved_at: null,
}

const team: Challenge = {
  ...basis,
  team_mode: true, group_count: 2, groups_drawn: true, meine_gruppe_id: 2,
  groups: [
    { id: 1, name: 'Gruppe A', size: 2, sum: 300, value: 150, rank: 2, geschafft: false,
      members: [standing(1, 'Rick', 412, 1), standing(3, 'Lea', 14, 3)] },
    { id: 2, name: 'Gruppe B', size: 2, sum: 542, value: 271, rank: 1, geschafft: false,
      members: [standing(2, 'Mia', 187, 2)] },
  ],
}

function renderCard(ch: Challenge) {
  return render(
    <MemoryRouter>
      <ChallengeHeroCard ch={ch} />
    </MemoryRouter>,
  )
}

describe('ChallengeHeroCard', () => {
  it('shows the own value and rank among all players', () => {
    const { container } = renderCard(basis)
    expect(container).toHaveTextContent('187 / 300 MM')
    expect(screen.getByText('Platz 2 von 3')).toBeInTheDocument()
    expect(container).not.toHaveTextContent('pro Kopf')
  })

  it('shows the own group per head and its rank among the groups', () => {
    const { container } = renderCard(team)
    expect(container).toHaveTextContent('271 / 300 MM pro Kopf')
    expect(screen.getByText('Gruppe B · Platz 1 von 2')).toBeInTheDocument()
  })

  it('falls back to the personal standing while the groups are not drawn', () => {
    const { container } = renderCard({ ...team, groups_drawn: false, groups: [], meine_gruppe_id: null })
    expect(container).toHaveTextContent('187 / 300 MM')
    expect(screen.getByText('Platz 2 von 3')).toBeInTheDocument()
  })
})
