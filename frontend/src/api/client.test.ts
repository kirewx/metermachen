import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, isUnauthorized } from './client'

afterEach(() => vi.restoreAllMocks())

function mockFetch(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    })),
  )
}

describe('ApiError / isUnauthorized', () => {
  it('trägt den HTTP-Status', () => {
    const e = new ApiError(403, 'Nur für Admins')
    expect(e.status).toBe(403)
    expect(e.message).toBe('Nur für Admins')
    expect(e).toBeInstanceOf(Error)
  })

  it('isUnauthorized nur bei 401-ApiError', () => {
    expect(isUnauthorized(new ApiError(401, 'x'))).toBe(true)
    expect(isUnauthorized(new ApiError(500, 'x'))).toBe(false)
    expect(isUnauthorized(new Error('Failed to fetch'))).toBe(false)
    expect(isUnauthorized(null)).toBe(false)
  })
})

describe('request()', () => {
  it('wirft ApiError mit Status und detail-Message bei nicht-ok', async () => {
    mockFetch(401, { detail: 'Nicht eingeloggt' })
    await expect(api.me()).rejects.toMatchObject({ status: 401, message: 'Nicht eingeloggt' })
  })

  it('fällt auf generische Message zurück, wenn kein detail da ist', async () => {
    mockFetch(500, {})
    await expect(api.me()).rejects.toMatchObject({ status: 500, message: 'Fehler 500' })
  })
})
