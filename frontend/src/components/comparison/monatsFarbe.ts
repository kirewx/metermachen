/**
 * Farben und Maßstab der Höhenmeter-Ansicht.
 *
 * Anders als in den übrigen Vergleichs-Ansichten steht hier nicht die Person im
 * Vordergrund, sondern der Monat: die Säulen wachsen ab Challenge-Start nach oben,
 * jeder Monat bekommt eine eigene Farbe. Die Palette läuft kühl → warm entlang der
 * Monatsposition, damit sich das Wachsen als Fortschritt liest — unabhängig davon,
 * in welchem Kalendermonat die Saison startet.
 */
export const MONATS_FARBEN = [
  '#22d3ee', '#38bdf8', '#60a5fa', '#818cf8', '#a78bfa', '#c084fc',
  '#e879f9', '#f472b6', '#fb7185', '#fb923c', '#fbbf24', '#facc15',
] as const

const MONATSNAMEN = [
  'Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
  'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez',
]

/** Farbe eines Monats ('YYYY-MM') anhand seiner Position auf der Saison-Achse. */
export function monatsFarbe(monat: string, achse: string[]): string {
  const i = achse.indexOf(monat)
  return MONATS_FARBEN[(i < 0 ? 0 : i) % MONATS_FARBEN.length]
}

/** 'Jul 26' — mit Jahr, weil Saisons über die Jahresgrenze laufen können. */
export function monatsLabel(monat: string): string {
  const [jahr, m] = monat.split('-')
  const name = MONATSNAMEN[Number(m) - 1]
  if (!name || !jahr) return monat
  return `${name} ${jahr.slice(2)}`
}

export type Berg = { name: string; meters: number }

/** Messlatten für die Y-Achse — dieselbe Idee wie die Meilensteine der Saison. */
export const BERGE: Berg[] = [
  { name: 'Brocken', meters: 1141 },
  { name: 'Zugspitze', meters: 2962 },
  { name: 'Mont Blanc', meters: 4808 },
  { name: 'Kilimandscharo', meters: 5895 },
  { name: 'Everest', meters: 8848 },
]

/** Nur Berge, die unter dem Höchstwert liegen — sonst wächst die Achse ins Leere. */
export function sichtbareBerge(max: number): Berg[] {
  return BERGE.filter((b) => b.meters < max)
}

/**
 * Obergrenze der Y-Achse: immer der höchste sichtbare Wert, damit das Diagramm
 * ohne Scrollen aufs Handydisplay passt. Ohne Daten eine Ersatzskala statt 0.
 */
export function skalaMax(werte: number[]): number {
  const max = Math.max(0, ...werte)
  return max > 0 ? max : 1000
}

export function formatHm(meter: number): string {
  return Math.round(meter).toLocaleString('de-DE')
}
