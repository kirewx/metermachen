import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import type { Comparison, ComparisonUser } from '../../api/client'
import Avatar from '../ui/Avatar'
import Card from '../ui/Card'
import Icon from '../ui/Icon'
import PersonDetail from './PersonDetail'
import { computeSinceLastSeen, describeSinceLastSeen } from './sinceLastSeen'
import { toDisplay, unitLabel, type UnitMode } from './unit'
import { userColor } from './userColor'

export default function RaceBahnen({ data, mode = 'mm' }: { data: Comparison; mode?: UnitMode }) {
  const [detail, setDetail] = useState<ComparisonUser | null>(null)
  const { data: lastSeen } = useQuery({
    queryKey: ['comparison-last-seen', data.year],
    queryFn: () => api.lastSeenComparison(data.year),
  })
  // "Jetzt" einmal beim Öffnen der Ansicht einfrieren — stabil über Re-Renders
  // und erfüllt die Purity-Regel (kein Date.now() im Render).
  const [nowMs] = useState(() => Date.now())
  const since = computeSinceLastSeen(data.users, lastSeen ?? null, nowMs)
  const [grown, setGrown] = useState(false)
  const marked = useRef(false)
  useEffect(() => {
    if (!since.active) return
    const t = setTimeout(() => setGrown(true), 60)
    return () => clearTimeout(t)
  }, [since.active])
  useEffect(() => {
    if (!since.active || marked.current) return
    marked.current = true
    const t = setTimeout(() => {
      api.markComparisonSeen(data.year).catch(() => {})
    }, 1600)
    return () => clearTimeout(t)
  }, [since.active, data.year])
  const maxKm = Math.max(data.goal_km, ...data.users.map((u) => u.total_scaled_km))
  const pct = (km: number) => `${(km / maxKm) * 100}%`
  const ids = data.users.map((u) => u.user_id)
  const fuehrend = data.users.find((u) => u.rank === 1)

  return (
    <Card className="overflow-x-auto">
      {since.active && (
        <div className="mb-3 rounded-xl border border-accent/40 bg-accent/10 px-3 py-2 text-sm text-ink">
          ⏱ {describeSinceLastSeen(since, data.users)}
        </div>
      )}
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
              <button
                type="button"
                onClick={() => setDetail(u)}
                aria-label={`Details zu ${u.display_name}`}
                className="flex w-44 shrink-0 items-center gap-2 rounded-lg text-left transition hover:opacity-80"
              >
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
                    {(u.emojis ?? []).length > 0 && (
                      <span className="ml-1.5 text-xs" title="Erspielte Auszeichnungen">
                        {(u.emojis ?? []).join(' ')}
                      </span>
                    )}
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
              </button>
              <div className="relative h-5 flex-1 overflow-hidden rounded-full border border-line bg-surface">
                {data.milestones.map((m) => (
                  <span
                    key={m.km}
                    className="absolute top-0 bottom-0 w-px bg-line"
                    style={{ left: pct(m.km) }}
                  />
                ))}
                {since.active && since.perUser[u.user_id]?.delta > 0 && (
                  <>
                    <div
                      className="absolute inset-y-0 left-0 rounded-full bg-ink-mute/25"
                      style={{ width: pct(since.perUser[u.user_id].prevScaled) }}
                    />
                    <span
                      className="absolute top-[-3px] bottom-[-3px] w-px bg-white/60"
                      style={{ left: pct(since.perUser[u.user_id].prevScaled) }}
                    />
                  </>
                )}
                <div
                  className={since.active ? 'absolute inset-y-0 left-0 rounded-full' : 'balken-wachsen absolute inset-y-0 left-0 rounded-full'}
                  style={{
                    width: since.active
                      ? grown
                        ? pct(u.total_scaled_km)
                        : pct(since.perUser[u.user_id]?.prevScaled ?? u.total_scaled_km)
                      : pct(u.total_scaled_km),
                    transition: since.active ? 'width 1.3s cubic-bezier(.2,.8,.2,1)' : undefined,
                    background: `linear-gradient(90deg, transparent, ${farbe})`,
                    boxShadow: fuehrt ? `0 0 14px ${farbe}` : `0 0 6px ${farbe}55`,
                  }}
                />
                {since.active && since.perUser[u.user_id]?.delta > 0 && (
                  <span
                    className="absolute top-1/2 -translate-x-full -translate-y-1/2 pr-1 text-[10px] font-black text-white [text-shadow:0_1px_2px_rgba(0,0,0,.6)]"
                    style={{ left: pct(u.total_scaled_km) }}
                  >
                    +{Math.round(since.perUser[u.user_id].delta)}
                  </span>
                )}
              </div>
              <p className="w-24 shrink-0 text-right text-lg font-black tabular-nums text-ink">
                {Math.round(toDisplay(u.total_scaled_km, u.total_real_km, mode))}{' '}
                <span className="text-xs font-normal text-ink-mute">{unitLabel(mode)}</span>
              </p>
            </div>
          )
        })}
      </div>
      {detail && (
        <PersonDetail user={detail} year={data.year} onClose={() => setDetail(null)} />
      )}
    </Card>
  )
}
