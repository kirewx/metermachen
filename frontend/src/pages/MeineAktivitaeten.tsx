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
  const [offen, setOffen] = useState<Set<number>>(new Set())
  const toggle = (catId: number) =>
    setOffen((s) => {
      const next = new Set(s)
      if (next.has(catId)) next.delete(catId)
      else next.add(catId)
      return next
    })
  const gruppen = [...catById.values()]
    .map((cat) => {
      const eintraege = activities.filter((a) => a.category_id === cat.id)
      const summe = eintraege.reduce((s, a) => s + a.scaled_km, 0)
      return { cat, eintraege, summe }
    })
    .filter((g) => g.eintraege.length > 0)
    .sort((a, b) => b.summe - a.summe)

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
        onSubmit={(input) => save.mutateAsync(input)}
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
      <div className="space-y-1">
        {gruppen.map(({ cat, eintraege, summe }) => {
          const auf = offen.has(cat.id)
          return (
            <div key={cat.id} className="border-b border-line/30 last:border-0">
              <button
                type="button"
                onClick={() => toggle(cat.id)}
                className="flex w-full items-center gap-3 py-2.5 text-left"
              >
                <Icon
                  name="chevron"
                  size={14}
                  className={`text-ink-mute transition ${auf ? 'rotate-180' : ''}`}
                />
                <Icon name={cat.icon} size={20} className="shrink-0 text-accent" />
                <span className="flex-1 text-sm font-bold text-ink">{cat.name}</span>
                <span className="text-xs text-ink-mute">{eintraege.length} Einträge</span>
                <span className="w-20 text-right font-mono text-sm font-bold tabular-nums text-accent">
                  {Math.round(summe)} km
                </span>
              </button>
              {auf && (
                <ul className="space-y-1 pb-2 pl-8">
                  {eintraege.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-3 border-t border-line/20 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-ink">
                          <span className="font-mono tabular-nums">{a.distance_km}</span> km
                          <span className="text-accent"> → {a.scaled_km} km</span>
                          {a.edited && (
                            <span className="ml-2 text-xs text-ink-mute">(bearbeitet)</span>
                          )}
                          {a.source === 'strava' && (
                            <span className="ml-2 rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
                              Strava
                            </span>
                          )}
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
                  ))}
                </ul>
              )}
            </div>
          )
        })}
        {activities.length === 0 && <p className="text-sm text-ink-mute">Noch keine Einträge.</p>}
      </div>
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
