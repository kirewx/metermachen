import { describe, expect, it } from 'vitest'
import type { ComparisonUser } from '../../api/client'
import { nachbarschaft, nachHoehe, presetAuswahl } from './hoehenAuswahl'

function user(id: number, name: string, hm: number): ComparisonUser {
  return {
    user_id: id,
    display_name: name,
    avatar: 'icon:laufen',
    rank: id,
    total_scaled_km: 0,
    total_real_km: 0,
    total_elevation_m: hm,
    km_factor: 1,
    by_category: [],
    segments: [],
    cumulative: [],
    elevation_by_month: [],
  }
}

// Zehn Personen, absteigend 1000, 900, ... — „ich" steht auf Platz 6.
const feld = Array.from({ length: 10 }, (_, i) => user(i + 1, `P${i + 1}`, 1000 - i * 100))
const ICH = 6

describe('nachHoehe', () => {
  it('sortiert absteigend nach Höhenmetern', () => {
    const gemischt = [user(1, 'Klein', 100), user(2, 'Gross', 900)]
    expect(nachHoehe(gemischt).map((u) => u.display_name)).toEqual(['Gross', 'Klein'])
  })

  it('entscheidet Gleichstand über den Namen', () => {
    const gleich = [user(1, 'Zoe', 500), user(2, 'Anna', 500)]
    expect(nachHoehe(gleich).map((u) => u.display_name)).toEqual(['Anna', 'Zoe'])
  })
})

describe('nachbarschaft', () => {
  it('zeigt Führenden plus zwei Plätze über und unter mir', () => {
    const namen = nachbarschaft(feld, ICH).map((u) => u.display_name)
    expect(namen).toEqual(['P1', 'P4', 'P5', 'P6', 'P7', 'P8'])
  })

  it('doppelt den Führenden nicht, wenn er ohnehin im Fenster liegt', () => {
    const namen = nachbarschaft(feld, 2).map((u) => u.display_name)
    expect(namen).toEqual(['P1', 'P2', 'P3', 'P4'])
  })

  it('fällt ohne bekannte eigene Person auf das Spitzenfeld zurück', () => {
    expect(nachbarschaft(feld, null)).toHaveLength(5)
  })
})

describe('presetAuswahl', () => {
  it('wählt alle', () => {
    expect(presetAuswahl('alle', feld, ICH).size).toBe(10)
  })

  it('wählt nur mich', () => {
    expect([...presetAuswahl('ich', feld, ICH)]).toEqual([ICH])
  })

  it('wählt die Nachbarschaft', () => {
    expect(presetAuswahl('nachbarschaft', feld, ICH).size).toBe(6)
  })
})
