import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import type { Challenge, ChallengeGroup } from '../../api/client'
import { useToast } from '../ui/Toast'
import { TEAM_FARBEN, teamFarbe } from './teamFarben'

type Props = { ch: Challenge; g: ChallengeGroup; onClose: () => void }

// Name and colour of one group. Members stay untouched, so this also works
// while the challenge is running (unlike the group editor).
export default function TeamEinstellungen({ ch, g, onClose }: Props) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState(g.name)
  const [farbe, setFarbe] = useState(teamFarbe(g))
  // Taken colours are only blocked while a free one is left: with as many groups
  // as colours nothing could change any more, so colours may repeat then.
  const vergeben = new Set(
    ch.groups.length < TEAM_FARBEN.length
      ? ch.groups.filter((o) => o.id !== g.id).map(teamFarbe)
      : [],
  )
  const speichern = useMutation({
    mutationFn: () => api.updateChallengeGroup(ch.id, g.id, { name: name.trim(), color: farbe }),
    onSuccess: (neu) => {
      queryClient.setQueryData(['challenge', ch.id], neu)
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
      onClose()
    },
    onError: (e: Error) => toast(e.message),
  })
  return (
    <form
      className="mt-2 space-y-2 rounded-xl border border-line p-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (name.trim()) speichern.mutate()
      }}
    >
      <label className="block text-[10px] font-bold uppercase tracking-wider text-ink-mute">
        Teamname
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1 block w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-sm font-semibold normal-case tracking-normal text-ink"
        />
      </label>
      <div
        role="radiogroup"
        aria-label={`Farbe ${g.name}`}
        className="flex flex-wrap gap-2"
      >
        {TEAM_FARBEN.map((f) => {
          const belegt = vergeben.has(f.hex)
          return (
            <button
              key={f.hex}
              type="button"
              role="radio"
              aria-checked={farbe === f.hex}
              aria-label={belegt ? `${f.name} (schon vergeben)` : f.name}
              disabled={belegt}
              onClick={() => setFarbe(f.hex)}
              className={`h-8 w-8 rounded-full border-2 transition disabled:cursor-not-allowed disabled:opacity-25 ${
                farbe === f.hex ? 'border-ink' : 'border-transparent'
              }`}
              style={{ background: f.hex, boxShadow: 'inset 0 0 0 2px var(--t-card)' }}
            />
          )
        })}
      </div>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="px-2 py-1 text-xs text-ink-mute hover:text-ink">
          Abbrechen
        </button>
        <button
          type="submit"
          disabled={!name.trim() || speichern.isPending}
          className="rounded-full bg-accent px-3 py-1 text-xs font-bold text-accent-ink disabled:opacity-40"
        >
          Speichern
        </button>
      </div>
    </form>
  )
}
