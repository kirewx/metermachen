import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Activity, type ActivityInput } from '../api/client'
import SchnellwahlCard from '../components/activities/SchnellwahlCard'
import Button from '../components/ui/Button'
import Icon from '../components/ui/Icon'
import Modal from '../components/ui/Modal'
import { useToast } from '../components/ui/Toast'

export default function MeineAktivitaeten() {
  const year = new Date().getFullYear()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<Activity | null>(null)
  const [loeschId, setLoeschId] = useState<number | null>(null)

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities = [] } = useQuery({
    queryKey: ['activities', year],
    queryFn: () => api.activities(year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))
  const gesamt = activities.reduce((s, a) => s + a.scaled_km, 0)

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['activities'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const save = useMutation({
    mutationFn: (input: ActivityInput) =>
      editing ? api.patchActivity(editing.id, input) : api.createActivity(input),
    onSuccess: () => {
      if (editing) toast('Eintrag aktualisiert', 'ok')
      setEditing(null)
      invalidate()
    },
    onError: (e) => toast(e.message),
  })
  const remove = useMutation({
    mutationFn: api.deleteActivity,
    onSuccess: () => {
      setLoeschId(null)
      invalidate()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <div className="space-y-6">
      <SchnellwahlCard
        key={editing?.id ?? 'neu'}
        categories={categories}
        initial={editing ?? undefined}
        onSubmit={save.mutate}
        onCancel={editing ? () => setEditing(null) : undefined}
      />
      <div className="flex items-baseline justify-between">
        <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
          Meine Einträge {year}
        </h2>
        <span className="text-sm font-black tabular-nums text-accent [text-shadow:var(--t-glow)]">
          {Math.round(gesamt)} km gewertet
        </span>
      </div>
      <ul className="space-y-2">
        {activities.map((a) => {
          const cat = catById.get(a.category_id)
          return (
            <li
              key={a.id}
              className="flex items-center gap-3 rounded-2xl border border-line bg-card p-3"
            >
              {cat && <Icon name={cat.icon} size={22} className="shrink-0 text-accent" />}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-ink">
                  {a.distance_km} km {cat?.name}{' '}
                  <span className="text-accent">→ {a.scaled_km} km</span>
                  {a.edited && <span className="ml-2 text-xs font-normal text-ink-mute">(bearbeitet)</span>}
                </p>
                <p className="truncate text-xs text-ink-mute">
                  {a.date}
                  {a.duration_min ? ` · ${a.duration_min} min` : ''}
                  {a.note ? ` · ${a.note}` : ''}
                </p>
              </div>
              <button
                aria-label="Bearbeiten"
                className="text-ink-mute hover:text-accent"
                onClick={() => setEditing(a)}
              >
                <Icon name="stift" size={16} />
              </button>
              <button
                aria-label="Löschen"
                className="text-ink-mute hover:text-danger"
                onClick={() => setLoeschId(a.id)}
              >
                <Icon name="papierkorb" size={16} />
              </button>
            </li>
          )
        })}
        {activities.length === 0 && <p className="text-sm text-ink-mute">Noch keine Einträge.</p>}
      </ul>
      <Modal open={loeschId !== null} onClose={() => setLoeschId(null)} title="Eintrag löschen?">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setLoeschId(null)}>
            Abbrechen
          </Button>
          <Button variant="danger" onClick={() => loeschId !== null && remove.mutate(loeschId)}>
            Löschen
          </Button>
        </div>
      </Modal>
    </div>
  )
}
