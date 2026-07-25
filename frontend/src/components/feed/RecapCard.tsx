import type { FeedEvent } from '../../api/client'
import { userColor } from '../comparison/userColor'

export default function RecapCard({ ev }: { ev: FeedEvent }) {
  const p = ev.payload
  const perUser = p.per_user ?? []
  const ids = perUser.map((e) => e.user_id)
  const max = Math.max(1, ...perUser.map((e) => e.mm))
  const art = ev.type === 'recap_week' ? 'Wochenrückblick' : 'Monatsrückblick'
  return (
    <div>
      <p className="text-sm font-bold text-ink">
        📊 {art} · {p.label}
      </p>
      <p className="mt-0.5 text-xs text-ink-mute">
        Gruppe gesamt: <b className="text-accent">{p.total_mm} MM</b>
      </p>
      <div className="mt-2 space-y-1.5">
        {perUser.map((e) => (
          <div key={e.user_id} className="flex items-center gap-2 text-xs">
            <span className="w-14 shrink-0 truncate text-ink-soft">{e.name}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full border border-line bg-surface">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(e.mm / max) * 100}%`,
                  background: `linear-gradient(90deg, transparent, ${userColor(e.user_id, ids)})`,
                }}
              />
            </div>
            <span className="w-14 shrink-0 text-right font-mono font-bold tabular-nums text-ink">
              {Math.round(e.mm)} MM
            </span>
          </div>
        ))}
      </div>
      {((p.ueberholungen?.length ?? 0) > 0 || (p.achievements?.length ?? 0) > 0) && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-mute">
          {(p.ueberholungen?.length ?? 0) > 0 && (
            <span>
              📈{' '}
              {p.ueberholungen!
                .map((u) => `${u.name} → Platz ${u.neuer_rang}`)
                .join(' · ')}
            </span>
          )}
          {(p.achievements?.length ?? 0) > 0 && (
            <span>
              🏆{' '}
              {p.achievements!
                .map((a) => (a.emoji ? `${a.emoji} ${a.title ?? a.label ?? ''}` : (a.title ?? a.label ?? '')))
                .join(' · ')}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
