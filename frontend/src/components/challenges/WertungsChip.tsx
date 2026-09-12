import type { Challenge } from '../../api/client'

type Props = {
  ch: Challenge
  rank: number
  geschafft: boolean
  value: number
  /** Target mode only: the target is out of reach for the rest of the period. */
  nichtMehr?: boolean
  /** Group values are per head, so the remainder is too. */
  proKopf?: boolean
}

// The standing of one person or one group in a nutshell. Das Theme hat keine
// Erfolgsfarbe (nur accent/danger/line) — "geschafft" wird deshalb ueber die
// gefuellte Akzentflaeche markiert, nicht ueber Gruen.
export default function WertungsChip({
  ch, rank, geschafft, value, nichtMehr = false, proKopf = false,
}: Props) {
  if (ch.mode === 'rangliste')
    return (
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
          geschafft ? 'bg-accent text-accent-ink' : 'border border-line text-ink-mute'
        }`}
      >
        Platz {rank}
      </span>
    )
  if (geschafft)
    return (
      <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold text-accent-ink">
        geschafft
      </span>
    )
  if (nichtMehr)
    return (
      <span className="shrink-0 rounded-full border border-danger px-2 py-0.5 text-[10px] font-bold text-danger">
        nicht mehr
      </span>
    )
  const rest = Math.max((ch.target ?? 0) - value, 0)
  return (
    <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
      noch {Math.round(rest * 100) / 100}
      {proKopf && ' pro Kopf'}
    </span>
  )
}
