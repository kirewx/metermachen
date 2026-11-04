import { useQuery } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { api } from '../../api/client'
import { TogetherPanel, TogetherStapel } from '../together/TogetherBadge'
import { hatBadge, useTogetherAktiv } from '../together/together'
import Icon from '../ui/Icon'

// 'YYYY-MM-DD' → 'DD.MM.'
function kurzDatum(iso: string): string {
  const [, m, d] = iso.split('-')
  return `${d}.${m}.`
}

/** Was hat die Person wann gemacht (neueste zuerst) — Sektion der Profilseite. */
export default function AktivitaetenListe({ userId, year }: { userId: number; year: number }) {
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities, isLoading } = useQuery({
    queryKey: ['user-activities', userId, year],
    queryFn: () => api.userActivities(userId, year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))
  const together = useTogetherAktiv()
  const [badgeOffen, setBadgeOffen] = useState<number | null>(null)

  return (
    <div className="max-h-[60vh] space-y-0.5 overflow-y-auto pr-1">
      {isLoading && <p className="text-sm text-ink-mute">Lädt…</p>}
      {activities?.map((a) => {
        const cat = catById.get(a.category_id)
        // Fremde Sicht (auch fürs eigene Profil): nur bestätigte Sessions, keine Buttons
        const badge = together && hatBadge(a.together, false) ? a.together : null
        return (
          <Fragment key={a.id}>
            <div className="flex items-center gap-2 border-b border-line/20 py-1.5 text-sm">
              <span className="w-11 shrink-0 font-mono text-xs tabular-nums text-ink-mute">
                {kurzDatum(a.date)}
              </span>
              {cat && <Icon name={cat.icon} size={16} className="shrink-0 text-accent" />}
              <span className="min-w-0 flex-1 break-words text-ink">
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
              {badge && (
                <TogetherStapel
                  together={badge}
                  own={false}
                  offen={badgeOffen === a.id}
                  onToggle={() => setBadgeOffen(badgeOffen === a.id ? null : a.id)}
                />
              )}
            </div>
            {badge && badgeOffen === a.id && <TogetherPanel together={badge} own={false} />}
          </Fragment>
        )
      })}
      {activities && activities.length === 0 && !isLoading && (
        <p className="text-sm text-ink-mute">Noch keine Einträge {year}.</p>
      )}
    </div>
  )
}
