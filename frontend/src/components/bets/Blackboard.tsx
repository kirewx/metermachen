/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react'
import type { Bet } from '../../api/client'
import Card from '../ui/Card'
import Select from '../ui/Select'
import type { Spieler } from './BetCard'

const TYP_LABEL: Record<Bet['type'], string> = {
  duell: 'Duell',
  monats_tipp: 'Monats-Tipp',
  ziel: 'Ziel-Wette',
  streak: 'Streak-Wette',
  ueber_unter: 'Über/Unter',
}

function datum(d: string) {
  return new Date(`${d}T00:00:00`).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
  })
}

function beteiligte(bet: Bet): number[] {
  const ids = new Set<number>([bet.creator_id])
  if (bet.params.opponent_id) ids.add(bet.params.opponent_id)
  for (const p of bet.participants) ids.add(p.user_id)
  return [...ids]
}

export function filtereBlackboard(
  bets: Bet[],
  filter: { personId: number | null; typ: Bet['type'] | null },
): Bet[] {
  return bets
    .filter((b) => b.status === 'offen' || b.status === 'laufend')
    .filter((b) => filter.typ === null || b.type === filter.typ)
    .filter((b) => filter.personId === null || beteiligte(b).includes(filter.personId))
}

export default function Blackboard({ bets, spieler }: { bets: Bet[]; spieler: Spieler[] }) {
  const [personId, setPersonId] = useState<number | null>(null)
  const [typ, setTyp] = useState<Bet['type'] | null>(null)
  const zeilen = filtereBlackboard(bets, { personId, typ })
  const name = (id: number | undefined) => {
    const s = spieler.find((sp) => sp.user_id === id)
    if (!s) return `#${id}`
    const emojis = s.emojis ?? []
    return emojis.length > 0 ? `${s.display_name} ${emojis.join(' ')}` : s.display_name
  }

  return (
    <Card>
      <div className="mb-3 flex flex-wrap gap-3">
        <Select
          label="Person"
          value={personId ?? ''}
          onChange={(e) => setPersonId(e.target.value ? Number(e.target.value) : null)}
          className="w-40"
        >
          <option value="">Alle</option>
          {spieler.map((s) => (
            <option key={s.user_id} value={s.user_id}>
              {s.display_name}
            </option>
          ))}
        </Select>
        <Select
          label="Wett-Typ"
          value={typ ?? ''}
          onChange={(e) => setTyp((e.target.value || null) as Bet['type'] | null)}
          className="w-40"
        >
          <option value="">Alle</option>
          {Object.entries(TYP_LABEL).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </Select>
      </div>
      {zeilen.length === 0 && (
        <p className="text-sm text-ink-mute">Nichts an der Tafel — Zeit für eine Wette.</p>
      )}
      <ul className="divide-y divide-line/30">
        {zeilen.map((b) => (
          <li key={b.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 py-2 text-sm">
            <span className="font-bold text-ink">
              {b.type === 'duell'
                ? `${name(b.creator_id)} ⚔️ ${name(b.params.opponent_id)}`
                : beteiligte(b).map((id) => name(id)).join(', ')}
            </span>
            <span className="rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-tech">
              {TYP_LABEL[b.type]}
            </span>
            <span className="min-w-0 flex-1 truncate text-ink-soft">{b.title}</span>
            <span className="font-bold text-accent">{b.stake} P</span>
            <span className="font-mono text-xs text-ink-mute">
              {datum(b.period_start)}–{datum(b.period_end)}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
