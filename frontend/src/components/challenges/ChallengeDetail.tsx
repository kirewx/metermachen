import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Challenge, ChallengeStanding } from '../../api/client'
import Avatar from '../ui/Avatar'
import { einheit, fortschritt, wertungText } from './wertung'

function Chip({ ch, s }: { ch: Challenge; s: ChallengeStanding }) {
  // Das Theme hat keine Erfolgsfarbe (nur accent/danger/line) — "geschafft"
  // wird deshalb ueber die gefuellte Akzentflaeche markiert, nicht ueber Gruen.
  if (ch.mode === 'rangliste')
    return (
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
          s.geschafft
            ? 'bg-accent text-accent-ink'
            : 'border border-line text-ink-mute'
        }`}
      >
        Platz {s.rank}
      </span>
    )
  if (s.geschafft)
    return (
      <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold text-accent-ink">
        geschafft
      </span>
    )
  if (s.nicht_mehr_schaffbar)
    return (
      <span className="shrink-0 rounded-full border border-danger px-2 py-0.5 text-[10px] font-bold text-danger">
        nicht mehr
      </span>
    )
  const rest = Math.max((ch.target ?? 0) - s.value, 0)
  return (
    <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
      noch {Math.round(rest * 100) / 100}
    </span>
  )
}

export default function ChallengeDetail() {
  const { id } = useParams()
  const challengeId = Number(id)
  const queryClient = useQueryClient()
  const { data: ch, error } = useQuery({
    queryKey: ['challenge', challengeId],
    queryFn: () => api.challenge(challengeId),
  })
  const { data: kategorien = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: api.categories,
  })
  const austreten = useMutation({
    mutationFn: () => api.leaveChallenge(challengeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenge', challengeId] })
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
  })

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (!ch) return <p className="p-8 text-sm text-ink-mute">Lädt…</p>

  const hoechster = Math.max(...ch.standings.map((s) => s.value), 1)
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <header className="rounded-2xl border border-line bg-card p-4">
        <h1 className="text-lg font-extrabold text-ink">{ch.title}</h1>
        <p className="mt-1 text-[11px] text-ink-mute">
          {new Date(ch.period_start).toLocaleDateString('de-DE')} –{' '}
          {new Date(ch.period_end).toLocaleDateString('de-DE')} ·{' '}
          {ch.join_mode === 'auto' ? 'alle automatisch dabei' : 'Beitritt nötig'}
        </p>
        <p className="mt-1 text-xs text-ink-soft">{wertungText(ch, kategorien)}</p>
        {ch.description && (
          <p className="mt-2 text-xs text-ink-soft">{ch.description}</p>
        )}
        {ch.prize && (
          <p className="mt-2 inline-block rounded-full bg-line px-2 py-0.5 text-[11px] font-semibold text-ink">
            🎁 {ch.prize}
          </p>
        )}
        {ch.vorlaeufig && (
          <p className="mt-2 rounded-xl border border-accent/40 bg-accent/10 px-3 py-1.5 text-[11px] text-ink">
            ⏱ Zeitraum vorbei — vorläufiges Ergebnis, Nachzügler zählen noch bis
            morgen früh.
          </p>
        )}
        {ch.bin_dabei && ch.join_mode === 'opt_in' && ch.status !== 'beendet' && (
          <button
            onClick={() => austreten.mutate()}
            disabled={austreten.isPending}
            className="mt-3 rounded-full border border-line px-3 py-1 text-[11px] font-bold text-ink-mute disabled:opacity-50"
          >
            Austreten
          </button>
        )}
      </header>

      <section className="space-y-1.5">
        {ch.standings.map((s) => (
          <div
            key={s.user_id}
            className={`rounded-xl border border-line bg-card p-2.5 ${
              s.nicht_mehr_schaffbar ? 'opacity-60' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              <Avatar value={s.avatar} size="sm" />
              <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
                {s.display_name}
              </span>
              <Chip ch={ch} s={s} />
              <span className="shrink-0 text-xs font-extrabold text-ink">
                {s.value} {einheit(ch.metric)}
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className={`h-full ${
                  s.nicht_mehr_schaffbar ? 'bg-ink-mute' : 'bg-accent'
                }`}
                style={{
                  width: `${
                    ch.mode === 'ziel'
                      ? fortschritt(ch, s.value) * 100
                      : (s.value / hoechster) * 100
                  }%`,
                }}
              />
            </div>
          </div>
        ))}
        {ch.standings.length === 0 && (
          <p className="p-6 text-center text-sm text-ink-mute">
            Noch niemand dabei.
          </p>
        )}
      </section>
    </div>
  )
}
