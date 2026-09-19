export type PeriodMode = 'month' | 'year'

const MONTHS_SHORT = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']

/** 'YYYY-MM' key of a local date, same format as the backend month axis. */
export function monthKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

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

/** Keys sort lexicographically, so a plain string compare is enough. */
export function isFinishedMonth(key: string, today: Date): boolean {
  return key < monthKey(today)
}
