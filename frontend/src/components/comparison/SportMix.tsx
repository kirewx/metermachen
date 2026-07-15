import { useState } from 'react'
import type { Comparison, ComparisonUser } from '../../api/client'
import Avatar from '../ui/Avatar'
import PersonDetail from './PersonDetail'
import { type UnitMode } from './unit'

export default function SportMix({ data }: { data: Comparison; mode?: UnitMode }) {
  const [detail, setDetail] = useState<ComparisonUser | null>(null)
  // Alle vorkommenden Kategorien für die Legende sammeln (Reihenfolge stabil).
  const legende = new Map<number, { name: string; color: string }>()
  for (const u of data.users)
    for (const c of u.by_category) legende.set(c.category_id, { name: c.name, color: c.color })

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        {data.users.map((u, i) => {
          const gesamt = u.by_category.reduce((s, c) => s + c.scaled_km, 0)
          return (
            <div
              key={u.user_id}
              className="reihe-rein flex items-center gap-3"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <button
                type="button"
                onClick={() => setDetail(u)}
                aria-label={`Details zu ${u.display_name}`}
                className="flex shrink-0 items-center gap-3 rounded-lg text-left transition hover:opacity-80"
              >
                <span className="w-7 font-mono text-sm font-bold tabular-nums text-ink-tech">
                  P{u.rank}
                </span>
                <Avatar value={u.avatar} size="sm" />
                <span className="w-24 truncate text-sm font-bold text-ink">{u.display_name}</span>
              </button>
              <div className="flex h-4 flex-1 overflow-hidden rounded-full bg-surface">
                {u.by_category.map((c) => (
                  <span
                    key={c.category_id}
                    title={`${c.name}: ${Math.round(c.scaled_km)} km`}
                    className="balken-wachsen h-full"
                    style={{
                      width: gesamt > 0 ? `${(c.scaled_km / gesamt) * 100}%` : '0%',
                      background: c.color,
                    }}
                  />
                ))}
              </div>
              <span className="w-24 text-right font-mono text-sm font-bold tabular-nums text-ink">
                {Math.round(gesamt)}
              </span>
            </div>
          )
        })}
      </div>
      <ul className="flex flex-wrap gap-3 text-xs text-ink-soft">
        {[...legende.entries()].map(([id, c]) => (
          <li key={id} className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: c.color }} />
            {c.name}
          </li>
        ))}
      </ul>
      {detail && (
        <PersonDetail user={detail} year={data.year} onClose={() => setDetail(null)} />
      )}
    </div>
  )
}
