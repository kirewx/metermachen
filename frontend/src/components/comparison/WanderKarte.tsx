import { useLayoutEffect, useRef, useState } from 'react'
import type { Comparison } from '../../api/client'
import Card from '../ui/Card'
import { progressFraction, spreadBadges } from './pathMath'
import { userColor } from './userColor'

const TRAIL = 'M 40,460 C 120,330 220,300 320,320 S 520,400 640,360 S 820,180 920,150'

type Point = { x: number; y: number }

export default function WanderKarte({ data }: { data: Comparison }) {
  const pathRef = useRef<SVGPathElement>(null)
  const [points, setPoints] = useState<Map<number, Point>>(new Map())
  const [milestonePoints, setMilestonePoints] = useState<Point[]>([])
  const [selected, setSelected] = useState<number | null>(null)

  useLayoutEffect(() => {
    const path = pathRef.current
    if (!path) return
    const len = path.getTotalLength()
    const at = (fraction: number) => {
      const p = path.getPointAtLength(fraction * len)
      return { x: p.x, y: p.y }
    }
    setPoints(
      new Map(
        data.users.map((u) => [
          u.user_id,
          at(progressFraction(u.total_scaled_km, data.goal_km)),
        ]),
      ),
    )
    setMilestonePoints(data.milestones.map((m) => at(progressFraction(m.km, data.goal_km))))
  }, [data])

  const badgeLanes = spreadBadges(
    data.users.map((u) => ({ id: u.user_id, x: points.get(u.user_id)?.x ?? 0 })),
    120,
  )

  const selectedUser = data.users.find((u) => u.user_id === selected)
  const ids = data.users.map((u) => u.user_id)
  const besteKm = Math.max(0, ...data.users.map((u) => u.total_scaled_km))

  return (
    <div className="space-y-3">
      <Card className="p-2">
        <svg viewBox="0 0 960 520" className="w-full rounded-xl">
          <defs>
            <radialGradient id="vignette" cx="50%" cy="50%" r="72%">
              <stop offset="55%" stopColor="#050508" stopOpacity="0" />
              <stop offset="100%" stopColor="#050508" stopOpacity="0.55" />
            </radialGradient>
            <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {data.map_image ? (
            <image
              href={data.map_image}
              width="960"
              height="520"
              preserveAspectRatio="xMidYMid slice"
            />
          ) : (
            <Landschaft />
          )}
          <rect width="960" height="520" fill="url(#vignette)" />
          <path
            d={TRAIL}
            fill="none"
            stroke="#050508"
            strokeOpacity="0.45"
            strokeWidth="14"
            strokeLinecap="round"
          />
          <path
            ref={pathRef}
            d={TRAIL}
            fill="none"
            stroke="var(--t-accent)"
            strokeWidth="3.5"
            strokeDasharray="10,9"
            strokeLinecap="round"
            filter="url(#neon-glow)"
          />
          {data.milestones.map((m, i) => {
            const p = milestonePoints[i]
            if (!p) return null
            const erreicht = besteKm >= m.km
            return (
              <g key={m.km} color={erreicht ? 'var(--t-accent)' : 'var(--t-ink-mute)'}>
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="14"
                  fill="var(--t-card)"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  filter={erreicht ? 'url(#neon-glow)' : undefined}
                />
                <use href={`/icons.svg#${m.icon}`} x={p.x - 8} y={p.y - 8} width="16" height="16" />
                <text x={p.x} y={p.y + 32} textAnchor="middle" fontSize="11" fill="var(--t-ink-soft)">
                  {m.label} · {m.km} km
                </text>
              </g>
            )
          })}
          <g color="var(--t-accent)">
            <circle
              cx="920"
              cy="150"
              r="16"
              fill="var(--t-card)"
              stroke="currentColor"
              strokeWidth="3"
              filter="url(#neon-glow)"
            />
            <use href="/icons.svg#fahne" x={911} y={141} width="18" height="18" />
            <text x="920" y="122" textAnchor="middle" fontSize="11" fill="var(--t-ink-soft)">
              {data.goal_km} km
            </text>
          </g>
          {[...data.users].reverse().map((u) => {
            const p = points.get(u.user_id)
            if (!p) return null
            const lane = badgeLanes.get(u.user_id) ?? 0
            const badgeY = p.y - 30 - lane * 24
            const farbe = userColor(u.user_id, ids)
            return (
              <g
                key={u.user_id}
                className="cursor-pointer"
                onClick={() => setSelected(u.user_id === selected ? null : u.user_id)}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r="15"
                  fill="var(--t-card)"
                  stroke={farbe}
                  strokeWidth="2.5"
                  filter={u.rank === 1 ? 'url(#neon-glow)' : undefined}
                />
                {u.avatar.startsWith('icon:') ? (
                  <use
                    href={`/icons.svg#${u.avatar.slice(5)}`}
                    x={p.x - 8}
                    y={p.y - 8}
                    width="16"
                    height="16"
                    color={farbe}
                  />
                ) : (
                  <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="14">
                    {u.avatar}
                  </text>
                )}
                <rect
                  x={p.x - 56}
                  y={badgeY - 13}
                  width="112"
                  height="19"
                  rx="9.5"
                  fill="#050508"
                  fillOpacity="0.85"
                  stroke={farbe}
                  strokeOpacity="0.6"
                />
                <text
                  x={p.x}
                  y={badgeY}
                  textAnchor="middle"
                  fontSize="11"
                  fontWeight="700"
                  fill="#f2fbfd"
                >
                  P{u.rank} {u.display_name} · {Math.round(u.total_scaled_km)}
                </text>
              </g>
            )
          })}
        </svg>
      </Card>
      {selectedUser && (
        <Card className="p-3">
          <p className="text-sm font-bold text-ink">
            {selectedUser.display_name} —{' '}
            <span className="text-accent">{Math.round(selectedUser.total_scaled_km)}</span> von{' '}
            {data.goal_km} km
          </p>
          <ul className="mt-1 flex flex-wrap gap-3 text-sm text-ink-soft">
            {selectedUser.by_category.map((b) => (
              <li key={b.category_id} className="flex items-center gap-1">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ background: b.color }}
                />
                {b.name}: {Math.round(b.scaled_km)} km
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

function Landschaft() {
  return (
    <g>
      <rect width="960" height="520" fill="#e7f0d8" />
      <ellipse cx="220" cy="120" rx="190" ry="80" fill="#7db86a" />
      <circle cx="160" cy="100" r="22" fill="#4e8c3f" />
      <circle cx="220" cy="125" r="26" fill="#5da04c" />
      <circle cx="280" cy="95" r="20" fill="#4e8c3f" />
      <polygon points="680,170 770,40 860,170" fill="#a8a29a" />
      <polygon points="745,75 770,40 795,75 770,88" fill="#f4f4f2" />
      <polygon points="770,170 840,80 910,170" fill="#bdb8b0" />
      <path d="M 0,400 Q 240,360 480,410 T 960,390 L 960,520 L 0,520 Z" fill="#79b9dd" />
      <path
        d="M 90,440 q 20,-9 40,0 M 300,465 q 20,-9 40,0 M 540,445 q 20,-9 40,0"
        stroke="#fff" strokeWidth="3" fill="none" opacity="0.7" strokeLinecap="round"
      />
    </g>
  )
}
