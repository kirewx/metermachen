import { describe, expect, it } from 'vitest'
import { defaultMonth, isFinishedMonth, monthKey, monthLabel, showsSeasonTargets } from './period'

const today = new Date(2026, 8, 19) // 19 Sep 2026

describe('period helpers', () => {
  it('monthKey formats a date as YYYY-MM', () => {
    expect(monthKey(today)).toBe('2026-09')
    expect(monthKey(new Date(2027, 0, 1))).toBe('2027-01')
  })

  it('defaultMonth prefers the current month', () => {
    expect(defaultMonth(['2026-07', '2026-08', '2026-09'], today)).toBe('2026-09')
  })

  it('defaultMonth falls back to the last month of a past season', () => {
    expect(defaultMonth(['2025-07', '2025-08'], today)).toBe('2025-08')
  })

  it('defaultMonth is null without months', () => {
    expect(defaultMonth([], today)).toBeNull()
  })

  it('monthLabel uses German short names', () => {
    expect(monthLabel('2026-09')).toBe('Sep 2026')
    expect(monthLabel('2027-03')).toBe('Mär 2027')
  })

  it('isFinishedMonth is true only for months before the current one', () => {
    expect(isFinishedMonth('2026-08', today)).toBe(true)
    expect(isFinishedMonth('2026-09', today)).toBe(false)
    expect(isFinishedMonth('2026-10', today)).toBe(false)
  })

  it('showsSeasonTargets only for the whole season in MM', () => {
    expect(showsSeasonTargets(null, 'mm')).toBe(true)
    expect(showsSeasonTargets(undefined, 'mm')).toBe(true)
    expect(showsSeasonTargets('2026-09', 'mm')).toBe(false)
    expect(showsSeasonTargets(null, 'km')).toBe(false)
  })
})
