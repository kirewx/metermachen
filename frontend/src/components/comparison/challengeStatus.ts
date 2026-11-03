import type { Challenge } from '../../api/client'

/** "läuft · noch 12 Tage", "läuft · letzter Tag" or "Endstand". */
export function statusText(ch: Challenge, today: Date): string {
  if (ch.status !== 'laufend') return 'Endstand'
  const [y, m, d] = ch.period_end.split('-').map(Number)
  const ende = Date.UTC(y, m - 1, d)
  const heute = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())
  const rest = Math.round((ende - heute) / 86_400_000)
  if (rest <= 0) return 'läuft · letzter Tag'
  return `läuft · noch ${rest + 1} Tage`
}
