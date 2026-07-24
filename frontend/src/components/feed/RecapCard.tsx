// RecapCard.tsx (Platzhalter, Task 9 füllt ihn)
import type { FeedEvent } from '../../api/client'
export default function RecapCard({ ev }: { ev: FeedEvent }) {
  return <p className="text-sm font-bold text-ink">📊 Rückblick {ev.payload.label}</p>
}
