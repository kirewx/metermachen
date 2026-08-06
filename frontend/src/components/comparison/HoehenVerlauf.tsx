import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Comparison, ComparisonUser } from '../../api/client'
import { BREIT_BIS } from './hoehenAuswahl'
import { formatHm, sichtbareBerge } from './monatsFarbe'
import { userColor } from './userColor'

/** Höhenmeter-Stand einer Person an jedem Stichtag, Lücken werden fortgeschrieben. */
function standJeDatum(user: ComparisonUser, daten: string[]): number[] {
  let i = 0
  let letzter = 0
  return daten.map((d) => {
    while (i < user.cumulative.length && user.cumulative[i].date <= d) {
      letzter = user.cumulative[i].elevation_m
      i++
    }
    return letzter
  })
}

function median(werte: number[]): number {
  if (werte.length === 0) return 0
  const s = [...werte].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

/**
 * Kurven über die Zeit. Bei 30 Linien wäre das Spaghetti, deshalb liegt immer ein
 * graues Band zwischen Median und Spitzenreiter im Hintergrund: solange viele
 * Personen ausgewählt sind, sieht man nur das Feld und die eigene Linie. Erst bei
 * einer überschaubaren Auswahl bekommt jede Person ihre eigene Kurve.
 */
export default function HoehenVerlauf({
  data,
  auswahl,
  meId,
}: {
  data: Comparison
  auswahl: Set<number>
  meId: number | null
}) {
  const daten = [...new Set(data.users.flatMap((u) => u.cumulative.map((p) => p.date)))].sort()
  const staende = new Map(data.users.map((u) => [u.user_id, standJeDatum(u, daten)]))
  const ids = data.users.map((u) => u.user_id)
  const gewaehlt = data.users.filter((u) => auswahl.has(u.user_id))
  const einzeln = gewaehlt.length <= BREIT_BIS
  const linien = einzeln ? gewaehlt : data.users.filter((u) => u.user_id === meId)

  const rows = daten.map((d, i) => {
    const alle = data.users.map((u) => staende.get(u.user_id)![i])
    const row: Record<string, number | string | number[]> = {
      date: d,
      band: [median(alle), Math.max(0, ...alle)],
    }
    for (const u of linien) row[u.display_name] = staende.get(u.user_id)![i]
    return row
  })
  const max = Math.max(0, ...rows.map((r) => (r.band as number[])[1]))

  return (
    <div className="space-y-2">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--t-line)" strokeOpacity={0.25} vertical={false} />
          <XAxis
            dataKey="date"
            fontSize={10}
            stroke="var(--t-ink-mute)"
            tickLine={false}
            axisLine={{ stroke: 'var(--t-line)' }}
            minTickGap={24}
          />
          <YAxis
            fontSize={10}
            unit=" hm"
            width={52}
            stroke="var(--t-ink-mute)"
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--t-card)',
              border: '1px solid var(--t-line)',
              borderRadius: 12,
              color: 'var(--t-ink)',
            }}
            labelStyle={{ color: 'var(--t-ink-mute)' }}
          />
          {sichtbareBerge(max).map((berg) => (
            <ReferenceLine
              key={berg.name}
              y={berg.meters}
              stroke="var(--t-ink-mute)"
              strokeOpacity={0.5}
              strokeDasharray="5 4"
              label={{
                value: `${berg.name} ${formatHm(berg.meters)}`,
                fontSize: 9,
                position: 'insideTopRight',
                fill: 'var(--t-ink-mute)',
              }}
            />
          ))}
          <Area
            dataKey="band"
            name="Feld (Median bis Spitze)"
            stroke="none"
            fill="var(--t-ink-mute)"
            fillOpacity={0.16}
            isAnimationActive={false}
          />
          {linien.map((u) => {
            const farbe = userColor(u.user_id, ids)
            return (
              <Line
                key={u.user_id}
                dataKey={u.display_name}
                stroke={farbe}
                strokeWidth={u.user_id === meId ? 3 : 2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            )
          })}
        </ComposedChart>
      </ResponsiveContainer>
      {!einzeln && (
        <p className="text-center text-[11px] text-ink-mute">
          {gewaehlt.length} Personen ausgewählt — gezeigt werden das Feld (Median bis Spitze)
          und deine Linie. Für einzelne Kurven höchstens {BREIT_BIS} Personen auswählen.
        </p>
      )}
    </div>
  )
}
