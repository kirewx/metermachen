import { describe, expect, it } from 'vitest'
import type { CategoryShare, ComparisonUser } from '../../api/client'
import { disziplin, kernSummen, profilAchsen, spezialKategorie, verbreitetsteSpezial } from './achsen'

function kat(
  category_id: number,
  name: string,
  icon: string,
  scaled_km: number,
): CategoryShare {
  return { category_id, name, color: '#123456', icon, scaled_km, real_km: scaled_km }
}

function person(
  user_id: number,
  by_category: CategoryShare[],
  total_elevation_m = 0,
): ComparisonUser {
  return {
    user_id,
    display_name: `P${user_id}`,
    avatar: 'icon:laufen',
    rank: user_id,
    total_scaled_km: by_category.reduce((s, c) => s + c.scaled_km, 0),
    total_real_km: by_category.reduce((s, c) => s + c.real_km, 0),
    total_elevation_m,
    km_factor: 1,
    by_category,
    segments: [],
    cumulative: [],
    elevation_by_month: [],
  }
}

describe('disziplin', () => {
  it('ordnet über das Icon zu — wie bucket_for_category im Backend', () => {
    expect(disziplin({ icon: 'laufen', name: 'Joggen' })).toBe('lauf')
    expect(disziplin({ icon: 'rad', name: 'Radfahren' })).toBe('rad')
    expect(disziplin({ icon: 'schwimmen', name: 'Schwimmen' })).toBe('schwimm')
  })

  it('fällt auf den Namen zurück, wenn das Icon nichts verrät', () => {
    expect(disziplin({ icon: 'medaille', name: 'Mountainbike' })).toBe('rad')
    expect(disziplin({ icon: 'medaille', name: 'Nachtlauf' })).toBe('lauf')
  })

  it('lässt Nebensportarten ohne Disziplin', () => {
    expect(disziplin({ icon: 'wandern', name: 'Wandern' })).toBeNull()
    expect(disziplin({ icon: 'tanzen', name: 'Tanzen' })).toBeNull()
  })
})

describe('kernSummen', () => {
  it('summiert mehrere Kategorien derselben Disziplin', () => {
    const u = person(1, [kat(1, 'Joggen', 'laufen', 60), kat(2, 'Laufen', 'laufen', 40)])
    expect(kernSummen(u)).toEqual({ lauf: 100, rad: 0, schwimm: 0 })
  })
})

describe('profilAchsen', () => {
  const anna = person(1, [kat(1, 'Joggen', 'laufen', 100), kat(4, 'Wandern', 'wandern', 60)], 4000)
  const bodo = person(2, [kat(2, 'Radfahren', 'rad', 400), kat(4, 'Wandern', 'wandern', 20)], 1000)
  const gruppe = [anna, bodo]

  it('liefert immer fünf Achsen in fester Reihenfolge', () => {
    expect(profilAchsen(anna, gruppe).map((a) => a.key)).toEqual([
      'lauf',
      'rad',
      'schwimm',
      'hoehe',
      'spezial',
    ])
  })

  it('skaliert jede Achse auf den Bestwert der Gruppe', () => {
    const achsen = profilAchsen(anna, gruppe)
    const lauf = achsen.find((a) => a.key === 'lauf')!
    expect(lauf.wert).toBe(100)
    expect(lauf.max).toBe(100)
    expect(lauf.anteil).toBe(1) // Anna führt beim Laufen

    const hoehe = achsen.find((a) => a.key === 'hoehe')!
    expect(hoehe.wert).toBe(4000)
    expect(hoehe.anteil).toBe(1)

    // Bodo hat 1000 von 4000 hm → ein Viertel des Netzradius
    expect(profilAchsen(bodo, gruppe).find((a) => a.key === 'hoehe')!.anteil).toBe(0.25)
  })

  it('nimmt die stärkste Nebenkategorie als fünfte Achse', () => {
    const spezial = profilAchsen(anna, gruppe).find((a) => a.key === 'spezial')!
    expect(spezial.label).toBe('Wandern')
    expect(spezial.wert).toBe(60)
    expect(spezial.max).toBe(60)
    expect(spezial.category_id).toBe(4)
  })

  it('misst beide Personen auf derselben Spezial-Achse, wenn eine vorgegeben ist', () => {
    const tanz = person(3, [kat(5, 'Tanzen', 'tanzen', 30)])
    const mit = [anna, bodo, tanz]
    // Annas Achse ist Wandern (id 4) — für Tanz-Person darauf gemessen: 0
    const erzwungen = profilAchsen(tanz, mit, 4)
    expect(erzwungen.find((a) => a.key === 'spezial')!.label).toBe('Wandern')
    expect(erzwungen.find((a) => a.key === 'spezial')!.wert).toBe(0)
  })

  it('leiht sich die verbreitetste Nebenkategorie, wenn jemand gar keine hat', () => {
    const nurRad = person(9, [kat(2, 'Radfahren', 'rad', 50)])
    const achsen = profilAchsen(nurRad, [anna, bodo, nurRad])
    const spezial = achsen.find((a) => a.key === 'spezial')!
    expect(spezial.label).toBe('Wandern')
    expect(spezial.wert).toBe(0)
    expect(spezial.anteil).toBe(0)
  })

  it('bleibt bei einer leeren Gruppe auf 0 statt durch 0 zu teilen', () => {
    const leer = person(1, [])
    for (const a of profilAchsen(leer, [leer])) {
      expect(a.anteil).toBe(0)
      expect(Number.isFinite(a.anteil)).toBe(true)
    }
  })
})

describe('Spezial-Auswahl', () => {
  it('wählt die stärkste Nebenkategorie der Person', () => {
    const u = person(1, [kat(4, 'Wandern', 'wandern', 10), kat(5, 'Tanzen', 'tanzen', 90)])
    expect(spezialKategorie(u)?.name).toBe('Tanzen')
  })

  it('nimmt für die Gruppe die von den meisten Leuten betriebene Nebensportart', () => {
    const a = person(1, [kat(4, 'Wandern', 'wandern', 5)])
    const b = person(2, [kat(4, 'Wandern', 'wandern', 5)])
    const c = person(3, [kat(5, 'Tanzen', 'tanzen', 500)])
    expect(verbreitetsteSpezial([a, b, c])?.name).toBe('Wandern')
  })
})
