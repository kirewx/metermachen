import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useStoredChoice } from './useStoredChoice'

const CHOICES = ['a', 'b'] as const

describe('useStoredChoice', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('starts with the fallback and remembers a change', () => {
    const { result } = renderHook(() => useStoredChoice('k', CHOICES, 'a'))
    expect(result.current[0]).toBe('a')
    act(() => result.current[1]('b'))
    expect(localStorage.getItem('k')).toBe('b')
  })

  it('restores a stored choice and ignores unknown values', () => {
    localStorage.setItem('k', 'b')
    expect(renderHook(() => useStoredChoice('k', CHOICES, 'a')).result.current[0]).toBe('b')
    localStorage.setItem('k', 'quatsch')
    expect(renderHook(() => useStoredChoice('k', CHOICES, 'a')).result.current[0]).toBe('a')
  })

  it('works without remembering when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const { result } = renderHook(() => useStoredChoice('k', CHOICES, 'a'))
    expect(result.current[0]).toBe('a')
    act(() => result.current[1]('b'))
    expect(result.current[0]).toBe('b')
  })
})
