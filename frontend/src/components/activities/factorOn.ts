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

/**
 * MM of an entry as the backend computes it: from elevation_from on, every
 * 100 hm count like 1 km (unless the category opts out), then the factor
 * valid on that date applies.
 */
export function mmOn(category: Category, isoDate: string, km: number, hm: number): number {
  const mitHm =
    category.counts_elevation && category.elevation_from && isoDate >= category.elevation_from
  return (km + (mitHm && hm > 0 ? hm / HM_PRO_KM : 0)) * factorOn(category, isoDate)
}
