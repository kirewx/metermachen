import type { PeriodMode } from './period'
import { useStoredChoice } from './useStoredChoice'

const KEY = 'mm_period_mode'
const MODES: readonly PeriodMode[] = ['month', 'year', 'challenge']

/** Monat (default on the first visit), Jahr or Challenge. The choice is remembered in the browser. */
export function usePeriodMode() {
  return useStoredChoice(KEY, MODES, 'month')
}
