import { useLayoutEffect, useRef, useState } from 'react'
import type { Comparison } from '../../api/client'
import { progressFraction, spreadBadges } from './pathMath'

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

  return (
    <div className="space-y-3">
    <svg viewBox="0 0 960 520" className="w-full rounded-2xl shadow">
      {data.map_image ? (
        <image href={data.map_image} width="960" height="520" preserveAspectRatio="xMidYMid slice" />
      ) : (
        <Landschaft />
      )}
      <path d={TRAIL} fill="none" stroke="#f7ecd4" strokeWidth="16" strokeLinecap="round" />
      <path
        ref={pathRef}
        d={TRAIL}
        fill="none"
        stroke="#cdab72"
        strokeWidth="3"
        strokeDasharray="10,9"
        strokeLinecap="round"
      />
      {data.milestones.map((m, i) => {
        const p = milestonePoints[i]
        if (!p) return null
        return (
          <g key={m.km}>
            <circle cx={p.x} cy={p.y} r="14" fill="#fff" stroke="#cdab72" strokeWidth="3" />
            <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="14">{m.emoji}</text>
            <text x={p.x} y={p.y + 32} textAnchor="middle" fontSize="11" fill="#666">
              {m.label} · {m.km} km
            </text>
          </g>
        )
      })}
      <g>
        <circle cx="920" cy="150" r="16" fill="#ffe9a8" stroke="#e0b84e" strokeWidth="3" />
        <text x="920" y="156" textAnchor="middle" fontSize="15">🏁</text>
        <text x="920" y="124" textAnchor="middle" fontSize="11" fill="#666">{data.goal_km} km</text>
      </g>
      {[...data.users].reverse().map((u) => {
        const p = points.get(u.user_id)
        if (!p) return null
        const lane = badgeLanes.get(u.user_id) ?? 0
        const badgeY = p.y - 28 - lane * 24
        return (
          <g
            key={u.user_id}
            className="cursor-pointer"
            onClick={() => setSelected(u.user_id === selected ? null : u.user_id)}
          >
            <circle cx={p.x} cy={p.y} r="15" fill="#fff" stroke="#888" strokeWidth="2" />
            <text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="15">{u.avatar_emoji}</text>
            <rect x={p.x - 52} y={badgeY - 13} width="104" height="18" rx="9" fill="#ffffffdd" />
            <text x={p.x} y={badgeY} textAnchor="middle" fontSize="11" fontWeight="600">
              {u.rank === 1 ? '👑 ' : ''}{u.display_name} · {Math.round(u.total_scaled_km)}
            </text>
          </g>
        )
      })}
    </svg>
      {selectedUser && (
        <div className="rounded-xl bg-white p-3 shadow">
          <p className="font-semibold">
            {selectedUser.avatar_emoji} {selectedUser.display_name} —{' '}
            {Math.round(selectedUser.total_scaled_km)} von {data.goal_km} km
          </p>
          <ul className="mt-1 flex flex-wrap gap-3 text-sm">
            {selectedUser.by_category.map((b) => (
              <li key={b.category_id} className="flex items-center gap-1">
                <span className="inline-block h-3 w-3 rounded-full" style={{ background: b.color }} />
                {b.icon_emoji} {b.name}: {Math.round(b.scaled_km)} km
              </li>
            ))}
          </ul>
        </div>
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
