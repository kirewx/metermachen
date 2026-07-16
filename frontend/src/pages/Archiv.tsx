import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Avatar from '../components/ui/Avatar'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import { aktiveSeason } from '../components/ui/season'

export default function Archiv() {
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const year = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const { data: warmup, error } = useQuery({
    queryKey: ['comparison', year, 'warmup'],
    queryFn: () => api.comparisonWarmup(year),
  })
  const { data: badges } = useQuery({
    queryKey: ['warmupAchievements'],
    queryFn: api.warmupAchievements,
  })

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (!warmup) return <p className="p-8 text-ink-mute">Lade…</p>

  const startFormatiert = warmup.start_date
    ? new Date(`${warmup.start_date}T00:00:00`).toLocaleDateString('de-DE')
    : ''

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="text-lg font-black tracking-wide text-ink">
          Warm-up-Phase <span className="text-ink-mute">(bis {startFormatiert})</span>
        </h2>
        <p className="mt-1 text-sm text-ink-mute">
          Diese Kilometer zählen nicht für die Challenge — Ehre, wem Ehre gebührt.
        </p>
        <ul className="mt-4">
          {warmup.users.map((u) => (
            <li
              key={u.user_id}
              className="flex items-center gap-3 border-b border-line/30 py-2 text-sm"
            >
              <span
                className={`w-7 font-black tabular-nums ${
                  u.rank === 1 ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
                }`}
              >
                P{u.rank}
              </span>
              <Avatar value={u.avatar} size="sm" />
              <span className="min-w-0 flex-1 truncate font-bold text-ink">
                {u.display_name}
              </span>
              <span className="font-mono tabular-nums text-ink">
                {u.total_scaled_km.toFixed(1)}{' '}
                <span className="text-xs font-normal text-ink-mute">km</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
      {badges && badges.achievements.length > 0 && (
        <Card>
          <h2 className="text-lg font-black tracking-wide text-ink">
            Warm-up-Auszeichnungen
          </h2>
          <ul className="mt-4 space-y-3">
            {badges.achievements.map((a) => (
              <li key={a.key} className="flex items-center gap-3 text-sm">
                <Icon name={a.icon} size={20} className="shrink-0 text-accent" />
                <span className="font-bold text-ink">{a.title}</span>
                <span className="min-w-0 flex-1 truncate text-ink-mute">
                  {a.winners
                    .map((w) => `${w.display_name} (${w.km.toFixed(1)} km)`)
                    .join(', ')}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}
