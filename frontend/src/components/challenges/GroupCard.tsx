import { useState } from 'react'
import type { Challenge, ChallengeGroup } from '../../api/client'
import Avatar from '../ui/Avatar'
import TeamEinstellungen from './TeamEinstellungen'
import { teamFarbe, tint } from './teamFarben'
import WertungsChip from './WertungsChip'
import { einheit, fortschritt } from './wertung'

// One group in the detail view: header with chip and progress, members below.
// `hoechster` is the leading group's per-head value (ranking mode bars).
export default function GroupCard({
  ch, g, mine, hoechster,
}: { ch: Challenge; g: ChallengeGroup; mine: boolean; hoechster: number }) {
  const pct = ch.mode === 'ziel' ? fortschritt(ch, g.value) * 100 : (g.value / hoechster) * 100
  const farbe = teamFarbe(g)
  const [bearbeiten, setBearbeiten] = useState(false)
  return (
    <div
      data-testid="group-card"
      className={`rounded-2xl border bg-card p-3 ${mine ? 'border-accent' : ''}`}
      style={mine ? undefined : { borderColor: tint(farbe, 0.55) }}
    >
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: farbe }} />
        <span className="min-w-0 flex-1 truncate text-sm font-extrabold" style={{ color: farbe }}>
          {g.name}
        </span>
        {ch.kann_gruppen_umbenennen && !bearbeiten && (
          <button
            type="button"
            onClick={() => setBearbeiten(true)}
            aria-label={`${g.name}: Name und Farbe ändern`}
            className="shrink-0 rounded-full px-1.5 text-xs text-ink-mute hover:text-accent"
          >
            ✎
          </button>
        )}
        {g.id === ch.sieger_group_id && <span className="shrink-0 text-sm">🏆</span>}
        {mine && <span className="shrink-0 text-[10px] font-bold text-accent">du</span>}
        <WertungsChip ch={ch} rank={g.rank} geschafft={g.geschafft} value={g.value} proKopf />
      </div>
      <p className="mt-1 text-xs text-ink-soft">
        {g.sum} {einheit(ch.metric)} · {g.value} pro Kopf
      </p>
      {bearbeiten && <TeamEinstellungen ch={ch} g={g} onClose={() => setBearbeiten(false)} />}
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
        <div className="h-full" style={{ width: `${pct}%`, background: farbe }} />
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
