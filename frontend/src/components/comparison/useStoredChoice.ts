import { useEffect, useState } from 'react'

/**
 * One of a fixed set of choices, remembered in the browser. Unknown stored values
 * fall back; blocked storage (private mode) just means nothing is remembered.
 */
export function useStoredChoice<T extends string>(key: string, allowed: readonly T[], fallback: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      return allowed.find((a) => a === stored) ?? fallback
    } catch {
      return fallback
    }
  })
  useEffect(() => {
    try {
      localStorage.setItem(key, value)
    } catch {
      // Storage is blocked: the choice lives for this visit only.
    }
  }, [key, value])
  return [value, setValue] as const
}
