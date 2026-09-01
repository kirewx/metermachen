import { Link } from 'react-router-dom'
import type { Challenge } from '../../api/client'

export default function ChallengeRow({ ch }: { ch: Challenge }) {
  const gewinner = ch.standings
    .filter((s) => ch.gewinner_ids.includes(s.user_id))
    .map((s) => s.display_name)
  return (
    <Link
      to={`/arena/challenges/${ch.id}`}
      className="flex items-center gap-2 border-b border-line px-3 py-2.5 text-sm last:border-b-0"
    >
      <span className="min-w-0 flex-1 truncate text-ink">{ch.title}</span>
      <span className="shrink-0 font-bold text-ink-mute">
        {ch.status === 'beendet'
          ? gewinner.length > 0
            ? `${gewinner.join(', ')} 🏆`
            : 'niemand'
          : new Date(ch.period_start).toLocaleDateString('de-DE')}
      </span>
    </Link>
  )
}
