import type { Achievement } from '../../api/client'
import Icon from '../ui/Icon'
import { TIER_LABEL } from './constants'

// One card per discipline with its bronze/silver/gold pills and progress to the next tier.
export default function TierCard({ tiers }: { tiers: Achievement[] }) {
  const label = tiers[0]?.parts[0]?.label ?? ''
  const next = tiers.find((s) => !s.achieved)
  return (
    <div
      className={`rounded-xl border p-3 ${
        tiers.some((s) => s.achieved) ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon name={tiers[0].icon} size={20} className="text-accent" />
        <span className="text-sm font-bold text-ink">{label}</span>
      </div>
      <div className="mt-2 flex gap-1.5">
        {tiers.map((s) => (
          <span
            key={s.key}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
              s.achieved
                ? s.tier === 'gold'
                  ? 'border-amber-400 text-amber-400'
                  : s.tier === 'silber'
                    ? 'border-slate-300 text-slate-300'
                    : 'border-amber-700 text-amber-700'
                : 'border-line/40 text-ink-mute'
            }`}
          >
            {TIER_LABEL[s.tier as keyof typeof TIER_LABEL]}
          </span>
        ))}
      </div>
      {next && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(next.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] tabular-nums text-ink-mute">
            {Math.round(next.parts[0]?.current_km ?? 0)}/
            {Math.round(next.parts[0]?.target_km ?? 0)} km bis{' '}
            {TIER_LABEL[next.tier as keyof typeof TIER_LABEL]}
          </p>
        </>
      )}
    </div>
  )
}
