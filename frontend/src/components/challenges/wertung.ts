import type { Challenge } from '../../api/client'

export type KategorieName = { id: number; name: string }

export function einheit(metric: Challenge['metric']): string {
  if (metric === 'streak') return 'Tage'
  if (metric === 'anzahl') return 'Aktivitäten'
  return 'MM'
}

function kategorienText(ch: Challenge, kategorien: KategorieName[]): string {
  if (ch.category_ids.length === 0) return 'allen Sportarten'
  const namen = ch.category_ids
    .map((id) => kategorien.find((k) => k.id === id)?.name)
    .filter((n): n is string => !!n)
  return namen.length > 0 ? namen.join(' und ') : 'ausgewählten Sportarten'
}

/** Menschenlesbare Beschreibung der Wertung, z.B. "Ziel: 300 MM aus allen Sportarten". */
export function wertungText(ch: Challenge, kategorien: KategorieName[]): string {
  const aus = `aus ${kategorienText(ch, kategorien)}`
  if (ch.mode === 'rangliste') {
    const was =
      ch.metric === 'streak'
        ? 'längste Serie'
        : ch.metric === 'anzahl'
          ? 'meiste Aktivitäten'
          : 'meiste MM'
    return `Rangliste: ${was} ${aus}, Top ${ch.top_n}`
  }
  if (ch.metric === 'streak') {
    return `Ziel: ${ch.target} Tage am Stück mit mindestens ${ch.streak_min_mm} MM ${aus}`
  }
  return `Ziel: ${ch.target} ${einheit(ch.metric)} ${aus}`
}

/** 0..1 für den Fortschrittsbalken. Ranglisten haben keine Schwelle → 0. */
export function fortschritt(ch: Challenge, wert: number): number {
  if (ch.mode !== 'ziel' || !ch.target) return 0
  return Math.min(wert / ch.target, 1)
}
