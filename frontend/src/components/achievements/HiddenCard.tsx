import type { Achievement } from '../../api/client'
import ShowcaseToggle from './ShowcaseToggle'

type Props = { a: Achievement; onToggle?: (a: Achievement) => void }

// An unlocked hidden achievement. Locked ones are never rendered (spec chunk 1).
export default function HiddenCard({ a, onToggle }: Props) {
  return (
    <div className="rounded-xl border border-accent p-3 shadow-glow">
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className="text-sm font-bold text-accent">{a.title}</span>
      </div>
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
