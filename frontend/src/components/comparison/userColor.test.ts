import { describe, expect, it } from 'vitest'
import { USER_FARBEN, userColor } from './userColor'

describe('userColor', () => {
  it('vergibt Farben nach sortierter User-ID-Reihenfolge', () => {
    expect(userColor(3, [7, 3, 12])).toBe(USER_FARBEN[0])
    expect(userColor(7, [7, 3, 12])).toBe(USER_FARBEN[1])
    expect(userColor(12, [7, 3, 12])).toBe(USER_FARBEN[2])
  })

  it('ist unabhängig von der Reihenfolge des ID-Arrays', () => {
    expect(userColor(7, [12, 7, 3])).toBe(userColor(7, [3, 7, 12]))
  })

  it('wiederholt die Palette bei mehr Personen als Farben', () => {
    const ids = Array.from({ length: USER_FARBEN.length + 1 }, (_, i) => i + 1)
    expect(userColor(ids[ids.length - 1], ids)).toBe(USER_FARBEN[0])
  })

  it('liefert eine Fallback-Farbe für unbekannte IDs', () => {
    expect(userColor(99, [1, 2])).toBe(USER_FARBEN[0])
  })
})
