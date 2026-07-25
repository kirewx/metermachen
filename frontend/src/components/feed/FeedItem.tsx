import type { FeedEvent } from '../../api/client'
import Icon from '../ui/Icon'
import RecapCard from './RecapCard'
import ReactionBar from './ReactionBar'

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
          </p>
        </>
      )}
      {ev.type === 'rank_change' && (
        <div className="flex items-baseline gap-2 text-sm">
          <span>📈</span>
          <span className="text-ink">
            <b>{ev.payload.name}</b> überholt <b>{ev.payload.ueberholt_name}</b> → Platz{' '}
            {ev.payload.neuer_rang}
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
                hat <b>{ev.payload.emoji ? `${ev.payload.emoji} ` : ''}{ev.payload.title}</b>{' '}
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
