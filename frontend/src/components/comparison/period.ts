import type { UnitMode } from './unit'

export type PeriodMode = 'month' | 'year'

const MONTHS_SHORT = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']

/** 'YYYY-MM' key of a local date, same format as the backend month axis. */
export function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/** `?month=` value that lets the server pick the season's default month (same rule as `defaultMonth`). */
export const CURRENT_MONTH = 'current'

/** Month to show when entering month mode: the current one if the season has it, else the last. */
export function defaultMonth(months: string[], today: Date): string | null {
  if (months.length === 0) return null
  const current = monthKey(today)
  return months.includes(current) ? current : months[months.length - 1]
}

export function monthLabel(key: string): string {
  const [year, month] = key.split('-')
  return `${MONTHS_SHORT[Number(month) - 1]} ${year}`
}

/** First day a month race counts: the 1st, or the season start inside a partial first month. */
export function monthStartDate(month: string, seasonStart: string | null): string {
  const first = `${month}-01`
  return seasonStart !== null && seasonStart.startsWith(month) && seasonStart > first
    ? seasonStart
    : first
}

/** Season goal and milestones are MM values for the whole season; a month or the km view has none. */
export function showsSeasonTargets(month: string | null | undefined, mode: UnitMode): boolean {
  return month == null && mode === 'mm'
}

/** Keys sort lexicographically, so a plain string compare is enough. */
export function isFinishedMonth(key: string, today: Date): boolean {
  return key < monthKey(today)
}
