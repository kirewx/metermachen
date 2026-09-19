import type { Comparison } from '../../api/client'
import { monthStartDate } from './period'
import type { UnitMode } from './unit'

export type VerlaufRow = Record<string, number | string>

/** Merges all curves into one chart dataset: one row per date, one column per person. */
export function verlaufRows(data: Comparison, mode: UnitMode): VerlaufRow[] {
  const byDate = new Map<string, VerlaufRow>()
  for (const u of data.users) {
    for (const p of u.cumulative) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[u.display_name] = mode === 'km' ? p.real_km : p.scaled_km
      byDate.set(p.date, row)
    }
  }
  if (data.month != null) {
    // A month race restarts at zero: every curve is anchored on the month's first
    // day, unless the person already logged something that day.
    const anchor = monthStartDate(data.month, data.start_date)
    const row = byDate.get(anchor) ?? { date: anchor }
    for (const u of data.users) {
      if (u.cumulative.length > 0 && row[u.display_name] === undefined) row[u.display_name] = 0
    }
    if (Object.keys(row).length > 1) byDate.set(anchor, row)
  }
  return [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)))
}
