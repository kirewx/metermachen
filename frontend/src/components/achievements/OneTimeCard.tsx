import type { Achievement } from '../../api/client'
import { NO_RACE_KEYS } from './constants'
import ShowcaseToggle from './ShowcaseToggle'

type Props = { a: Achievement; onToggle?: (a: Achievement) => void }

// Emoji achievements: first-to-gold races, warm-up specials, early bird.
export default function OneTimeCard({ a, onToggle }: Props) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        a.achieved ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className={`text-sm font-bold ${a.achieved ? 'text-accent' : 'text-ink'}`}>
          {a.title}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {!a.achieved && a.parts.length > 0 && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(a.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] tabular-nums text-ink-mute">
            {Math.round(a.parts[0].current_km)}/{Math.round(a.parts[0].target_km)} MM
          </p>
        </>
      )}
      {!a.achieved && a.parts.length === 0 && !NO_RACE_KEYS.has(a.key) && (
        <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-ink-mute">
          {a.claimed_by ? `vergeben an ${a.claimed_by}` : 'bekommt nur die erste Person'}
        </p>
      )}
      {onToggle && <ShowcaseToggle a={a} onToggle={onToggle} />}
    </div>
  )
}
