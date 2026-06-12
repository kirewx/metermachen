import { describe, expect, it } from 'vitest'
import { progressFraction, spreadBadges } from './pathMath'

describe('progressFraction', () => {
  it('berechnet den Anteil zum Ziel', () => {
    expect(progressFraction(250, 1000)).toBe(0.25)
  })
  it('kappt bei 1 wenn das Ziel überschritten ist', () => {
    expect(progressFraction(1500, 1000)).toBe(1)
  })
  it('ist 0 bei Ziel 0 oder negativer Distanz', () => {
    expect(progressFraction(100, 0)).toBe(0)
    expect(progressFraction(-5, 1000)).toBe(0)
  })
})

describe('spreadBadges', () => {
  it('lässt entfernte Punkte auf Ebene 0', () => {
    const lanes = spreadBadges([
      { id: 1, x: 0 },
      { id: 2, x: 500 },
    ], 60)
    expect(lanes.get(1)).toBe(0)
    expect(lanes.get(2)).toBe(0)
  })
  it('stapelt nahe Punkte auf verschiedene Ebenen', () => {
    const lanes = spreadBadges([
      { id: 1, x: 100 },
      { id: 2, x: 110 },
      { id: 3, x: 130 },
    ], 60)
    expect(new Set([lanes.get(1), lanes.get(2), lanes.get(3)]).size).toBe(3)
  })
})
