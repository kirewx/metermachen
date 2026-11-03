import type { ChallengeGroup } from '../../api/client'

/** Team colours, same hex values and order as TEAM_FARBEN in backend/app/services/challenges.py. */
export const TEAM_FARBEN = [
  { hex: '#60a5fa', name: 'Blau' },
  { hex: '#f472b6', name: 'Pink' },
  { hex: '#fb923c', name: 'Orange' },
  { hex: '#4ade80', name: 'Grün' },
  { hex: '#a78bfa', name: 'Lila' },
  { hex: '#facc15', name: 'Gelb' },
] as const

/** A group's colour; groups from before colours existed get the default by id. */
export function teamFarbe(g: Pick<ChallengeGroup, 'id' | 'color'>): string {
  return g.color ?? TEAM_FARBEN[(g.id - 1) % TEAM_FARBEN.length].hex
}

/** Hex colour plus alpha, e.g. tint('#60a5fa', 0.08) for a faint row background. */
export function tint(hex: string, alpha: number): string {
  const a = Math.round(alpha * 255).toString(16).padStart(2, '0')
  return `${hex}${a}`
}
