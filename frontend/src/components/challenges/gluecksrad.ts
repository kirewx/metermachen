import type { Challenge, ChallengeGroup } from '../../api/client'

/** One slice on the wheel: a person (user_id) or a group (group id). */
export type Kandidat = { id: number; label: string; avatar?: string; vorgewaehlt: boolean }

const UINT32 = 2 ** 32

function cryptoUint32(): number {
  return crypto.getRandomValues(new Uint32Array(1))[0]
}

/** Uniform index in [0, n). Rejects the incomplete last block so no slice is
 * favoured by modulo bias. */
export function ziehe(n: number, uint32: () => number = cryptoUint32): number {
  if (n < 1) throw new Error('Keine Kandidaten')
  const grenze = UINT32 - (UINT32 % n)
  for (;;) {
    const x = uint32()
    if (x < grenze) return x % n
  }
}

/** Slice index under the pointer at the top. Slice i covers [i, i+1) * 360/n
 * degrees clockwise from the top; rotating the wheel clockwise by r brings the
 * point at angle -r under the pointer. */
export function segmentAmZeiger(rotation: number, n: number): number {
  const winkel = (((-rotation) % 360) + 360) % 360
  return Math.min(Math.floor(winkel / (360 / n)), n - 1)
}

/** Absolute rotation (degrees) to animate to so the wheel stops on slice
 * `index`. Always spins forward by at least `umdrehungen` full turns from
 * `aktuell`; `lage` in [0, 1) picks the spot inside the slice, kept away from
 * the edges so the pointer never sits on a border. */
export function zielRotation(
  index: number,
  n: number,
  aktuell: number,
  lage: number,
  umdrehungen = 5,
): number {
  const breite = 360 / n
  const ziel = index * breite + breite * (0.15 + 0.7 * lage)
  const rest = (((360 - ziel) % 360) + 360) % 360
  let r = aktuell - (((aktuell % 360) + 360) % 360) + rest
  while (r < aktuell + umdrehungen * 360) r += 360
  return r
}

/** Everybody in the result; those who reached the target are preselected. */
export function personenKandidaten(ch: Challenge): Kandidat[] {
  return ch.standings.map((s) => ({
    id: s.user_id, label: s.display_name, avatar: s.avatar, vorgewaehlt: s.geschafft,
  }))
}

export function gruppenKandidaten(ch: Challenge): Kandidat[] {
  return ch.groups.map((g) => ({ id: g.id, label: g.name, vorgewaehlt: g.geschafft }))
}

/** Second round of a group challenge: the drawn group's members, all in. */
export function mitgliederKandidaten(g: ChallengeGroup): Kandidat[] {
  return g.members.map((m) => ({
    id: m.user_id, label: m.display_name, avatar: m.avatar, vorgewaehlt: true,
  }))
}
