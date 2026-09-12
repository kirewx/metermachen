import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import type { Challenge, ChallengeGroupInput, SeedingEntry } from '../../api/client'
import Avatar from '../ui/Avatar'
import Button from '../ui/Button'
import Input from '../ui/Input'
import { useToast } from '../ui/Toast'
import { einheit } from './wertung'

type Person = SeedingEntry

function toInputs(ch: Challenge): ChallengeGroupInput[] {
  return ch.groups.map((g) => ({
    id: g.id,
    name: g.name,
    member_ids: g.members.map((m) => m.user_id),
  }))
}

function sameGroups(a: ChallengeGroupInput[], b: ChallengeGroupInput[]): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

// Per person: a small select instead of drag and drop, which is unreliable on
// phones. Value "g:<id>" moves into that group, "remove" takes the person out.
function MoveSelect({
  person, current, groups, onMove,
}: {
  person: Person
  current: number | null
  groups: ChallengeGroupInput[]
  onMove: (target: number | null) => void
}) {
  return (
    <select
      aria-label={`${person.display_name} verschieben`}
      value=""
      onChange={(e) => {
        const v = e.target.value
        if (v === 'remove') onMove(null)
        else if (v.startsWith('g:')) onMove(Number(v.slice(2)))
      }}
      className="rounded-lg border border-line bg-surface px-1.5 py-1 text-[11px] text-ink"
    >
      <option value="">{current === null ? '→ Gruppe…' : 'Verschieben nach…'}</option>
      {groups
        .filter((g) => g.id !== current)
        .map((g) => (
          <option key={g.id} value={`g:${g.id}`}>
            → {g.name}
          </option>
        ))}
      {current !== null && <option value="remove">Entfernen</option>}
    </select>
  )
}

function PersonRow({
  person, ch, current, groups, onMove,
}: {
  person: Person
  ch: Challenge
  current: number | null
  groups: ChallengeGroupInput[]
  onMove: (target: number | null) => void
}) {
  return (
    <li className="flex items-center gap-2 text-xs">
      <Avatar value={person.avatar} size="sm" />
      <span data-testid="person-name" className="min-w-0 flex-1 truncate text-ink">
        {person.display_name}
      </span>
      <span className="shrink-0 text-[10px] text-ink-mute">
        {Math.round(person.value * 10) / 10} {einheit(ch.metric)}
      </span>
      <MoveSelect person={person} current={current} groups={groups} onMove={onMove} />
    </li>
  )
}

export default function GroupEditor() {
  const { id } = useParams()
  const challengeId = Number(id)
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: ch, error } = useQuery({
    queryKey: ['challenge', challengeId],
    queryFn: () => api.challenge(challengeId),
  })
  const { data: seeding, error: seedingError } = useQuery({
    queryKey: ['challenge-seeding', challengeId],
    queryFn: () => api.challengeSeeding(challengeId),
    enabled: !!ch?.kann_gruppen_bearbeiten,
  })
  // Local edits live as an overlay over the server state: null means "nothing
  // touched yet", so fresh server data flows straight through and saving just
  // drops the overlay — no effect that mirrors props into state.
  const [edited, setEdited] = useState<ChallengeGroupInput[] | null>(null)
  const [confirmRedraw, setConfirmRedraw] = useState(false)
  const serverGroups = ch ? toInputs(ch) : []
  const groups = edited ?? serverGroups
  const dirty = !sameGroups(groups, serverGroups)
  // Derived, not stored: saving or undoing the edits answers the question by
  // itself, so a stale "yes" can never redraw over something worth keeping.
  const fragen = confirmRedraw && dirty

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['challenge', challengeId] })
    queryClient.invalidateQueries({ queryKey: ['challenges'] })
  }
  const uebernehmen = (neu: Challenge) => {
    setEdited(null)
    queryClient.setQueryData(['challenge', challengeId], neu)
    invalidate()
  }
  const speichern = useMutation({
    mutationFn: () => api.saveChallengeGroups(challengeId, groups),
    onSuccess: (neu) => {
      uebernehmen(neu)
      toast('Gruppen gespeichert', 'ok')
    },
    onError: (e: Error) => toast(e.message),
  })
  const auslosen = useMutation({
    mutationFn: () => api.drawChallengeGroups(challengeId),
    onSuccess: (neu) => {
      setConfirmRedraw(false)
      uebernehmen(neu)
      toast('Gruppen neu ausgelost', 'ok')
    },
    onError: (e: Error) => toast(e.message),
  })

  if (error)
    return (
      <div className="mx-auto max-w-xl space-y-3">
        <p className="text-sm text-danger">{error.message}</p>
        <Link to="/arena/challenges" className="text-xs font-bold text-accent hover:underline">
          ← Arena
        </Link>
      </div>
    )
  if (!ch) return <p className="p-8 text-sm text-ink-mute">Lädt…</p>
  if (!ch.kann_gruppen_bearbeiten)
    return (
      <div className="mx-auto max-w-xl space-y-3">
        <p className="text-sm text-ink-mute">Die Gruppen lassen sich hier nicht bearbeiten.</p>
        <Link to={`/arena/challenges/${ch.id}`} className="text-xs font-bold text-accent hover:underline">
          ← zur Challenge
        </Link>
      </div>
    )

  // Without the seeding list every row would first show a bare "#7" and jump
  // once the values land, so wait for it — unless it failed, then edit without.
  if (seeding === undefined && !seedingError)
    return <p className="p-8 text-sm text-ink-mute">Lädt…</p>

  // Seeding gone: fall back to everyone the challenge itself reports, placed
  // members included, so the groups stay editable and stay readable — only the
  // values are missing, not the people.
  const setzliste: Person[] =
    seeding ??
    [...ch.groups.flatMap((g) => g.members), ...ch.unassigned].map((p) => ({
      user_id: p.user_id,
      display_name: p.display_name,
      avatar: p.avatar,
      value: 0,
    }))
  const personen = new Map<number, Person>(setzliste.map((p) => [p.user_id, p]))
  // People the seeding list does not cover (no longer active, for instance).
  const personOf = (userId: number): Person =>
    personen.get(userId) ?? {
      user_id: userId,
      display_name: ch.standings.find((s) => s.user_id === userId)?.display_name ?? `#${userId}`,
      avatar: 'icon:laufen',
      value: 0,
    }
  const zugeordnet = new Set(groups.flatMap((g) => g.member_ids))
  const poolIds = new Set(ch.unassigned.map((u) => u.user_id))
  const frei = setzliste
    .filter((p) => !zugeordnet.has(p.user_id))
    .sort((a, b) => Number(poolIds.has(b.user_id)) - Number(poolIds.has(a.user_id)) || b.value - a.value)
  const sizes = groups.map((g) => g.member_ids.length)
  const ungleich = sizes.length > 0 && Math.max(...sizes) - Math.min(...sizes) > 1
  // The backend rejects an empty group, so do not even offer to send one.
  const leereGruppe = sizes.some((s) => s === 0)

  const bearbeiten = (f: (gs: ChallengeGroupInput[]) => ChallengeGroupInput[]) => {
    setConfirmRedraw(false)
    setEdited((cur) => f(cur ?? serverGroups))
  }
  const move = (userId: number, target: number | null) =>
    bearbeiten((gs) =>
      gs.map((g) => ({
        ...g,
        member_ids: [
          ...g.member_ids.filter((uid) => uid !== userId),
          ...(g.id === target ? [userId] : []),
        ],
      })),
    )
  const rename = (gid: number, name: string) =>
    bearbeiten((gs) => gs.map((g) => (g.id === gid ? { ...g, name } : g)))
  const redraw = () => {
    if (dirty && !fragen) {
      setConfirmRedraw(true)
      return
    }
    auslosen.mutate()
  }

  return (
    <div className="mx-auto max-w-xl space-y-4">
      <Link to={`/arena/challenges/${ch.id}`} className="text-xs font-bold text-accent hover:underline">
        ← {ch.title}
      </Link>
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="flex-1 text-lg font-extrabold text-ink">Gruppen</h1>
        {dirty && (
          <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-bold text-ink-mute">
            ungespeichert
          </span>
        )}
        <Button variant="ghost" onClick={redraw} disabled={auslosen.isPending}>
          {fragen ? 'Wirklich neu auslosen?' : 'Neu auslosen'}
        </Button>
        <Button
          onClick={() => speichern.mutate()}
          disabled={!dirty || leereGruppe || speichern.isPending}
        >
          Speichern
        </Button>
      </header>
      {seedingError && (
        <p className="rounded-xl border border-danger px-3 py-1.5 text-[11px] text-danger">
          Setzliste konnte nicht geladen werden: {seedingError.message}
        </p>
      )}
      {ungleich && (
        <p className="rounded-xl border border-accent/40 bg-accent/10 px-3 py-1.5 text-[11px] text-ink">
          Die Gruppen sind ungleich groß (Unterschied mehr als eine Person).
        </p>
      )}

      {groups.map((g) => {
        const summe = g.member_ids.reduce((s, uid) => s + personOf(uid).value, 0)
        const proKopf = g.member_ids.length ? Math.round((summe / g.member_ids.length) * 10) / 10 : 0
        return (
          <section
            key={g.id}
            data-testid={`editor-group-${g.id}`}
            aria-label={`Gruppe ${g.name}`}
            className="rounded-2xl border border-line bg-card p-3"
          >
            <div className="flex items-end gap-2">
              <Input
                label="Name"
                className="flex-1"
                value={g.name}
                onChange={(e) => rename(g.id, e.target.value)}
              />
              <span className="pb-2 text-[11px] text-ink-mute">
                {g.member_ids.length} Pers. · {Math.round(summe)} {einheit(ch.metric)} · {proKopf} pro Kopf
              </span>
            </div>
            <ul className="mt-2 space-y-1">
              {g.member_ids.map((uid) => (
                <PersonRow
                  key={uid}
                  person={personOf(uid)}
                  ch={ch}
                  current={g.id}
                  groups={groups}
                  onMove={(t) => move(uid, t)}
                />
              ))}
              {g.member_ids.length === 0 && (
                <li className="text-xs text-danger">Leer — eine Gruppe braucht mindestens eine Person.</li>
              )}
            </ul>
          </section>
        )
      })}

      <section data-testid="editor-unassigned" className="rounded-2xl border border-dashed border-line p-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-ink-mute">Nicht zugeordnet</h2>
        <ul className="mt-2 space-y-1">
          {frei.map((p) => (
            <PersonRow
              key={p.user_id}
              person={p}
              ch={ch}
              current={null}
              groups={groups}
              onMove={(t) => move(p.user_id, t)}
            />
          ))}
          {frei.length === 0 && <li className="text-xs text-ink-mute">Alle sind zugeordnet.</li>}
        </ul>
      </section>
      <p className="text-[11px] text-ink-mute">
        Setzliste: {einheit(ch.metric)} der letzten {ch.seeding_days} Tage.
      </p>
    </div>
  )
}
