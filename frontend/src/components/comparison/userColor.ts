/**
 * Feste Neon-Palette pro Person — identische Farbe in allen drei
 * Vergleichs-Ansichten. Zuordnung stabil über die sortierte User-ID-Reihenfolge.
 */
export const USER_FARBEN = [
  '#22d3ee', '#818cf8', '#2dd4bf', '#a78bfa', '#38bdf8', '#e879f9', '#34d399', '#f472b6',
] as const

export function userColor(userId: number, alleIds: number[]): string {
  const sortiert = [...alleIds].sort((a, b) => a - b)
  const i = Math.max(0, sortiert.indexOf(userId))
  return USER_FARBEN[i % USER_FARBEN.length]
}
