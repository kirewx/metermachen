import type { Achievement } from '../../api/client'
import Icon from '../ui/Icon'

// Classic km goal (Startschuss, Marathon, Ironman, ...): icon, title, progress per part.
export default function AchievementBadge({ a }: { a: Achievement }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        a.achieved ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon
          name={a.icon}
          size={20}
          className={a.achieved ? 'text-accent' : 'text-ink-mute'}
        />
        <span className={`text-sm font-bold ${a.achieved ? 'text-accent' : 'text-ink'}`}>
          {a.title}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {!a.achieved && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(a.progress * 100)}%` }}
            />
          </div>
          {a.parts.some((p) => p.target_km >= 1) && (
            <p className="mt-1 space-x-2 font-mono text-[10px] tabular-nums text-ink-mute">
              {a.parts
                .filter((p) => p.target_km >= 1)
                .map((p) => (
                  <span key={p.label}>
                    {p.label}: {Math.round(p.current_km)}/{Math.round(p.target_km)} km
                  </span>
                ))}
            </p>
          )}
        </>
      )}
    </div>
  )
}
