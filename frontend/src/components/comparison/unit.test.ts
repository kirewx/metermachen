import { describe, expect, it } from 'vitest'
import { toDisplay, unitLabel } from './unit'

describe('unit helpers', () => {
  it('MM-Modus zeigt den skalierten Wert', () => {
    expect(toDisplay(130, 35, 'mm')).toBe(130)
  })
  it('km-Modus zeigt die echten km vom Backend', () => {
    expect(toDisplay(130, 35, 'km')).toBe(35)
  })
  it('identische Werte bleiben in beiden Modi gleich', () => {
    expect(toDisplay(120, 120, 'km')).toBe(120)
    expect(toDisplay(120, 120, 'mm')).toBe(120)
  })
  it('unitLabel benennt die Modi', () => {
    expect(unitLabel('mm')).toBe('MM')
    expect(unitLabel('km')).toBe('km')
  })
})
