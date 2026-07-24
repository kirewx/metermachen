import { useState } from 'react'
import type { Auszeichnung } from '../../api/client'

/** Emoji-Badges mit Popover (Hover + Tap): "Hattrick — Drei Aktivitäten…" */
export default function AuszeichnungsBadges({ liste }: { liste: Auszeichnung[] }) {
  const [offen, setOffen] = useState<number | null>(null)
  if (liste.length === 0) return null
  return (
    <span className="relative ml-1.5 text-xs">
      {liste.map((a, i) => (
        <span
          key={`${a.emoji}-${i}`}
          role="button"
          tabIndex={0}
          className="cursor-help"
          onMouseEnter={() => setOffen(i)}
          onMouseLeave={() => setOffen((o) => (o === i ? null : o))}
          onClick={(e) => {
            e.stopPropagation()
            e.preventDefault()
            setOffen((o) => (o === i ? null : i))
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') setOffen((o) => (o === i ? null : i))
          }}
        >
          {a.emoji}
          {offen === i && (
            <span className="absolute bottom-full left-0 z-40 mb-1.5 w-56 rounded-xl border border-line bg-card p-2 text-left shadow-lg">
              <span className="block text-xs font-bold text-ink">{a.title}</span>
              <span className="block text-[11px] font-normal text-ink-mute">
                {a.description}
              </span>
            </span>
          )}
        </span>
      ))}
    </span>
  )
}
