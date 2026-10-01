import type { Achievement } from '../../api/client'
import Icon from '../ui/Icon'
import ShowcaseToggle from './ShowcaseToggle'

type Props = { stages: Achievement[]; onToggle?: (a: Achievement) => void }

function formatValue(value: number, unit: string | null | undefined) {
  if (unit === 'h') return value.toLocaleString('de-DE', { maximumFractionDigits: 1 })
  return Math.round(value).toLocaleString('de-DE')
}

// A stacking ladder (MM-Club, hours per category): stage pills, and a bar that
// always measures towards the next stage — 5 h of 10 h fills it halfway.
export default function LadderCard({ stages, onToggle }: Props) {
  const first = stages[0]
  const next = stages.find((s) => !s.achieved)
  const reached = stages.filter((s) => s.achieved)
  return (
    <div
      className={`rounded-xl border p-3 ${
        reached.length > 0 ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon name={first.icon} size={20} className="text-accent" />
        <span className="text-sm font-bold text-ink">{first.ladder_title}</span>
        {first.unit === 'h' && <span className="text-[10px] text-ink-mute">Zeit</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {stages.map((s) => (
          <span
            key={s.key}
            title={s.title}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
              s.achieved ? 'border-accent text-accent' : 'border-line/40 text-ink-mute'
            }`}
          >
            {s.stage}
            {s.achieved && s.emoji ? ` ${s.emoji}` : ''}
          </span>
        ))}
      </div>
      {next && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(next.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] tabular-nums text-ink-mute">
            {formatValue(next.parts[0]?.current_km ?? 0, next.unit)}/
            {formatValue(next.parts[0]?.target_km ?? 0, next.unit)} {next.unit} bis {next.stage}
          </p>
        </>
      )}
      {onToggle &&
        reached
          .filter((s) => s.emoji)
          .map((s) => <ShowcaseToggle key={s.key} a={s} onToggle={onToggle} />)}
    </div>
  )
}
