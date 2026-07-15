import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Props as LabelProps } from 'recharts/types/component/Label'
import type { DotItemDotProps } from 'recharts/types/util/types'
import { useState } from 'react'
import type { Comparison, ComparisonUser } from '../../api/client'
import Card from '../ui/Card'
import PersonDetail from './PersonDetail'
import { unitLabel, type UnitMode } from './unit'
import { userColor } from './userColor'

export default function JahresVerlauf({ data, mode = 'mm' }: { data: Comparison; mode?: UnitMode }) {
  const [detail, setDetail] = useState<ComparisonUser | null>(null)
  const [visible, setVisible] = useState<Set<number>>(() => new Set(data.users.map((u) => u.user_id)))
  // Kurven zu einem gemeinsamen Datensatz mergen: eine Zeile pro Datum.
  const byDate = new Map<string, Record<string, number | string>>()
  for (const u of data.users) {
    for (const p of u.cumulative) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[u.display_name] = mode === 'km' ? p.real_km : p.scaled_km
      byDate.set(p.date, row)
    }
  }
  const rows = [...byDate.values()].sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )
  const ids = data.users.map((u) => u.user_id)
  // Letzter Datenpunkt je Person — dort sitzen Endpunkt-Dot und Namens-Label.
  const lastIndex = new Map<string, number>()
  for (const u of data.users) {
    for (let i = rows.length - 1; i >= 0; i--) {
      if (rows[i][u.display_name] !== undefined) {
        lastIndex.set(u.display_name, i)
        break
      }
    }
  }

  return (
    <Card>
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={rows} margin={{ top: 8, right: 90, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--t-line)" strokeOpacity={0.25} vertical={false} />
          <XAxis
            dataKey="date"
            fontSize={11}
            stroke="var(--t-ink-mute)"
            tickLine={false}
            axisLine={{ stroke: 'var(--t-line)' }}
          />
          <YAxis fontSize={11} unit={` ${unitLabel(mode)}`} stroke="var(--t-ink-mute)" tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{
              background: 'var(--t-card)',
              border: '1px solid var(--t-line)',
              borderRadius: 12,
              color: 'var(--t-ink)',
            }}
            labelStyle={{ color: 'var(--t-ink-mute)' }}
          />
          {mode === 'mm' && data.milestones.map((m) => (
            <ReferenceLine
              key={m.km}
              y={m.km}
              stroke="var(--t-ink-mute)"
              strokeOpacity={0.5}
              strokeDasharray="5 4"
              label={{ value: m.label, fontSize: 11, position: 'right', fill: 'var(--t-ink-mute)' }}
            />
          ))}
          {mode === 'mm' && (
            <ReferenceLine
              y={data.goal_km}
              stroke="var(--t-accent)"
              label={{ value: 'Ziel', fontSize: 11, fill: 'var(--t-accent)' }}
            />
          )}
          {data.users.filter((u) => visible.has(u.user_id)).map((u) => {
            const farbe = userColor(u.user_id, ids)
            const letzte = lastIndex.get(u.display_name)
            return (
              <Line
                key={u.user_id}
                dataKey={u.display_name}
                stroke={farbe}
                strokeWidth={2.5}
                connectNulls
                style={{ filter: `drop-shadow(0 0 4px ${farbe})` }}
                dot={(p: DotItemDotProps) =>
                  p.index === letzte ? (
                    <circle key={`dot-${p.index}`} cx={p.cx} cy={p.cy} r={4} fill={farbe} />
                  ) : (
                    <g key={`dot-empty-${p.index}`} />
                  )
                }
                label={(p: LabelProps) =>
                  p.index === letzte ? (
                    <text
                      key={`label-${p.index}`}
                      x={(typeof p.x === 'number' ? p.x : 0) + 8}
                      y={(typeof p.y === 'number' ? p.y : 0) + 4}
                      fontSize={11}
                      fontWeight={700}
                      fill={farbe}
                    >
                      {u.display_name}
                    </text>
                  ) : (
                    <g key={`label-empty-${p.index}`} />
                  )
                }
              />
            )
          })}
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setVisible(new Set(data.users.map((u) => u.user_id)))}
          className="rounded-full border border-line px-2.5 py-1 text-xs font-bold text-ink-mute transition hover:text-ink"
        >
          Alle
        </button>
        <button
          type="button"
          onClick={() => setVisible(new Set())}
          className="rounded-full border border-line px-2.5 py-1 text-xs font-bold text-ink-mute transition hover:text-ink"
        >
          Keine
        </button>
        {data.users.map((u) => {
          const an = visible.has(u.user_id)
          const farbe = userColor(u.user_id, ids)
          return (
            <span
              key={u.user_id}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
                an ? 'text-ink' : 'text-ink-mute opacity-50'
              }`}
              style={{ borderColor: an ? farbe : 'var(--t-line)' }}
            >
              <button
                type="button"
                aria-pressed={an}
                aria-label={`${u.display_name} ein-/ausblenden`}
                onClick={() =>
                  setVisible((prev) => {
                    const next = new Set(prev)
                    if (next.has(u.user_id)) next.delete(u.user_id)
                    else next.add(u.user_id)
                    return next
                  })
                }
                className="flex items-center gap-1.5"
              >
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: an ? farbe : 'var(--t-ink-mute)' }} />
                {u.display_name}
              </button>
              <button
                type="button"
                aria-label={`Details zu ${u.display_name}`}
                onClick={() => setDetail(u)}
                className="flex h-4 w-4 items-center justify-center rounded-full border border-line text-[9px] text-ink-mute transition hover:border-accent hover:text-accent"
              >
                i
              </button>
            </span>
          )
        })}
      </div>
      {detail && (
        <PersonDetail user={detail} year={data.year} onClose={() => setDetail(null)} />
      )}
    </Card>
  )
}
