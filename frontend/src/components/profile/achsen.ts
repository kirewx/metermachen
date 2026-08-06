import type { CategoryShare, ComparisonUser } from '../../api/client'

/**
 * Achsen des Spinnennetzes: drei feste Kerndisziplinen, die Höhenmeter und
 * eine persönliche Spezialdisziplin. Die drei Kernachsen sind bei allen gleich,
 * damit Profile vergleichbar bleiben.
 */
export type AchsenKey = 'lauf' | 'rad' | 'schwimm' | 'hoehe' | 'spezial'

export type Achse = {
  key: AchsenKey
  label: string
  /** Rohwert: gewertete MM, bei 'hoehe' Höhenmeter. */
  wert: number
  /** Bestwert der Gruppe auf dieser Achse (100 % des Netzes). */
  max: number
  /** wert / max, auf 0…1 begrenzt. */
  anteil: number
  einheit: 'MM' | 'hm'
  color: string
  icon: string
  /** Nur bei 'spezial': die zugrunde liegende Kategorie. */
  category_id?: number
}

export type Kern = 'lauf' | 'rad' | 'schwimm'

// Zuordnung Kategorie → Disziplin, gespiegelt aus bucket_for_category() im
// Backend (services/achievements.py): erst das Icon, dann der Name.
const KERN_DEF = [
  { key: 'lauf', label: 'Laufen', icon: 'laufen', namen: ['lauf', 'jogg'], color: '#e74c3c' },
  { key: 'rad', label: 'Rad', icon: 'rad', namen: ['rad', 'bike'], color: '#3498db' },
  { key: 'schwimm', label: 'Schwimmen', icon: 'schwimmen', namen: ['schwimm'], color: '#9b59b6' },
] as const

export function disziplin(cat: { icon: string; name: string }): Kern | null {
  for (const k of KERN_DEF) if (cat.icon === k.icon) return k.key
  const name = cat.name.toLowerCase()
  for (const k of KERN_DEF) if (k.namen.some((n) => name.includes(n))) return k.key
  return null
}

/** Gewertete MM je Kerndisziplin. */
export function kernSummen(user: ComparisonUser): Record<Kern, number> {
  const summe: Record<Kern, number> = { lauf: 0, rad: 0, schwimm: 0 }
  for (const c of user.by_category) {
    const k = disziplin(c)
    if (k) summe[k] += c.scaled_km
  }
  return summe
}

/** Alle Kategorien der Person, die zu keiner Kerndisziplin gehören. */
export function nebenKategorien(user: ComparisonUser): CategoryShare[] {
  return user.by_category.filter((c) => disziplin(c) === null)
}

/** Stärkste Nebenkategorie der Person — die wird zur fünften Achse. */
export function spezialKategorie(user: ComparisonUser): CategoryShare | null {
  const neben = [...nebenKategorien(user)].sort((a, b) => b.scaled_km - a.scaled_km)
  return neben[0] ?? null
}

/**
 * Fallback für Leute ohne Nebenkategorie: die in der Gruppe verbreitetste
 * (bei Gleichstand die mit den meisten MM). So bleibt das Fünfeck ein Fünfeck.
 */
export function verbreitetsteSpezial(users: ComparisonUser[]): CategoryShare | null {
  const zaehler = new Map<number, { cat: CategoryShare; leute: number; mm: number }>()
  for (const u of users) {
    for (const c of nebenKategorien(u)) {
      const e = zaehler.get(c.category_id)
      if (e) {
        e.leute += 1
        e.mm += c.scaled_km
      } else {
        zaehler.set(c.category_id, { cat: c, leute: 1, mm: c.scaled_km })
      }
    }
  }
  const sortiert = [...zaehler.values()].sort((a, b) => b.leute - a.leute || b.mm - a.mm)
  return sortiert[0]?.cat ?? null
}

function mmInKategorie(user: ComparisonUser, categoryId: number): number {
  return user.by_category.find((c) => c.category_id === categoryId)?.scaled_km ?? 0
}

/**
 * Baut die fünf Achsen einer Person. `spezialId` erzwingt eine bestimmte
 * Spezialkategorie — nötig, damit beim Vergleich zweier Personen beide auf
 * derselben Achse gemessen werden.
 */
export function profilAchsen(
  user: ComparisonUser,
  alle: ComparisonUser[],
  spezialId?: number | null,
): Achse[] {
  const spezialCat =
    (spezialId != null
      ? alle.flatMap((u) => u.by_category).find((c) => c.category_id === spezialId)
      : null) ??
    spezialKategorie(user) ??
    verbreitetsteSpezial(alle)

  const eigene = kernSummen(user)
  const summenAlle = alle.map(kernSummen)

  const achsen: Achse[] = KERN_DEF.map((k) => {
    const max = Math.max(0, ...summenAlle.map((s) => s[k.key]))
    return {
      key: k.key,
      label: k.label,
      wert: eigene[k.key],
      max,
      anteil: max > 0 ? Math.min(1, eigene[k.key] / max) : 0,
      einheit: 'MM' as const,
      color: k.color,
      icon: k.icon,
    }
  })

  const maxHm = Math.max(0, ...alle.map((u) => u.total_elevation_m))
  achsen.push({
    key: 'hoehe',
    label: 'Höhe',
    wert: user.total_elevation_m,
    max: maxHm,
    anteil: maxHm > 0 ? Math.min(1, user.total_elevation_m / maxHm) : 0,
    einheit: 'hm',
    color: '#27ae60',
    icon: 'berg',
  })

  const spezialWert = spezialCat ? mmInKategorie(user, spezialCat.category_id) : 0
  const spezialMax = spezialCat
    ? Math.max(0, ...alle.map((u) => mmInKategorie(u, spezialCat.category_id)))
    : 0
  achsen.push({
    key: 'spezial',
    label: spezialCat?.name ?? 'Spezial',
    wert: spezialWert,
    max: spezialMax,
    anteil: spezialMax > 0 ? Math.min(1, spezialWert / spezialMax) : 0,
    einheit: 'MM',
    color: spezialCat?.color ?? '#f1c40f',
    icon: spezialCat?.icon ?? 'medaille',
    category_id: spezialCat?.category_id,
  })

  return achsen
}
