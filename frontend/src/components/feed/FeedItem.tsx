import { useState } from 'react'
import type { FeedEvent } from '../../api/client'
import Icon from '../ui/Icon'
import RecapCard from './RecapCard'
import ReactionBar from './ReactionBar'

/** ["Ben"] → "Ben"; ["Ben","Clara","David"] → "Ben, Clara und David" */
function undListe(namen: string[]): string {
  if (namen.length <= 1) return namen[0] ?? ''
  return `${namen.slice(0, -1).join(', ')} und ${namen[namen.length - 1]}`
}

const TYP_FARBE: Record<string, string> = {
  rank_change: '#c084fc',
  achievement: '#fbbf24',
  milestone: '#fbbf24',
  recap_week: '#fbbf24',
  recap_month: '#fbbf24',
}

function borderColor(ev: FeedEvent): string {
  if (ev.type === 'activity') return ev.payload.category?.color ?? '#8b8f98'
  return TYP_FARBE[ev.type] ?? '#8b8f98'
}

export default function FeedItem({ ev }: { ev: FeedEvent }) {
  const [infoOffen, setInfoOffen] = useState(false)
  return (
    <div
      className="rounded-xl border border-line bg-card p-3"
      style={{ borderLeft: `3px solid ${borderColor(ev)}` }}
    >
      {ev.type === 'activity' && (
        <>
          <div className="flex items-baseline gap-2 text-sm">
            {ev.payload.category && (
              <Icon name={ev.payload.category.icon} size={16} className="shrink-0 self-center text-accent" />
            )}
            <span className="font-bold text-ink">{ev.display_name}</span>
            <span className="text-ink-mute">· {ev.payload.category?.name}</span>
            <Zeit iso={ev.created_at} />
          </div>
          <p className="mt-0.5 break-words text-[13px] text-ink-soft">
            {ev.payload.titel ? `„${ev.payload.titel}" — ` : ''}
            {ev.payload.distance_km} km →{' '}
            <span className="font-bold text-accent">{ev.payload.mm} MM</span>
            {ev.payload.strava_url && (
              <a
                href={ev.payload.strava_url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-2 rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent hover:bg-accent/10"
              >
                View on Strava
              </a>
            )}
          </p>
        </>
      )}
      {ev.type === 'rank_change' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>📈</span>
          <span className="text-ink">
            <b>{ev.payload.name}</b> überholt{' '}
            <b>
              {undListe(
                ev.payload.ueberholte?.map((u) => u.name) ??
                  (ev.payload.ueberholt_name ? [ev.payload.ueberholt_name] : []),
              )}
            </b>
            <span className="text-ink-mute">
              {' '}
              · Platz {ev.payload.alter_rang ? `${ev.payload.alter_rang} → ` : ''}
            </span>
            <b className="text-accent">{ev.payload.neuer_rang}</b>
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {(ev.type === 'achievement' || ev.type === 'milestone') && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>🏆</span>
          <span className="text-ink">
            <b>{ev.display_name}</b>{' '}
            {ev.type === 'achievement' ? (
              <>
                hat{' '}
                <span
                  role="button"
                  tabIndex={0}
                  className="relative cursor-help font-bold"
                  onMouseEnter={() => setInfoOffen(true)}
                  onMouseLeave={() => setInfoOffen(false)}
                  onClick={() => setInfoOffen((o) => !o)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') setInfoOffen((o) => !o)
                  }}
                >
                  {ev.payload.emoji ? `${ev.payload.emoji} ` : ''}
                  {ev.payload.title}
                  {infoOffen && ev.payload.description && (
                    <span className="absolute bottom-full left-0 z-40 mb-1.5 w-56 rounded-xl border border-line bg-card p-2 text-left shadow-lg">
                      <span className="block text-xs font-bold text-ink">
                        {ev.payload.emoji ? `${ev.payload.emoji} ` : ''}
                        {ev.payload.title}
                      </span>
                      <span className="block text-[11px] font-normal text-ink-mute">
                        {ev.payload.description}
                      </span>
                    </span>
                  )}
                </span>{' '}
                freigeschaltet
              </>
            ) : (
              <>
                hat den Meilenstein <b>{ev.payload.label}</b> erreicht ({ev.payload.km} km)
              </>
            )}
          </span>
          <Zeit iso={ev.created_at} />
        </div>
      )}
      {(ev.type === 'recap_week' || ev.type === 'recap_month') && <RecapCard ev={ev} />}
      <ReactionBar ev={ev} />
    </div>
  )
}

function Zeit({ iso }: { iso: string }) {
  const t = new Date(iso)
  return (
    <span className="ml-auto shrink-0 text-[11px] text-ink-mute">
      {t.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
    </span>
  )
}
