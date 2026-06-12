import type { Comparison } from '../../api/client'

export default function RaceBahnen({ data }: { data: Comparison }) {
  const maxKm = Math.max(data.goal_km, ...data.users.map((u) => u.total_scaled_km))
  const pct = (km: number) => `${(km / maxKm) * 100}%`

  return (
    <div className="overflow-x-auto rounded-2xl bg-white p-4 shadow">
      <div className="relative min-w-[700px] space-y-5 pt-6 pb-2">
        {data.milestones.map((m) => (
          <div
            key={m.km}
            className="absolute top-0 bottom-0 border-l-2 border-dashed border-gray-300"
            style={{ left: pct(m.km) }}
          >
            <span className="absolute -top-1 -translate-x-1/2 text-xs whitespace-nowrap text-gray-500">
              {m.emoji} {m.km}
            </span>
          </div>
        ))}
        <div
          className="absolute top-0 bottom-0 border-l-2 border-amber-400"
          style={{ left: pct(data.goal_km) }}
        >
          <span className="absolute -top-1 -translate-x-1/2 text-xs text-amber-600">
            🏁 {data.goal_km}
          </span>
        </div>
        {data.users.map((u) => (
          <div key={u.user_id}>
            <p className="mb-1 text-sm font-semibold">
              {u.rank === 1 ? '👑 ' : ''}{u.avatar_emoji} {u.display_name} ·{' '}
              {Math.round(u.total_scaled_km)} km
            </p>
            <div className="flex h-5 overflow-hidden rounded-full bg-gray-100">
              {u.segments.map((s, i) => (
                <div
                  key={i}
                  style={{ width: pct(s.scaled_km), background: s.color }}
                  title={`${s.date}: ${s.scaled_km} km`}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
