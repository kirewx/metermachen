import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Challenge, SiegerWahl } from '../../api/client'
import Avatar from '../ui/Avatar'
import Select from '../ui/Select'
import GroupCard from './GroupCard'
import WertungsChip from './WertungsChip'
import { einheit, fortschritt, siegerText, wertungText } from './wertung'

function GroupSection({ ch }: { ch: Challenge }) {
  const editorLink = ch.kann_gruppen_bearbeiten && (
    <Link
      to={`/arena/challenges/${ch.id}/gruppen`}
      className="inline-block rounded-full border border-accent px-3 py-1 text-[11px] font-bold text-accent"
    >
      Gruppen bearbeiten
    </Link>
  )
  if (!ch.groups_drawn)
    return (
      <section className="space-y-2 rounded-2xl border border-dashed border-line p-4 text-center">
        <p className="text-sm text-ink-mute">Gruppen werden noch ausgelost</p>
        {editorLink}
      </section>
    )
  const meine = ch.meine_gruppe_id
  const sortiert = [...ch.groups].sort((a, b) => {
    if (a.id === meine) return -1
    if (b.id === meine) return 1
    return a.rank - b.rank || a.id - b.id
  })
  const hoechster = Math.max(...ch.groups.map((g) => g.value), 1)
  return (
    <section className="space-y-2">
      {editorLink && <div className="text-right">{editorLink}</div>}
      {sortiert.map((g) => (
        <GroupCard key={g.id} ch={ch} g={g} mine={g.id === meine} hoechster={hoechster} />
      ))}
      {ch.groups.length === 0 && (
        <p className="p-6 text-center text-sm text-ink-mute">Noch keine Gruppen.</p>
      )}
    </section>
  )
}

/** Select options: qualified groups first, then their members; plain people otherwise. */
function siegerOptionen(ch: Challenge): { value: string; label: string }[] {
  if (!ch.team_mode) {
    return ch.standings
      .filter((s) => ch.gewinner_ids.includes(s.user_id))
      .map((s) => ({ value: `u:${s.user_id}`, label: s.display_name }))
  }
  const gruppen = ch.groups.filter((g) => g.geschafft)
  return [
    ...gruppen.map((g) => ({ value: `g:${g.id}`, label: g.name })),
    ...gruppen.flatMap((g) =>
      g.members.map((m) => ({ value: `u:${m.user_id}`, label: `${m.display_name} (${g.name})` })),
    ),
  ]
}

function parseWahl(wahl: string): SiegerWahl {
  const [art, id] = wahl.split(':')
  return art === 'g' ? { group_id: Number(id) } : { user_id: Number(id) }
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
  const [wahl, setWahl] = useState<string>('')
  const siegerSetzen = useMutation({
    mutationFn: (sieger: SiegerWahl) => api.setChallengeSieger(challengeId, sieger),
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
      <Link to="/arena/challenges" className="text-xs font-bold text-accent hover:underline">
        ← Arena
      </Link>
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
        {ch.bin_dabei &&
          ch.join_mode === 'opt_in' &&
          ch.status !== 'beendet' &&
          (!ch.team_mode || ch.status === 'geplant') && (
            <button
              onClick={() => austreten.mutate()}
              disabled={austreten.isPending}
              className="mt-3 rounded-full border border-line px-3 py-1 text-[11px] font-bold text-ink-mute disabled:opacity-50"
            >
              Austreten
            </button>
          )}
      </header>

      {ch.status === 'beendet' && ch.mode === 'ziel' && (
        <section className="rounded-2xl border border-accent bg-card p-3">
          {siegerText(ch) !== null ? (
            <p className="text-sm font-bold text-ink">
              🏆 Sieger: {siegerText(ch)}
              {ch.prize && (
                <span className="font-normal text-ink-mute"> — {ch.prize}</span>
              )}
            </p>
          ) : ch.kann_sieger_setzen ? (
            <div className="flex items-end gap-2">
              <Select
                label="Sieger"
                className="flex-1"
                value={wahl}
                onChange={(e) => setWahl(e.target.value)}
              >
                <option value="">– bitte wählen –</option>
                {siegerOptionen(ch).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </Select>
              <button
                onClick={() => wahl && siegerSetzen.mutate(parseWahl(wahl))}
                disabled={!wahl || siegerSetzen.isPending}
                className="shrink-0 rounded-xl border border-accent px-3 py-2 text-xs font-bold text-accent disabled:opacity-50"
              >
                Sieger eintragen
              </button>
            </div>
          ) : (
            <p className="text-sm text-ink-mute">
              {ch.gewinner_ids.length > 0
                ? 'Sieger wird noch ausgelost.'
                : 'Niemand hat das Ziel erreicht.'}
            </p>
          )}
        </section>
      )}

      {ch.team_mode ? (
        <GroupSection ch={ch} />
      ) : (
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
                  {s.user_id === ch.sieger_id && ' 🏆'}
                </span>
                <WertungsChip
                  ch={ch}
                  rank={s.rank}
                  geschafft={s.geschafft}
                  value={s.value}
                  nichtMehr={s.nicht_mehr_schaffbar}
                />
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
      )}
    </div>
  )
}
