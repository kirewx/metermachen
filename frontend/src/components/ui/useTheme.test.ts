import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.className = ''
  })

  it('startet dunkel und setzt die dark-Klasse', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('dunkel')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('toggle wechselt auf hell und persistiert', () => {
    const { result } = renderHook(() => useTheme())
    act(() => result.current.toggle())
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('theme')).toBe('hell')
  })

  it('liest gespeichertes hell beim Start', () => {
    localStorage.setItem('theme', 'hell')
    const { result } = renderHook(() => useTheme())
    expect(result.current.theme).toBe('hell')
  })
})
