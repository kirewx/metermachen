import { describe, expect, it } from 'vitest'
import { challengeLaeuft, challengeStartMs, formatCountdown } from './countdown'

describe('countdown', () => {
  it('baut den Startzeitpunkt mit deutscher Sommerzeit (+02:00)', () => {
    expect(challengeStartMs('2026-07-20')).toBe(Date.parse('2026-07-20T00:00:00+02:00'))
  })

  it('formatiert Tage/Stunden/Minuten/Sekunden', () => {
    const start = Date.parse('2026-07-20T00:00:00+02:00')
    const now = Date.parse('2026-07-12T10:17:55+02:00')
    expect(formatCountdown(start - now)).toBe('7 T 13:42:05')
  })

  it('liefert null wenn vorbei', () => {
    expect(formatCountdown(-1)).toBeNull()
    expect(formatCountdown(0)).toBeNull()
  })

  it('challengeLaeuft: vor Start false, ab Start true, ohne Stichtag true', () => {
    const start = challengeStartMs('2026-07-20')
    expect(challengeLaeuft('2026-07-20', start - 1)).toBe(false)
    expect(challengeLaeuft('2026-07-20', start)).toBe(true)
    expect(challengeLaeuft(null)).toBe(true)
  })
})
