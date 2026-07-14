import { useQuery } from '@tanstack/react-query'
import { api, type ComparisonUser } from '../../api/client'
import Avatar from '../ui/Avatar'
import Icon from '../ui/Icon'
import Modal from '../ui/Modal'

// 'YYYY-MM-DD' → 'DD.MM.'
function kurzDatum(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${d}.${m}.`
}

// Detailansicht eines Mitglieds: was hat die Person wann gemacht (neueste zuerst).
export default function PersonDetail({
  user,
  year,
  onClose,
}: {
  user: ComparisonUser
  year: number
  onClose: () => void
}) {
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities, isLoading } = useQuery({
    queryKey: ['user-activities', user.user_id, year],
    queryFn: () => api.userActivities(user.user_id, year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))

  return (
    <Modal open onClose={onClose} title={user.display_name}>
      <div className="mb-3 flex items-center gap-3">
        <Avatar value={user.avatar} size="sm" />
        <div>
          <p className="text-sm font-bold text-ink">
            P{user.rank} · {Math.round(user.total_scaled_km)} km gewertet
          </p>
          <p className="text-xs text-ink-mute">{activities?.length ?? 0} Einträge {year}</p>
        </div>
      </div>
      <div className="max-h-[60vh] space-y-0.5 overflow-y-auto pr-1">
        {isLoading && <p className="text-sm text-ink-mute">Lädt…</p>}
        {activities?.map((a) => {
          const cat = catById.get(a.category_id)
          return (
            <div
              key={a.id}
              className="flex items-center gap-2 border-b border-line/20 py-1.5 text-sm"
            >
              <span className="w-11 shrink-0 font-mono text-xs tabular-nums text-ink-mute">
                {kurzDatum(a.date)}
              </span>
              {cat && <Icon name={cat.icon} size={16} className="shrink-0 text-accent" />}
              <span className="min-w-0 flex-1 truncate text-ink">
                {cat?.name ?? 'Aktivität'}
                {a.note ? <span className="text-ink-mute"> · {a.note}</span> : null}
                {a.elevation_m ? (
                  <span className="text-ink-mute"> · {Math.round(a.elevation_m)} hm</span>
                ) : null}
              </span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-ink-mute">
                {a.distance_km}
              </span>
              <span className="shrink-0 font-mono text-xs font-bold tabular-nums text-accent">
                → {a.scaled_km}
              </span>
              {a.strava_url && (
                <a
                  href={a.strava_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Auf Strava öffnen"
                  className="shrink-0 text-[11px] font-bold text-accent hover:underline"
                >
                  ↗
                </a>
              )}
            </div>
          )
        })}
        {activities && activities.length === 0 && !isLoading && (
          <p className="text-sm text-ink-mute">Noch keine Einträge {year}.</p>
        )}
      </div>
    </Modal>
  )
}
