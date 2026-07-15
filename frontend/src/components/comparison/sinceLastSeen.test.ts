import { expect, it } from 'vitest'
import { computeSinceLastSeen, describeSinceLastSeen, type UserLike } from './sinceLastSeen'

const users: UserLike[] = [
  { user_id: 1, display_name: 'Erik', total_scaled_km: 130, rank: 1 },
  { user_id: 2, display_name: 'Ben', total_scaled_km: 128, rank: 2 },
]
const NOW = 1_700_000_000_000
const OLD = new Date(NOW - 3 * 86_400_000).toISOString() // vor 3 Tagen
const RECENT = new Date(NOW - 2 * 3_600_000).toISOString() // vor 2 h

it('ist inaktiv ohne Snapshot', () => {
  const s = computeSinceLastSeen(users, null, NOW)
  expect(s.active).toBe(false)
})

it('ist inaktiv, wenn letzter Besuch < 8 h her ist', () => {
  const s = computeSinceLastSeen(users, { seen_at: RECENT, entries: [] }, NOW)
  expect(s.active).toBe(false)
})

it('berechnet Deltas, Rang-Verbesserung und daysAgo', () => {
  const s = computeSinceLastSeen(
    users,
    { seen_at: OLD, entries: [
      { user_id: 1, scaled_km: 122, rank: 1 },
      { user_id: 2, scaled_km: 100, rank: 3 },
    ] },
    NOW,
  )
  expect(s.active).toBe(true)
  expect(s.daysAgo).toBe(3)
  expect(s.perUser[1].delta).toBe(8)
  expect(s.perUser[2].delta).toBe(28)
  expect(s.perUser[2].improved).toBe(true) // Rang 3 -> 2
  expect(s.perUser[1].improved).toBe(false)
})

it('neue Person (nicht im Snapshot) bekommt Delta 0 und rankPrev null', () => {
  const s = computeSinceLastSeen(
    users,
    { seen_at: OLD, entries: [{ user_id: 1, scaled_km: 122, rank: 1 }] },
    NOW,
  )
  expect(s.perUser[2].delta).toBe(0)
  expect(s.perUser[2].rankPrev).toBeNull()
})

it('describeSinceLastSeen fasst die Top-Bewegungen zusammen', () => {
  const s = computeSinceLastSeen(
    users,
    { seen_at: OLD, entries: [
      { user_id: 1, scaled_km: 122, rank: 1 },
      { user_id: 2, scaled_km: 100, rank: 3 },
    ] },
    NOW,
  )
  const text = describeSinceLastSeen(s, users)
  expect(text).toContain('vor 3 Tagen')
  expect(text).toContain('Ben +28 MM')
  expect(text).toContain('🚀')
})
