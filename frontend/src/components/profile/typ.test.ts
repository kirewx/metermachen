import { describe, expect, it } from 'vitest'
import type { CategoryShare, ComparisonUser } from '../../api/client'
import { profilAchsen } from './achsen'
import { bestimmeTyp, hoehenIntensitaet, median } from './typ'

function kat(id: number, name: string, icon: string, scaled_km: number): CategoryShare {
  return { category_id: id, name, color: '#123456', icon, scaled_km, real_km: scaled_km }
}

function person(id: number, cats: CategoryShare[], hm = 0): ComparisonUser {
  return {
    user_id: id,
    display_name: `P${id}`,
    avatar: 'icon:laufen',
    rank: id,
    total_scaled_km: cats.reduce((s, c) => s + c.scaled_km, 0),
    total_real_km: cats.reduce((s, c) => s + c.real_km, 0),
    total_elevation_m: hm,
    km_factor: 1,
    by_category: cats,
    segments: [],
    cumulative: [],
    elevation_by_month: [],
  }
}

/** Typ einer Person im Kontext ihrer Gruppe (Default: nur sie selbst). */
function typVon(u: ComparisonUser, gruppe: ComparisonUser[] = [u]) {
  return bestimmeTyp(u, gruppe, profilAchsen(u, gruppe))
}

const LAUF = (km: number) => kat(1, 'Joggen', 'laufen', km)
const RAD = (km: number) => kat(2, 'Radfahren', 'rad', km)
const SCHWIMM = (km: number) => kat(3, 'Schwimmen', 'schwimmen', km)
const WANDERN = (km: number) => kat(4, 'Wandern', 'wandern', km)

describe('median', () => {
  it('rechnet bei gerader Anzahl den Mittelwert der Mitte', () => {
    expect(median([1, 3])).toBe(2)
    expect(median([5, 1, 3])).toBe(3)
    expect(median([])).toBe(0)
  })
})

describe('hoehenIntensitaet', () => {
  it('misst Höhenmeter je 100 gewerteten MM', () => {
    expect(hoehenIntensitaet(person(1, [RAD(200)], 1000))).toBe(500)
    expect(hoehenIntensitaet(person(1, [], 1000))).toBe(0)
  })
})

describe('bestimmeTyp', () => {
  it('nennt Leute ohne nennenswerte Meter Frischling', () => {
    expect(typVon(person(1, [LAUF(10)])).label).toBe('Frischling')
  })

  it('erkennt den Schwerpunkt Schwimmen', () => {
    const typ = typVon(person(1, [SCHWIMM(60), LAUF(40)]))
    expect(typ.label).toBe('Wasserratte')
    expect(typ.satz).toContain('60 %')
  })

  it('erkennt den Schwerpunkt Rad', () => {
    expect(typVon(person(1, [RAD(80), LAUF(20)])).label).toBe('Kilometerfresser')
  })

  it('erkennt den Schwerpunkt Laufen', () => {
    expect(typVon(person(1, [LAUF(80), RAD(20)])).label).toBe('Laufmaschine')
  })

  it('macht aus drei ausgewogenen Kerndisziplinen eine Triathlon-Maschine', () => {
    expect(typVon(person(1, [LAUF(35), RAD(35), SCHWIMM(30)])).label).toBe('Triathlon-Maschine')
  })

  it('gibt Wandernden einen eigenen Namen', () => {
    expect(typVon(person(1, [WANDERN(80), LAUF(20)])).label).toBe('Gipfelstürmer')
  })

  it('nennt exotische Spezialdisziplinen Freigeist', () => {
    const typ = typVon(person(1, [kat(9, 'Bogenschießen', 'medaille', 90), LAUF(10)]))
    expect(typ.label).toBe('Freigeist')
    expect(typ.satz).toContain('Bogenschießen')
  })

  it('erkennt zwei gleich starke Disziplinen als Doppelspitze', () => {
    const typ = typVon(person(1, [LAUF(35), RAD(35), WANDERN(30)]))
    expect(typ.label).toBe('Doppelspitze')
  })

  it('nennt breit verteilte Profile Allrounder', () => {
    const u = person(1, [LAUF(25), RAD(25), WANDERN(25), kat(5, 'Tanzen', 'tanzen', 25)])
    // Schwimmen fehlt → kein Triathlon; Laufen/Rad bei je 25 % → keine Doppelspitze
    expect(typVon(u).label).toBe('Allrounder')
  })

  it('sticht mit auffällig vielen Höhenmetern jeden Sport-Schwerpunkt aus', () => {
    // Gleiche Sportverteilung wie die Kilometerfresserin, aber sehr bergig
    const flach = person(2, [RAD(1000)], 500)
    const bergig = person(1, [RAD(1000)], 20000)
    expect(typVon(bergig, [bergig, flach]).label).toBe('Bergziege')
    expect(typVon(flach, [bergig, flach]).label).toBe('Kilometerfresser')
  })

  it('macht aus wenigen Höhenmetern keine Bergziege, egal wie steil', () => {
    const steil = person(1, [RAD(100)], 2000) // unter der 3 000-hm-Schwelle
    const flach = person(2, [RAD(1000)], 10)
    expect(typVon(steil, [steil, flach]).label).toBe('Kilometerfresser')
  })
})
