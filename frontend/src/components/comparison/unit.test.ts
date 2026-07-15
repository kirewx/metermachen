import { describe, expect, it } from 'vitest'
import { toDisplay, unitLabel } from './unit'

describe('unit helpers', () => {
  it('MM-Modus gibt den skalierten Wert unverändert zurück', () => {
    expect(toDisplay(130, 1.3, 'mm')).toBe(130)
  })
  it('km-Modus teilt durch den km_factor', () => {
    expect(toDisplay(130, 1.3, 'km')).toBeCloseTo(100)
  })
  it('km_factor 1 liefert in beiden Modi denselben Wert', () => {
    expect(toDisplay(120, 1, 'km')).toBe(120)
    expect(toDisplay(120, 1, 'mm')).toBe(120)
  })
  it('faktor 0 wird abgefangen (kein Division-durch-0)', () => {
    expect(toDisplay(50, 0, 'km')).toBe(50)
  })
  it('unitLabel benennt die Modi', () => {
    expect(unitLabel('mm')).toBe('MM')
    expect(unitLabel('km')).toBe('km')
  })
})
