import type { Comparison } from '../../api/client'
import Avatar from '../ui/Avatar'
import Card from '../ui/Card'
import Icon from '../ui/Icon'
import { userColor } from './userColor'

export default function RaceBahnen({ data }: { data: Comparison }) {
  const maxKm = Math.max(data.goal_km, ...data.users.map((u) => u.total_scaled_km))
  const pct = (km: number) => `${(km / maxKm) * 100}%`
  const ids = data.users.map((u) => u.user_id)
  const fuehrend = data.users.find((u) => u.rank === 1)

  return (
    <Card className="overflow-x-auto">
      <div className="min-w-[640px] space-y-3">
        {/* Kopfzeile: Meilenstein- und Ziel-Marker über der Bahnspur */}
        <div className="flex items-end gap-3">
          <div className="w-44 shrink-0" />
          <div className="relative h-9 flex-1">
            {data.milestones.map((m) => (
              <span
                key={m.km}
                className="absolute flex -translate-x-1/2 flex-col items-center text-ink-mute"
                style={{ left: pct(m.km) }}
              >
                <Icon name={m.icon} size={13} />
                <span className="text-[9px] tabular-nums">{m.km}</span>
              </span>
            ))}
            <span
              className="absolute flex -translate-x-1/2 flex-col items-center text-accent"
              style={{ left: pct(data.goal_km) }}
            >
              <Icon name="fahne" size={13} />
              <span className="text-[9px] font-bold tabular-nums">{data.goal_km}</span>
            </span>
          </div>
          <div className="w-24 shrink-0" />
        </div>
        {data.users.map((u) => {
          const farbe = userColor(u.user_id, ids)
          const fuehrt = u.rank === 1
          const abstand =
            fuehrend && !fuehrt ? Math.round(fuehrend.total_scaled_km - u.total_scaled_km) : 0
          return (
            <div key={u.user_id} className="flex items-center gap-3">
              <div className="flex w-44 shrink-0 items-center gap-2">
                <span
                  className={`w-7 text-sm font-black tabular-nums ${
                    fuehrt ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
                  }`}
                >
                  P{u.rank}
                </span>
                <Avatar value={u.avatar} size="sm" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-ink">
                    {u.display_name}
                    {u.km_factor !== 1 && (
                      <span
                        title="Handicap-Faktor"
                        className="ml-1.5 font-mono text-[10px] font-normal text-ink-mute"
                      >
                        ×{u.km_factor}
                      </span>
                    )}
                  </p>
                  {!fuehrt && (
                    <p className="text-[10px] text-ink-mute">−{abstand} km auf P1</p>
                  )}
                </div>
              </div>
              <div className="relative h-5 flex-1 overflow-hidden rounded-full border border-line bg-surface">
                {data.milestones.map((m) => (
                  <span
                    key={m.km}
                    className="absolute top-0 bottom-0 w-px bg-line"
                    style={{ left: pct(m.km) }}
                  />
                ))}
                <div
                  className="balken-wachsen absolute inset-y-0 left-0 rounded-full"
                  style={{
                    width: pct(u.total_scaled_km),
                    background: `linear-gradient(90deg, transparent, ${farbe})`,
                    boxShadow: fuehrt ? `0 0 14px ${farbe}` : `0 0 6px ${farbe}55`,
                  }}
                />
              </div>
              <p className="w-24 shrink-0 text-right text-lg font-black tabular-nums text-ink">
                {Math.round(u.total_scaled_km)}{' '}
                <span className="text-xs font-normal text-ink-mute">km</span>
              </p>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
