import { describe, expect, it } from 'vitest'
import type { Category } from '../../api/client'
import { factorOn, mmOn } from './factorOn'

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

describe('mmOn', () => {
  const laufen: Category = {
    id: 2, name: 'Laufen', factor: 4, base_factor: 4, color: '#f00', icon: 'laufen',
    default_km: 5, is_active: true, strava_sport_types: [], history: [], pending_changes: [],
    counts_elevation: true, base_counts_elevation: false,
    elevation_changes: [{ counts_elevation: true, valid_from: '2026-11-09' }],
  }

  it('counts 100 hm as 1 km from the cutover on', () => {
    expect(mmOn(laufen, '2026-11-09', 10, 500)).toBe(60)
    expect(mmOn(laufen, '2026-11-09', 0, 100)).toBe(4)
  })

  it('ignores hm before the cutover', () => {
    expect(mmOn(laufen, '2026-11-08', 10, 500)).toBe(40)
  })

  it('ignores hm from a later switch-off on, but not before it', () => {
    const aus = {
      ...laufen,
      elevation_changes: [
        ...laufen.elevation_changes!,
        { counts_elevation: false, valid_from: '2026-12-01' },
      ],
    }
    expect(mmOn(aus, '2026-11-30', 10, 500)).toBe(60)
    expect(mmOn(aus, '2026-12-01', 10, 500)).toBe(40)
  })
})
