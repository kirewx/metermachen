import type { Achievement } from '../../api/client'

type Props = { a: Achievement; onToggle: (a: Achievement) => void }

// Wear the special emoji next to your name, or take it off.
export default function ShowcaseToggle({ a, onToggle }: Props) {
  if (!a.achieved || !a.emoji) return null
  const on = a.showcased ?? true
  return (
    <button
      type="button"
      onClick={() => onToggle(a)}
      className={`mt-2 flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
        on ? 'border-accent text-accent' : 'border-line text-ink-mute'
      }`}
      title="Emoji neben deinem Namen anzeigen"
    >
      <span className="text-sm">{a.emoji}</span>
      {on ? 'wird getragen' : 'abgelegt'}
    </button>
  )
}
