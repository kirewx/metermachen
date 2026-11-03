import type { Achievement } from '../../api/client'
import CounterPill from './CounterPill'
import ShowcaseToggle from './ShowcaseToggle'

type Props = { a: Achievement; onToggle?: (a: Achievement) => void }

// An unlocked hidden achievement. Locked ones are never rendered (spec chunk 1).
export default function HiddenCard({ a, onToggle }: Props) {
  return (
    <div className="rounded-xl border border-accent p-3 shadow-glow">
      <div className="flex items-start gap-2">
        <span className="shrink-0 text-lg leading-5">{a.emoji}</span>
        <span className="min-w-0 text-sm leading-5 font-bold text-accent [overflow-wrap:anywhere] hyphens-auto">
          {a.title}
        </span>
      </div>
      {a.counter && <CounterPill text={a.counter} />}
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {a.unlocked_at && (
        <p className="mt-1 font-mono text-[10px] text-ink-mute">
          freigeschaltet am {new Date(a.unlocked_at).toLocaleDateString('de-DE')}
        </p>
      )}
      {onToggle && <ShowcaseToggle a={a} onToggle={onToggle} />}
    </div>
  )
}
