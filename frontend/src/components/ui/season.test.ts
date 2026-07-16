import { describe, expect, it } from 'vitest'
import type { Season } from '../../api/client'
import { aktiveSeason, saisonLabel } from './season'

const s = (over: Partial<Season>): Season => ({
  id: 1,
  year: 2026,
  goal_km: 1000,
  milestones: [],
  start_date: null,
  end_date: null,
  ...over,
})

const ts = (iso: string) => Date.parse(`${iso}T12:00:00`)

describe('aktiveSeason', () => {
  it('findet die jahresübergreifende Season im Februar 2027', () => {
    const seasons = [s({ start_date: '2026-07-20', end_date: '2027-05-16' })]
    expect(aktiveSeason(seasons, ts('2027-02-01'))?.year).toBe(2026)
  })

  it('nach dem Ende: die zuletzt begonnene Season', () => {
    const seasons = [s({ start_date: '2026-07-20', end_date: '2027-05-16' })]
    expect(aktiveSeason(seasons, ts('2027-06-01'))?.year).toBe(2026)
  })

  it('ohne Start/Ende: Kalenderjahr-Verhalten', () => {
    const seasons = [s({ year: 2025 }), s({ id: 2, year: 2026 })]
    expect(aktiveSeason(seasons, ts('2026-03-01'))?.year).toBe(2026)
    expect(aktiveSeason(seasons, ts('2025-03-01'))?.year).toBe(2025)
  })

  it('vor allen Fenstern: die als Nächstes beginnende', () => {
    const seasons = [s({ year: 2028, start_date: '2028-07-20' })]
    expect(aktiveSeason(seasons, ts('2027-12-01'))?.year).toBe(2028)
  })

  it('leere Liste: undefined', () => {
    expect(aktiveSeason([], ts('2026-01-01'))).toBeUndefined()
  })
})

describe('saisonLabel', () => {
  it('nur Jahr, wenn das Ende nicht jahresübergreifend ist', () => {
    expect(saisonLabel(s({}))).toBe('2026')
    expect(saisonLabel(s({ end_date: '2026-12-31' }))).toBe('2026')
  })

  it('Saison 2026/27 bei Ende im Folgejahr', () => {
    expect(saisonLabel(s({ end_date: '2027-05-16' }))).toBe('Saison 2026/27')
  })

  it('undefined: aktuelles Kalenderjahr', () => {
    expect(saisonLabel(undefined)).toBe(String(new Date().getFullYear()))
  })
})
