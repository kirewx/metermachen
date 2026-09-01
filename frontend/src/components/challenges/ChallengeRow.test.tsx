import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Challenge, ChallengeStanding } from '../../api/client'
import ChallengeRow from './ChallengeRow'

function standing(user_id: number, display_name: string, rank: number): ChallengeStanding {
  return { user_id, display_name, avatar: '🦊', value: 100 - rank, rank, geschafft: true, nicht_mehr_schaffbar: false }
}

function challenge(over: Partial<Challenge>): Challenge {
  return {
    id: 1, title: 'Juli-Sprint bis zum Stuttgartlauf', description: '', prize: null,
    creator_id: 1, mode: 'ziel', target: 100, top_n: 1, metric: 'mm',
    category_ids: [], streak_min_mm: 5, join_mode: 'auto',
    period_start: '2026-07-01', period_end: '2026-07-31', status: 'beendet',
    vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
    standings: [], mein_stand: null, gewinner_ids: [], sieger_id: null,
    kann_sieger_setzen: false, created_at: '2026-07-01T10:00:00Z', resolved_at: '2026-08-01T04:00:00Z',
    ...over,
  }
}

function renderRow(ch: Challenge) {
  return render(
    <MemoryRouter>
      <ChallengeRow ch={ch} />
    </MemoryRouter>,
  )
}

describe('ChallengeRow (finished)', () => {
  const three = [standing(1, 'Anna', 1), standing(2, 'Ben', 2), standing(3, 'Chris', 3)]

  it('shows the admin-set prize winner, not every qualifier', () => {
    renderRow(challenge({ standings: three, gewinner_ids: [1, 2, 3], sieger_id: 2 }))
    expect(screen.getByText('🏆 Ben')).toBeInTheDocument()
    expect(screen.queryByText(/Anna/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Chris/)).not.toBeInTheDocument()
  })

  it('keeps the title as a second line', () => {
    renderRow(challenge({ standings: three, gewinner_ids: [1, 2, 3], sieger_id: 2 }))
    expect(screen.getByText('Juli-Sprint bis zum Stuttgartlauf')).toBeInTheDocument()
  })

  it('treats a single qualifier as the winner even before the draw', () => {
    renderRow(challenge({ standings: [standing(2, 'Ben', 1)], gewinner_ids: [2] }))
    expect(screen.getByText('🏆 Ben')).toBeInTheDocument()
  })

  it('shows a count while a target challenge with several qualifiers waits for the draw', () => {
    renderRow(challenge({ standings: three, gewinner_ids: [1, 2, 3] }))
    expect(screen.getByText('3 × geschafft · Sieger offen')).toBeInTheDocument()
    expect(screen.queryByText(/Anna/)).not.toBeInTheDocument()
  })

  it('shows rank 1 for a ranking challenge with a top-3', () => {
    renderRow(challenge({ mode: 'rangliste', top_n: 3, standings: three, gewinner_ids: [3, 1, 2] }))
    expect(screen.getByText('🏆 Anna')).toBeInTheDocument()
  })

  it('says niemand when nobody qualified', () => {
    renderRow(challenge({ standings: three.map((s) => ({ ...s, geschafft: false })) }))
    expect(screen.getByText('niemand')).toBeInTheDocument()
  })
})

describe('ChallengeRow (planned)', () => {
  it('shows title and start date', () => {
    renderRow(challenge({ status: 'geplant', period_start: '2026-10-01', resolved_at: null }))
    expect(screen.getByText('Juli-Sprint bis zum Stuttgartlauf')).toBeInTheDocument()
    expect(screen.getByText('1.10.2026')).toBeInTheDocument()
  })
})
