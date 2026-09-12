import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { Challenge, ChallengeInput } from '../../api/client'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Input from '../ui/Input'
import Select from '../ui/Select'
import { useToast } from '../ui/Toast'

const LEER: ChallengeInput = {
  title: '',
  description: '',
  prize: '',
  mode: 'ziel',
  target: 300,
  top_n: 1,
  metric: 'mm',
  category_ids: [],
  streak_min_mm: 5,
  join_mode: 'auto',
  period_start: '',
  period_end: '',
  team_mode: false,
  group_count: 3,
  seeding_days: 30,
}

export default function ChallengesAdmin() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [form, setForm] = useState<ChallengeInput>(LEER)
  const { data: alle = [] } = useQuery({
    queryKey: ['challenges'],
    queryFn: api.challenges,
  })
  const { data: kategorien = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: api.categories,
  })
  const anlegen = useMutation({
    mutationFn: (b: ChallengeInput) => api.createChallenge(b),
    onSuccess: () => {
      setForm(LEER)
      toast('Challenge angelegt', 'ok')
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
    onError: (e: Error) => toast(e.message),
  })
  const abbrechen = useMutation({
    mutationFn: (id: number) => api.cancelChallenge(id),
    onSuccess: () => {
      toast('Challenge abgebrochen', 'ok')
      queryClient.invalidateQueries({ queryKey: ['challenges'] })
    },
    onError: (e: Error) => toast(e.message),
  })

  const set = <K extends keyof ChallengeInput>(k: K, v: ChallengeInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  return (
    <Card>
      <h2 className="mb-3 text-sm font-bold uppercase tracking-wider text-ink-mute">
        Challenges
      </h2>

      <div className="space-y-2">
        <Input
          label="Titel"
          value={form.title}
          onChange={(e) => set('title', e.target.value)}
        />
        <Input
          label="Beschreibung"
          value={form.description ?? ''}
          onChange={(e) => set('description', e.target.value)}
        />
        <Input
          label="Preis (optional)"
          value={form.prize ?? ''}
          onChange={(e) => set('prize', e.target.value)}
        />
        <div className="grid grid-cols-2 gap-2">
          <Select
            label="Modus"
            value={form.mode}
            onChange={(e) => set('mode', e.target.value as Challenge['mode'])}
          >
            <option value="ziel">Ziel erreichen</option>
            <option value="rangliste">Rangliste</option>
          </Select>
          <Select
            label="Wertung"
            value={form.metric}
            onChange={(e) => set('metric', e.target.value as Challenge['metric'])}
          >
            <option value="mm">MM</option>
            {!form.team_mode && <option value="streak">Streak (Tage am Stück)</option>}
            <option value="anzahl">Anzahl Aktivitäten</option>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {form.mode === 'ziel' ? (
            <Input
              label={form.team_mode ? 'Ziel pro Kopf' : 'Ziel'}
              type="number"
              value={String(form.target ?? '')}
              onChange={(e) => set('target', Number(e.target.value))}
            />
          ) : (
            <Input
              label="Gewertete Plätze"
              type="number"
              value={String(form.top_n ?? 1)}
              onChange={(e) => set('top_n', Number(e.target.value))}
            />
          )}
          {form.metric === 'streak' && (
            <Input
              label="Tages-Minimum (MM)"
              type="number"
              value={String(form.streak_min_mm ?? 5)}
              onChange={(e) => set('streak_min_mm', Number(e.target.value))}
            />
          )}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Input
            label="Start"
            type="date"
            value={form.period_start}
            onChange={(e) => set('period_start', e.target.value)}
          />
          <Input
            label="Ende"
            type="date"
            value={form.period_end}
            onChange={(e) => set('period_end', e.target.value)}
          />
        </div>
        <Select
          label="Teilnahme"
          value={form.join_mode}
          onChange={(e) => set('join_mode', e.target.value as Challenge['join_mode'])}
        >
          <option value="auto">Alle automatisch dabei</option>
          <option value="opt_in">Beitritt nötig</option>
        </Select>

        <label className="flex items-center gap-2 text-xs font-semibold text-ink">
          <input
            type="checkbox"
            checked={form.team_mode ?? false}
            onChange={(e) => {
              const team = e.target.checked
              setForm((f) => ({
                ...f,
                team_mode: team,
                metric: team && f.metric === 'streak' ? 'mm' : f.metric,
              }))
            }}
          />
          Gruppen-Challenge
        </label>
        {form.team_mode && (
          <div className="grid grid-cols-2 gap-2">
            <Input
              label="Anzahl Gruppen"
              type="number"
              min={2}
              value={String(form.group_count ?? 3)}
              onChange={(e) => set('group_count', Number(e.target.value))}
            />
            <Input
              label="Setzliste: letzte N Tage"
              type="number"
              min={1}
              value={String(form.seeding_days ?? 30)}
              onChange={(e) => set('seeding_days', Number(e.target.value))}
            />
          </div>
        )}

        <fieldset className="rounded-xl border border-line p-2">
          <legend className="px-1 text-[11px] text-ink-mute">
            Kategorien (keine = alle)
          </legend>
          <div className="flex flex-wrap gap-2">
            {kategorien.map((k) => (
              <label key={k.id} className="flex items-center gap-1 text-xs text-ink">
                <input
                  type="checkbox"
                  checked={(form.category_ids ?? []).includes(k.id)}
                  onChange={(e) =>
                    set(
                      'category_ids',
                      e.target.checked
                        ? [...(form.category_ids ?? []), k.id]
                        : (form.category_ids ?? []).filter((id) => id !== k.id),
                    )
                  }
                />
                {k.name}
              </label>
            ))}
          </div>
        </fieldset>

        <Button
          onClick={() =>
            anlegen.mutate({ ...form, prize: form.prize || null })
          }
          disabled={anlegen.isPending || !form.title || !form.period_start || !form.period_end}
        >
          Challenge anlegen
        </Button>
      </div>

      <ul className="mt-4 space-y-1.5">
        {alle.map((ch) => (
          <li
            key={ch.id}
            className="flex items-center gap-2 rounded-xl border border-line p-2 text-sm"
          >
            <span className="min-w-0 flex-1 truncate text-ink">{ch.title}</span>
            {ch.team_mode && ch.status === 'geplant' && (
              <Link
                to={`/arena/challenges/${ch.id}/gruppen`}
                className="shrink-0 rounded-full border border-accent px-2 py-0.5 text-[11px] font-bold text-accent"
              >
                Gruppen
              </Link>
            )}
            <span className="shrink-0 text-[11px] text-ink-mute">{ch.status}</span>
            {ch.status !== 'beendet' && (
              <button
                onClick={() => abbrechen.mutate(ch.id)}
                className="shrink-0 rounded-full border border-line px-2 py-0.5 text-[11px] text-ink-mute"
              >
                Abbrechen
              </button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}
