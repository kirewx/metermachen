import { useEffect, useState } from 'react'

export type UnitMode = 'mm' | 'km'

const KEY = 'mm_unit_mode'

/** MM (skaliert, Standard) vs. echte km. Auswahl wird im Browser gemerkt. */
export function useUnitMode() {
  const [mode, setMode] = useState<UnitMode>(() =>
    localStorage.getItem(KEY) === 'km' ? 'km' : 'mm',
  )
  useEffect(() => {
    localStorage.setItem(KEY, mode)
  }, [mode])
  return { mode, toggle: () => setMode((m) => (m === 'mm' ? 'km' : 'mm')) }
}

/** Skalierte MM in die anzuzeigende Einheit umrechnen. km = MM / km_factor. */
export function toDisplay(scaledKm: number, kmFactor: number, mode: UnitMode): number {
  return mode === 'km' && kmFactor > 0 ? scaledKm / kmFactor : scaledKm
}

export const unitLabel = (mode: UnitMode): string => (mode === 'km' ? 'km' : 'MM')
