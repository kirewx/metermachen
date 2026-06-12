/** Anteil [0..1] der Strecke zum Jahresziel; >Ziel sitzt am Ende (🏁). */
export function progressFraction(scaledKm: number, goalKm: number): number {
  if (goalKm <= 0 || scaledKm <= 0) return 0
  return Math.min(scaledKm / goalKm, 1)
}

/**
 * Verteilt Namens-Badges auf vertikale Ebenen (0,1,2,…), damit nahe
 * Avatare sich nicht überdecken. Punkte näher als minDist (in
 * SVG-Einheiten) bekommen unterschiedliche Ebenen.
 */
export function spreadBadges(
  points: { id: number; x: number }[],
  minDist: number,
): Map<number, number> {
  const sorted = [...points].sort((a, b) => a.x - b.x)
  const lanes = new Map<number, number>()
  const lastXPerLane: number[] = []
  for (const p of sorted) {
    let lane = 0
    while (lane < lastXPerLane.length && p.x - lastXPerLane[lane] < minDist) lane++
    lastXPerLane[lane] = p.x
    lanes.set(p.id, lane)
  }
  return lanes
}
