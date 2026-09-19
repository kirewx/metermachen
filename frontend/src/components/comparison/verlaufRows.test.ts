import { describe, expect, it } from 'vitest'
import type { Comparison } from '../../api/client'
import { verlaufRows } from './verlaufRows'

const user = (id: number, name: string, points: [string, number][]) => ({
  user_id: id,
  display_name: name,
  avatar: 'icon:laufen',
  rank: id,
  total_scaled_km: points.at(-1)?.[1] ?? 0,
  total_real_km: 0,
  km_factor: 1,
  by_category: [],
  segments: [],
  cumulative: points.map(([date, scaled_km]) => ({ date, scaled_km, real_km: scaled_km / 2, elevation_m: 0 })),
  elevation_by_month: [],
})

const base = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  start_date: '2026-07-10',
  phase: 'challenge',
  months: ['2026-07', '2026-08', '2026-09'],
}

describe('verlaufRows', () => {
  it('merges the curves into one row per date, without an anchor in year mode', () => {
    const data = {
      ...base,
      month: null,
      users: [user(1, 'Erik', [['2026-09-12', 35]]), user(2, 'Lisa', [['2026-09-12', 10], ['2026-09-14', 20]])],
    } as Comparison
    expect(verlaufRows(data, 'mm')).toEqual([
      { date: '2026-09-12', Erik: 35, Lisa: 10 },
      { date: '2026-09-14', Lisa: 20 },
    ])
  })

  it('starts every month curve at zero on the 1st', () => {
    const data = { ...base, month: '2026-09', users: [user(1, 'Erik', [['2026-09-12', 35]])] } as Comparison
    expect(verlaufRows(data, 'mm')).toEqual([
      { date: '2026-09-01', Erik: 0 },
      { date: '2026-09-12', Erik: 35 },
    ])
  })

  it('keeps a real value logged on the anchor day and skips people without meters', () => {
    const data = {
      ...base,
      month: '2026-09',
      users: [user(1, 'Erik', [['2026-09-01', 8]]), user(2, 'Lisa', [['2026-09-03', 5]]), user(3, 'Mara', [])],
    } as Comparison
    expect(verlaufRows(data, 'mm')).toEqual([
      { date: '2026-09-01', Erik: 8, Lisa: 0 },
      { date: '2026-09-03', Lisa: 5 },
    ])
  })

  it('anchors a partial first month on the season start', () => {
    const data = { ...base, month: '2026-07', users: [user(1, 'Erik', [['2026-07-20', 12]])] } as Comparison
    expect(verlaufRows(data, 'km')[0]).toEqual({ date: '2026-07-10', Erik: 0 })
  })

  it('adds no anchor row to an empty month', () => {
    const data = { ...base, month: '2026-08', users: [user(1, 'Erik', [])] } as Comparison
    expect(verlaufRows(data, 'mm')).toEqual([])
  })
})
