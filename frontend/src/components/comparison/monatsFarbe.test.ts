import { describe, expect, it } from 'vitest'
import {
  formatHm,
  monatsFarbe,
  monatsLabel,
  MONATS_FARBEN,
  sichtbareBerge,
  skalaMax,
} from './monatsFarbe'

describe('monatsFarbe', () => {
  const achse = ['2026-07', '2026-08', '2026-09']

  it('färbt nach der Position auf der Saison-Achse, nicht nach Kalendermonat', () => {
    expect(monatsFarbe('2026-07', achse)).toBe(MONATS_FARBEN[0])
    expect(monatsFarbe('2026-09', achse)).toBe(MONATS_FARBEN[2])
  })

  it('fällt auf die erste Farbe zurück, wenn der Monat nicht auf der Achse liegt', () => {
    expect(monatsFarbe('2026-01', achse)).toBe(MONATS_FARBEN[0])
  })

  it('wiederholt die Palette bei Saisons über zwölf Monate', () => {
    const lang = Array.from({ length: 14 }, (_, i) => `2026-${String(i + 1).padStart(2, '0')}`)
    expect(monatsFarbe(lang[12], lang)).toBe(MONATS_FARBEN[0])
  })
})

describe('monatsLabel', () => {
  it('zeigt Monat und Jahr, weil Saisons über die Jahresgrenze laufen', () => {
    expect(monatsLabel('2026-07')).toBe('Jul 26')
    expect(monatsLabel('2027-01')).toBe('Jan 27')
  })

  it('lässt unbekannte Werte unverändert', () => {
    expect(monatsLabel('kaputt')).toBe('kaputt')
  })
})

describe('sichtbareBerge', () => {
  it('blendet nur Berge ein, die unter dem Höchstwert liegen', () => {
    expect(sichtbareBerge(3000).map((b) => b.name)).toEqual(['Brocken', 'Zugspitze'])
  })

  it('zeigt ohne nennenswerte Höhenmeter gar keine Berge', () => {
    expect(sichtbareBerge(950)).toEqual([])
  })
})

describe('skalaMax', () => {
  it('nimmt den höchsten Wert, damit alles aufs Display passt', () => {
    expect(skalaMax([300, 4050, 900])).toBe(4050)
  })

  it('nutzt eine Ersatzskala statt null', () => {
    expect(skalaMax([])).toBe(1000)
    expect(skalaMax([0, 0])).toBe(1000)
  })
})

describe('formatHm', () => {
  it('rundet und gruppiert Tausender', () => {
    expect(formatHm(4050.4)).toBe('4.050')
  })
})
