import type { Challenge } from '../../api/client'

export default function ChallengeInvite({
  ch,
  onJoin,
  busy,
}: {
  ch: Challenge
  onJoin: () => void
  busy: boolean
}) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-dashed border-accent bg-card p-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-bold text-ink">{ch.title}</p>
        <p className="mt-0.5 text-[11px] text-ink-mute">
          {ch.prize ? `🎁 ${ch.prize} · ` : ''}
          {ch.status === 'geplant'
            ? `ab ${new Date(ch.period_start).toLocaleDateString('de-DE')}`
            : `bis ${new Date(ch.period_end).toLocaleDateString('de-DE')}`}
          {ch.team_mode && ' · in Gruppen'}
        </p>
      </div>
      <button
        onClick={onJoin}
        disabled={busy}
        className="shrink-0 rounded-full border border-accent px-3 py-1 text-[11px] font-bold text-accent disabled:opacity-50"
      >
        Beitreten
      </button>
    </div>
  )
}
