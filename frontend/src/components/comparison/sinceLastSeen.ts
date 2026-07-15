export type SeenEntry = { user_id: number; scaled_km: number; rank: number }
export type LastSeen = { seen_at: string; entries: SeenEntry[] }
export type UserLike = {
  user_id: number
  display_name: string
  total_scaled_km: number
  rank: number
}

export const SEEN_THRESHOLD_MS = 8 * 60 * 60 * 1000

export type PerUser = {
  prevScaled: number
  delta: number
  rankNow: number
  rankPrev: number | null
  improved: boolean
}

export type SinceLastSeen = {
  active: boolean
  daysAgo: number
  perUser: Record<number, PerUser>
}

/** Reiner Diff aktueller Stand vs. letzter Snapshot. `nowMs` wird injiziert (testbar). */
export function computeSinceLastSeen(
  users: UserLike[],
  last: LastSeen | null,
  nowMs: number,
): SinceLastSeen {
  const active = last != null && nowMs - Date.parse(last.seen_at) > SEEN_THRESHOLD_MS
  const prevMap = new Map<number, SeenEntry>()
  if (last) for (const e of last.entries) prevMap.set(e.user_id, e)

  const perUser: Record<number, PerUser> = {}
  for (const u of users) {
    const prev = prevMap.get(u.user_id)
    const prevScaled = prev ? prev.scaled_km : u.total_scaled_km
    const rankPrev = prev ? prev.rank : null
    perUser[u.user_id] = {
      prevScaled,
      delta: Math.max(0, u.total_scaled_km - prevScaled),
      rankNow: u.rank,
      rankPrev,
      improved: rankPrev != null && u.rank < rankPrev,
    }
  }
  const daysAgo = last
    ? Math.max(0, Math.round((nowMs - Date.parse(last.seen_at)) / 86_400_000))
    : 0
  return { active, daysAgo, perUser }
}

/** Kurztext fürs Banner: Zeitangabe + bis zu drei größte Zuwächse. */
export function describeSinceLastSeen(since: SinceLastSeen, users: UserLike[]): string {
  if (!since.active) return ''
  const zeit =
    since.daysAgo <= 0 ? 'seit heute' : since.daysAgo === 1 ? 'seit gestern' : `vor ${since.daysAgo} Tagen`
  const top = users
    .map((u) => ({
      name: u.display_name,
      delta: since.perUser[u.user_id]?.delta ?? 0,
      improved: since.perUser[u.user_id]?.improved ?? false,
    }))
    .filter((x) => x.delta > 0)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 3)
  if (top.length === 0) return `Seit deinem letzten Besuch (${zeit}) hat sich nichts getan.`
  const teile = top.map((x) => `${x.name} +${Math.round(x.delta)} MM${x.improved ? ' 🚀' : ''}`)
  return `Seit deinem letzten Besuch (${zeit}): ${teile.join(' · ')}`
}
