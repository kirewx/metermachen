import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Comparison } from '../../api/client'

const COLORS = ['#e74c3c', '#3498db', '#27ae60', '#9b59b6', '#e67e22', '#16a085', '#d35400']

export default function JahresVerlauf({ data }: { data: Comparison }) {
  // Kurven zu einem gemeinsamen Datensatz mergen: eine Zeile pro Datum.
  const byDate = new Map<string, Record<string, number | string>>()
  for (const u of data.users) {
    for (const p of u.cumulative) {
      const row = byDate.get(p.date) ?? { date: p.date }
      row[u.display_name] = p.scaled_km
      byDate.set(p.date, row)
    }
  }
  const rows = [...byDate.values()].sort((a, b) =>
    String(a.date).localeCompare(String(b.date)),
  )

  return (
    <div className="rounded-2xl bg-white p-4 shadow">
      <ResponsiveContainer width="100%" height={380}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" fontSize={11} />
          <YAxis fontSize={11} unit=" km" />
          <Tooltip />
          <Legend />
          {data.milestones.map((m) => (
            <ReferenceLine
              key={m.km}
              y={m.km}
              stroke="#999"
              strokeDasharray="5 4"
              label={{ value: m.label, fontSize: 11, position: 'right' }}
            />
          ))}
          <ReferenceLine y={data.goal_km} stroke="#e0b84e" label={{ value: '🏁 Ziel', fontSize: 11 }} />
          {data.users.map((u, i) => (
            <Line
              key={u.user_id}
              dataKey={u.display_name}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2.5}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
