import { useStoredChoice } from './useStoredChoice'

export type UnitMode = 'mm' | 'km'

const KEY = 'mm_unit_mode'
const MODES: readonly UnitMode[] = ['mm', 'km']

/** MM (skaliert, Standard) vs. echte km. Auswahl wird im Browser gemerkt. */
export function useUnitMode() {
  const [mode, setMode] = useStoredChoice(KEY, MODES, 'mm')
  return { mode, toggle: () => setMode((m) => (m === 'mm' ? 'km' : 'mm')) }
}

/** Anzeigewert wählen: MM = skaliert (Kategorie-Faktor × Handicap), km = echte km vom Backend. */
export function toDisplay(scaledKm: number, realKm: number, mode: UnitMode): number {
  return mode === 'km' ? realKm : scaledKm
}

export const unitLabel = (mode: UnitMode): string => (mode === 'km' ? 'km' : 'MM')
