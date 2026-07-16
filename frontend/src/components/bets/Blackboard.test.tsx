import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Bet } from '../../api/client'
import Blackboard, { filtereBlackboard } from './Blackboard'

const basis = {
  stake: 10, jackpot: 0, created_at: '2026-07-20T00:00:00Z', resolved_at: null,
  result: {}, standing: {}, my_role: null, participants: [] as Bet['participants'],
  period_start: '2026-08-01', period_end: '2026-08-31',
}

const bets: Bet[] = [
  { ...basis, id: 1, type: 'duell', creator_id: 1, title: 'Erik vs. Lisa',
    status: 'laufend', params: { opponent_id: 2 } },
  { ...basis, id: 2, type: 'ziel', creator_id: 2, title: 'Lisa schafft 100',
    status: 'offen', params: { target_km: 100 } },
  { ...basis, id: 3, type: 'duell', creator_id: 1, title: 'Alte Wette',
    status: 'entschieden', params: { opponent_id: 2 } },
]

const spieler = [
  { user_id: 1, display_name: 'Erik' },
  { user_id: 2, display_name: 'Lisa' },
]

describe('filtereBlackboard', () => {
  it('zeigt nur offene und laufende Wetten', () => {
    const r = filtereBlackboard(bets, { personId: null, typ: null })
    expect(r.map((b) => b.id)).toEqual([1, 2])
  })

  it('filtert nach Person (Ersteller, Duell-Gegner oder Teilnehmer)', () => {
    const r = filtereBlackboard(bets, { personId: 2, typ: null })
    expect(r.map((b) => b.id)).toEqual([1, 2])
    expect(filtereBlackboard(bets, { personId: 1, typ: null }).map((b) => b.id)).toEqual([1])
  })

  it('filtert nach Wett-Typ', () => {
    expect(filtereBlackboard(bets, { personId: null, typ: 'ziel' }).map((b) => b.id)).toEqual([2])
  })
})

describe('Blackboard', () => {
  it('zeigt Duelle als A ⚔️ B und filtert per Dropdown', async () => {
    render(<Blackboard bets={bets} spieler={spieler} />)
    expect(screen.getByText('Erik ⚔️ Lisa')).toBeInTheDocument()
    expect(screen.getByText('Lisa schafft 100')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Wett-Typ'), 'ziel')
    expect(screen.queryByText('Erik ⚔️ Lisa')).not.toBeInTheDocument()
    expect(screen.getByText('Lisa schafft 100')).toBeInTheDocument()
  })
})
