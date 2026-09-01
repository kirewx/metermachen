import type { Achievement } from '../../api/client'
import Icon from '../ui/Icon'

// Hours below 24 h, days from there on, one decimal each.
function formatLeadTime(hours: number) {
  if (hours < 24) {
    return `${hours.toLocaleString('de-DE', { maximumFractionDigits: 1 })} h`
  }
  const days = hours / 24
  return `${days.toLocaleString('de-DE', { maximumFractionDigits: 1 })} Tage`
}

// "Zeit an der Spitze": a running timer instead of a target value.
export default function TimeAtTopCard({ a }: { a: Achievement }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        a.achieved ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon
          name={a.icon}
          size={20}
          className={a.achieved ? 'text-accent' : 'text-ink-mute'}
        />
        <span className={`text-sm font-bold ${a.achieved ? 'text-accent' : 'text-ink'}`}>
          {a.title}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      <p className="mt-2 flex items-center gap-2 font-mono text-lg font-bold tabular-nums text-ink">
        {formatLeadTime(a.timer_hours ?? 0)}
        {a.timer_running && (
          <span
            className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent"
            title="Timer läuft — aktuell an der Spitze"
          />
        )}
      </p>
    </div>
  )
}
