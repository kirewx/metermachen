import type { Category } from '../../api/client'

/**
 * Factor of a category valid on a 'YYYY-MM-DD' date: the latest change with
 * valid_from on or before that date wins, before the first change the base
 * factor applies. Without a date (or without the change lists) the current
 * factor from the backend is used.
 */
export function factorOn(category: Category, isoDate: string): number {
  const { history, pending_changes: pending } = category
  if (!isoDate || !history || !pending) return category.factor
  const effective = [...history, ...pending]
    .filter((c) => c.valid_from <= isoDate)
    .sort((a, b) => a.valid_from.localeCompare(b.valid_from))
  return effective.length > 0 ? effective[effective.length - 1].factor : category.base_factor
}

export const HM_PRO_KM = 100

/** Whether a category counts Höhenmeter on a 'YYYY-MM-DD' date (latest change wins). */
export function countsElevationOn(category: Category, isoDate: string): boolean {
  const effective = (category.elevation_changes ?? [])
    .filter((c) => c.valid_from <= isoDate)
    .sort((a, b) => a.valid_from.localeCompare(b.valid_from))
  return effective.length > 0
    ? effective[effective.length - 1].counts_elevation
    : Boolean(category.base_counts_elevation)
}

/** MM of an entry as the backend computes it: (km + hm / 100) × factor on that date. */
export function mmOn(category: Category, isoDate: string, km: number, hm: number): number {
  const bonus = hm > 0 && countsElevationOn(category, isoDate) ? hm / HM_PRO_KM : 0
  return (km + bonus) * factorOn(category, isoDate)
}
