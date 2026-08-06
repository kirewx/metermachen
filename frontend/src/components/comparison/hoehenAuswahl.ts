import type { ComparisonUser } from '../../api/client'

/**
 * Personenauswahl der Höhenmeter-Ansicht. Bei rund 30 Mitspielenden ist die
 * eigentliche Frage nicht „welche Grafik", sondern „wen zeigt man überhaupt" —
 * deshalb liegt die Auswahl-Logik hier zentral und wird von beiden
 * Unteransichten geteilt.
 */
export type Preset = 'alle' | 'nachbarschaft' | 'ich'

export const PRESETS: { key: Preset; label: string }[] = [
  { key: 'alle', label: 'Alle' },
  { key: 'nachbarschaft', label: 'Nachbarschaft' },
  { key: 'ich', label: 'Nur ich' },
]

/** Absteigend nach Höhenmetern; bei Gleichstand entscheidet der Name. */
export function nachHoehe(users: ComparisonUser[]): ComparisonUser[] {
  return [...users].sort(
    (a, b) =>
      b.total_elevation_m - a.total_elevation_m ||
      a.display_name.localeCompare(b.display_name),
  )
}

/**
 * Führender plus zwei Plätze über und unter der eigenen Person. Ohne bekannte
 * eigene Person (z. B. Gast-Blick) bleibt es beim Spitzenfeld.
 */
export function nachbarschaft(sortiert: ComparisonUser[], meId: number | null): ComparisonUser[] {
  const i = sortiert.findIndex((u) => u.user_id === meId)
  if (i < 0) return sortiert.slice(0, 5)
  const fenster = sortiert.slice(Math.max(0, i - 2), i + 3)
  const fuehrend = sortiert[0]
  return fenster.some((u) => u.user_id === fuehrend.user_id)
    ? fenster
    : [fuehrend, ...fenster]
}

export function presetAuswahl(
  preset: Preset,
  sortiert: ComparisonUser[],
  meId: number | null,
): Set<number> {
  if (preset === 'ich') {
    const ich = sortiert.find((u) => u.user_id === meId)
    return new Set(ich ? [ich.user_id] : sortiert.slice(0, 1).map((u) => u.user_id))
  }
  if (preset === 'nachbarschaft') {
    return new Set(nachbarschaft(sortiert, meId).map((u) => u.user_id))
  }
  return new Set(sortiert.map((u) => u.user_id))
}

/** Ab hier wird es eng: schmale Säulen ohne Namen, Kurven nur noch als Band. */
export const BREIT_BIS = 8
