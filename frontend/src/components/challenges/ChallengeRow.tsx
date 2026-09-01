import { Link } from 'react-router-dom'
import type { Challenge } from '../../api/client'

// The one person who won. Target mode: the admin-set prize winner, or the
// only qualifier when there is exactly one. Ranking mode: rank 1 among the
// qualifiers. Null while a target challenge with several qualifiers still
// waits for the draw.
function winnerName(ch: Challenge): string | null {
  if (ch.sieger_id != null) {
    return ch.standings.find((s) => s.user_id === ch.sieger_id)?.display_name ?? null
  }
  const qualified = ch.standings
    .filter((s) => ch.gewinner_ids.includes(s.user_id))
    .sort((a, b) => a.rank - b.rank)
  if (qualified.length === 0) return null
  if (ch.mode === 'rangliste' || qualified.length === 1) return qualified[0].display_name
  return null
}

function outcome(ch: Challenge): string {
  const winner = winnerName(ch)
  if (winner) return `🏆 ${winner}`
  if (ch.gewinner_ids.length === 0) return 'niemand'
  return `${ch.gewinner_ids.length} × geschafft · Sieger offen`
}

// Compact list row for planned and finished challenges. Finished: the winner
// leads, the title sits below in small print so the row stays readable on a phone.
export default function ChallengeRow({ ch }: { ch: Challenge }) {
  const finished = ch.status === 'beendet'
  return (
    <Link
      to={`/arena/challenges/${ch.id}`}
      className="flex items-center gap-2 border-b border-line px-3 py-2.5 text-sm last:border-b-0"
    >
      {finished ? (
        <span className="min-w-0 flex-1">
          <span className="block truncate font-bold text-ink">{outcome(ch)}</span>
          <span className="block truncate text-xs text-ink-mute">{ch.title}</span>
        </span>
      ) : (
        <>
          <span className="min-w-0 flex-1 truncate text-ink">{ch.title}</span>
          <span className="shrink-0 font-bold text-ink-mute">
            {new Date(ch.period_start).toLocaleDateString('de-DE')}
          </span>
        </>
      )}
    </Link>
  )
}
