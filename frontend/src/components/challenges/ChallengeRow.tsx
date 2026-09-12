import { Link } from 'react-router-dom'
import type { Challenge } from '../../api/client'
import { siegerText } from './wertung'

// The one winner. Entered prize winner first (group or person). Otherwise:
// group challenge → the winning groups' names; target mode → the only
// qualifier when there is exactly one; ranking mode → rank 1. Null while a
// target challenge with several qualifiers still waits for the draw.
function winnerName(ch: Challenge): string | null {
  const entered = siegerText(ch)
  if (entered !== null) return entered
  if (ch.team_mode) {
    const namen = ch.groups.filter((g) => g.geschafft).map((g) => g.name)
    return namen.length > 0 ? namen.join(', ') : null
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
