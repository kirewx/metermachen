// ReactionBar.tsx (Platzhalter, Task 9 füllt ihn)
import type { FeedEvent } from '../../api/client'
export default function ReactionBar({ ev }: { ev: FeedEvent }) {
  if (ev.reactions.length === 0) return null
  return (
    <div className="mt-2 flex gap-1.5">
      {ev.reactions.map((r) => (
        <span key={r.emoji} className="rounded-full border border-line px-2 py-0.5 text-xs">
          {r.emoji} {r.count}
        </span>
      ))}
    </div>
  )
}
