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

/** Anzeigewert wählen: MM = skaliert (Kategorie-Faktor × Handicap), km = echte km vom Backend. */
export function toDisplay(scaledKm: number, realKm: number, mode: UnitMode): number {
  return mode === 'km' ? realKm : scaledKm
}

export const unitLabel = (mode: UnitMode): string => (mode === 'km' ? 'km' : 'MM')
