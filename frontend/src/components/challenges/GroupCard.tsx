import type { Challenge, ChallengeGroup } from '../../api/client'
import Avatar from '../ui/Avatar'
import { einheit, fortschritt } from './wertung'

function GroupChip({ ch, g }: { ch: Challenge; g: ChallengeGroup }) {
  if (ch.mode === 'rangliste')
    return (
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
          g.geschafft ? 'bg-accent text-accent-ink' : 'border border-line text-ink-mute'
        }`}
      >
        Platz {g.rank}
      </span>
    )
  if (g.geschafft)
    return (
      <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold text-accent-ink">
        geschafft
      </span>
    )
  const rest = Math.max((ch.target ?? 0) - g.value, 0)
  return (
    <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
      noch {Math.round(rest * 100) / 100} pro Kopf
    </span>
  )
}

// One group in the detail view: header with chip and progress, members below.
// `hoechster` is the leading group's per-head value (ranking mode bars).
export default function GroupCard({
  ch, g, mine, hoechster,
}: { ch: Challenge; g: ChallengeGroup; mine: boolean; hoechster: number }) {
  const pct = ch.mode === 'ziel' ? fortschritt(ch, g.value) * 100 : (g.value / hoechster) * 100
  return (
    <div
      data-testid="group-card"
      className={`rounded-2xl border bg-card p-3 ${mine ? 'border-accent' : 'border-line'}`}
    >
      <div className="flex items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-extrabold text-ink">
          {g.name}
          {g.id === ch.sieger_group_id && ' 🏆'}
          {mine && <span className="ml-1 text-[10px] font-bold text-accent">du</span>}
        </span>
        <GroupChip ch={ch} g={g} />
      </div>
      <p className="mt-1 text-xs text-ink-soft">
        {g.sum} {einheit(ch.metric)} · {g.value} pro Kopf
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
        <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
      <ul className="mt-2 space-y-1">
        {g.members.map((m) => (
          <li key={m.user_id} className="flex items-center gap-2 text-xs">
            <Avatar value={m.avatar} size="sm" />
            <span className="min-w-0 flex-1 truncate text-ink">
              {m.display_name}
              {m.user_id === ch.sieger_id && ' 🏆'}
            </span>
            <span className="shrink-0 font-bold text-ink">
              {m.value} {einheit(ch.metric)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
