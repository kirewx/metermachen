import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { Challenge, ChallengeGroup, ChallengeStanding } from '../../api/client'
import ChallengeRennen from './ChallengeRennen'
import { statusText } from './challengeStatus'

function s(user_id: number, display_name: string, value: number, rank: number, over: Partial<ChallengeStanding> = {}): ChallengeStanding {
  return { user_id, display_name, avatar: '🦊', value, rank, geschafft: false, nicht_mehr_schaffbar: false, ...over }
}

function g(id: number, name: string, value: number, rank: number, members: ChallengeStanding[], color?: string): ChallengeGroup {
  return { id, name, color, size: members.length, sum: value * members.length, value, rank, geschafft: false, members }
}

function challenge(over: Partial<Challenge>): Challenge {
  return {
    id: 7, title: 'Dezember-Duell', description: '', prize: null, creator_id: 1,
    mode: 'rangliste', target: null, top_n: 1, metric: 'mm', category_ids: [],
    streak_min_mm: 5, join_mode: 'auto', period_start: '2026-12-01', period_end: '2026-12-31',
    status: 'laufend', vorlaeufig: true, bin_dabei: true, kann_beitreten: false,
    standings: [], mein_stand: null, gewinner_ids: [], sieger_id: null, kann_sieger_setzen: false,
    team_mode: false, group_count: null, seeding_days: 30, groups_drawn: false, groups: [],
    unassigned: [], meine_gruppe_id: null, sieger_group_id: null, kann_gruppen_bearbeiten: false,
    created_at: '2026-11-01T10:00:00Z', resolved_at: null,
    ...over,
  }
}

const mount = (ch: Challenge) =>
  render(
    <MemoryRouter>
      <ChallengeRennen ch={ch} today={new Date(2026, 11, 20)} />
    </MemoryRouter>,
  )

const anna = s(1, 'Anna', 151, 1)
const erik = s(2, 'Erik', 142, 2)
const tom = s(3, 'Tom', 103, 3)
const mia = s(4, 'Mia', 88, 4)

describe('ChallengeRennen', () => {
  it('shows a tug of war for two teams and tints the lanes in team colours', () => {
    mount(challenge({
      team_mode: true, group_count: 2, groups_drawn: true,
      standings: [anna, erik, tom, mia],
      groups: [g(1, 'Team Blau', 115, 2, [erik, mia], '#60a5fa'), g(2, 'Team Pink', 127, 1, [anna, tom], '#f472b6')],
    }))
    expect(screen.getByTestId('tauziehen')).toBeInTheDocument()
    expect(screen.getByText('Team Blau')).toBeInTheDocument()
    const bahnen = screen.getAllByTestId('challenge-bahn')
    expect(bahnen.map((b) => b.textContent)).toEqual([
      expect.stringContaining('Anna'), expect.stringContaining('Erik'),
      expect.stringContaining('Tom'), expect.stringContaining('Mia'),
    ])
    // Erik is in Team Blau: faint blue row background (#60a5fa at 8 %).
    expect(bahnen[1].getAttribute('style')).toContain('rgba(96, 165, 250, 0.08')
  })

  it('ranks three or more teams instead of a tug of war', () => {
    const ben = s(5, 'Ben', 126, 3)
    mount(challenge({
      team_mode: true, group_count: 3, groups_drawn: true,
      standings: [anna, erik, ben, tom, mia],
      groups: [
        g(1, 'Blau', 115, 2, [erik, mia]), g(2, 'Pink', 127, 1, [anna, tom]), g(3, 'Orange', 126, 3, [ben]),
      ],
    }))
    expect(screen.queryByTestId('tauziehen')).toBeNull()
    expect(screen.getAllByTestId('teamzeile').map((z) => z.textContent)).toEqual([
      expect.stringContaining('Pink'), expect.stringContaining('Blau'), expect.stringContaining('Orange'),
    ])
  })

  it('shows goal, qualifiers and prize when everybody plays for themselves', () => {
    mount(challenge({
      mode: 'ziel', target: 120, prize: 'Kuchen',
      standings: [
        s(1, 'Anna', 151, 1, { geschafft: true }), s(2, 'Erik', 142, 2, { geschafft: true }),
        s(4, 'Mia', 10, 3, { nicht_mehr_schaffbar: true }),
      ],
    }))
    expect(screen.getByText('120 MM')).toBeInTheDocument()
    expect(screen.getByText('2 von 3')).toBeInTheDocument()
    expect(screen.getByText('Kuchen')).toBeInTheDocument()
    expect(screen.getAllByText('✓')).toHaveLength(2)
    expect(screen.getAllByTitle('Ziel 120')).toHaveLength(3) // one goal line per lane
    expect(screen.getAllByTestId('challenge-bahn')[2].className).toContain('opacity-55')
  })

  it('names the leader in ranking mode', () => {
    mount(challenge({ standings: [anna, erik] }))
    expect(screen.getByText('führt')).toBeInTheDocument()
    expect(screen.getAllByText('Anna').length).toBeGreaterThan(1)
  })
})

describe('statusText', () => {
  const ch = challenge({ period_end: '2026-12-31' })
  it('counts the remaining days including today', () => {
    expect(statusText(ch, new Date(2026, 11, 20))).toBe('läuft · noch 12 Tage')
    expect(statusText(ch, new Date(2026, 11, 31))).toBe('läuft · letzter Tag')
  })
  it('says Endstand once finished', () => {
    expect(statusText({ ...ch, status: 'beendet' }, new Date(2027, 0, 5))).toBe('Endstand')
  })
})
