import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import Avatar from '../ui/Avatar'
import Card from '../ui/Card'

export default function PunkteRanking() {
  const { data: ranking = [] } = useQuery({
    queryKey: ['pointsRanking'],
    queryFn: api.pointsRanking,
  })
  return (
    <Card>
      <h2 className="text-lg font-black tracking-wide text-ink">Punkte-Ranking</h2>
      <p className="mt-1 text-xs text-ink-mute">
        Die zweite Meisterschaft: Wetten gewinnen statt (nur) Kilometer machen.
      </p>
      <ul className="mt-3">
        {ranking.map((e) => (
          <li
            key={e.user_id}
            className="flex items-center gap-3 border-b border-line/30 py-2 text-sm"
          >
            <span
              className={`w-7 font-black tabular-nums ${
                e.rank === 1 ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
              }`}
            >
              P{e.rank}
            </span>
            <Avatar value={e.avatar} size="sm" />
            <span className="min-w-0 flex-1 truncate font-bold text-ink">
              {e.display_name}
            </span>
            <span className="font-mono tabular-nums text-ink">
              {e.balance} <span className="text-xs font-normal text-ink-mute">P</span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
