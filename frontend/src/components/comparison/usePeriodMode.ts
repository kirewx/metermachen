import { useEffect, useState } from 'react'
import type { PeriodMode } from './period'

const KEY = 'mm_period_mode'

/** Monat (default on the first visit) vs. Jahr. The choice is remembered in the browser. */
export function usePeriodMode() {
  const [period, setPeriod] = useState<PeriodMode>(() =>
    localStorage.getItem(KEY) === 'year' ? 'year' : 'month',
  )
  useEffect(() => {
    localStorage.setItem(KEY, period)
  }, [period])
  return [period, setPeriod] as const
}
