import { describe, expect, it } from 'vitest'
import type { Category } from '../../api/client'
import { factorOn } from './factorOn'

const swimming: Category = {
  id: 1, name: 'Schwimmen', factor: 25, base_factor: 30, color: '#0af', icon: 'schwimmen',
  default_km: 2, is_active: true, strava_sport_types: [],
  history: [{ id: 1, factor: 25, valid_from: '2026-09-01' }],
  pending_changes: [{ id: 2, factor: 20, valid_from: '2026-10-01' }],
}

describe('factorOn', () => {
  it('uses the base factor before the first change', () => {
    expect(factorOn(swimming, '2026-08-31')).toBe(30)
  })

  it('switches on the cutover day itself', () => {
    expect(factorOn(swimming, '2026-09-01')).toBe(25)
    expect(factorOn(swimming, '2026-09-30')).toBe(25)
  })

  it('honours pending changes for dates on or after their cutover', () => {
    expect(factorOn(swimming, '2026-10-01')).toBe(20)
  })

  it('falls back to the current factor without a date or without change lists', () => {
    expect(factorOn(swimming, '')).toBe(25)
    const plain = { ...swimming, history: undefined, pending_changes: undefined } as unknown as Category
    expect(factorOn(plain, '2026-08-31')).toBe(25)
  })
})
