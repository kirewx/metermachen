import { describe, expect, it } from 'vitest'
import type { Challenge, ChallengeGroup, ChallengeStanding } from '../../api/client'
import {
  gruppenKandidaten,
  mitgliederKandidaten,
  personenKandidaten,
  segmentAmZeiger,
  zielRotation,
  ziehe,
} from './gluecksrad'

const stand = (user_id: number, display_name: string, geschafft: boolean): ChallengeStanding => ({
  user_id, display_name, avatar: '🦊', value: 0, rank: 1, geschafft, nicht_mehr_schaffbar: false,
})

describe('ziehe', () => {
  it('bleibt im Bereich und nutzt die Zufallsquelle', () => {
    expect(ziehe(4, () => 0)).toBe(0)
    expect(ziehe(4, () => 7)).toBe(3)
    expect(ziehe(1, () => 123456)).toBe(0)
  })

  it('verwirft Werte aus dem unvollständigen letzten Block (kein Modulo-Bias)', () => {
    // 2^32 = 4294967296; bei n=3 ist 4294967295 der eine überzählige Wert.
    const werte = [4294967295, 5]
    expect(ziehe(3, () => werte.shift()!)).toBe(2)
  })

  it('wirft bei leerer Liste', () => {
    expect(() => ziehe(0)).toThrow()
  })
})

describe('zielRotation', () => {
  it('landet für jedes Segment genau auf diesem Segment', () => {
    for (const n of [1, 2, 3, 7, 12]) {
      for (let i = 0; i < n; i++) {
        for (const lage of [0, 0.5, 0.999]) {
          const r = zielRotation(i, n, 0, lage)
          expect(segmentAmZeiger(r, n)).toBe(i)
        }
      }
    }
  })

  it('dreht immer vorwärts und mindestens die geforderten Umdrehungen', () => {
    const start = 1234.5
    const r = zielRotation(2, 5, start, 0.5, 5)
    expect(r - start).toBeGreaterThanOrEqual(5 * 360)
    expect(r - start).toBeLessThan(6 * 360)
    expect(segmentAmZeiger(r, 5)).toBe(2)
  })
})

describe('Kandidaten', () => {
  const ch = {
    standings: [stand(1, 'Rick', true), stand(2, 'Mia', false)],
    groups: [
      { id: 1, name: 'Gruppe A', geschafft: true, members: [stand(1, 'Rick', true), stand(2, 'Mia', false)] },
      { id: 2, name: 'Gruppe B', geschafft: false, members: [stand(3, 'Lea', false)] },
    ],
  } as unknown as Challenge

  it('Personen: alle Teilnehmenden, wer es geschafft hat, ist vorgewählt', () => {
    expect(personenKandidaten(ch)).toEqual([
      { id: 1, label: 'Rick', avatar: '🦊', vorgewaehlt: true },
      { id: 2, label: 'Mia', avatar: '🦊', vorgewaehlt: false },
    ])
  })

  it('Gruppen: alle Gruppen, erfolgreiche vorgewählt', () => {
    expect(gruppenKandidaten(ch).map((k) => [k.label, k.vorgewaehlt])).toEqual([
      ['Gruppe A', true],
      ['Gruppe B', false],
    ])
  })

  it('Mitglieder der gezogenen Gruppe sind alle vorgewählt', () => {
    const g = ch.groups[0] as ChallengeGroup
    expect(mitgliederKandidaten(g).map((k) => [k.id, k.vorgewaehlt])).toEqual([
      [1, true],
      [2, true],
    ])
  })
})
