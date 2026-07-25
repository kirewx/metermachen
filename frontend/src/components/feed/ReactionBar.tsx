import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { FeedEvent } from '../../api/client'

export const REACTION_EMOJIS = ['👏', '🔥', '💪', '😂', '😮'] as const

export default function ReactionBar({ ev }: { ev: FeedEvent }) {
  const queryClient = useQueryClient()
  const [auswahlOffen, setAuswahlOffen] = useState(false)
  const [namenFuer, setNamenFuer] = useState<string | null>(null)
  const toggle = useMutation({
    mutationFn: (emoji: string) => api.toggleFeedReaction(ev.id, emoji),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['feed'] }),
  })
  return (
    <div className="relative mt-2 flex flex-wrap items-center gap-1.5">
      {ev.reactions.map((r) => (
        <button
          key={r.emoji}
          onClick={() => toggle.mutate(r.emoji)}
          onMouseEnter={() => setNamenFuer(r.emoji)}
          onMouseLeave={() => setNamenFuer(null)}
          className={`rounded-full border px-2 py-0.5 text-xs transition ${
            r.mine
              ? 'border-accent bg-accent/10 text-ink'
              : 'border-line bg-surface text-ink-soft hover:text-ink'
          }`}
        >
          {r.emoji} {r.count}
          {namenFuer === r.emoji && r.users.length > 0 && (
            <span className="absolute bottom-full left-0 z-40 mb-1 rounded-lg border border-line bg-card px-2 py-1 text-[11px] text-ink-mute shadow-lg">
              {r.users.join(', ')}
            </span>
          )}
        </button>
      ))}
      <button
        aria-label="Reagieren"
        onClick={() => setAuswahlOffen((o) => !o)}
        className="rounded-full border border-dashed border-line px-2 py-0.5 text-xs text-ink-mute transition hover:border-line hover:text-ink"
      >
        ＋
      </button>
      {auswahlOffen && (
        <span className="flex gap-1.5 rounded-full border border-line bg-card px-2.5 py-1 shadow-lg">
          {REACTION_EMOJIS.map((e) => (
            <button
              key={e}
              onClick={() => {
                toggle.mutate(e)
                setAuswahlOffen(false)
              }}
              className="text-sm transition hover:scale-125"
            >
              {e}
            </button>
          ))}
        </span>
      )}
    </div>
  )
}
