import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Activity, type ActivityInput } from '../api/client'
import ActivityForm from '../components/activities/ActivityForm'
import Icon from '../components/ui/Icon'

export default function MeineAktivitaeten() {
  const year = new Date().getFullYear()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Activity | null>(null)
  const [error, setError] = useState('')

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities = [] } = useQuery({
    queryKey: ['activities', year],
    queryFn: () => api.activities(year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['activities'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const save = useMutation({
    mutationFn: (input: ActivityInput) =>
      editing ? api.patchActivity(editing.id, input) : api.createActivity(input),
    onSuccess: () => {
      setEditing(null)
      setError('')
      invalidate()
    },
    onError: (e) => setError(e.message),
  })
  const remove = useMutation({ mutationFn: api.deleteActivity, onSuccess: invalidate })

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{editing ? 'Eintrag bearbeiten' : 'Neue Aktivität'}</h1>
      <ActivityForm
        key={editing?.id ?? 'new'}
        categories={categories}
        initial={editing ?? undefined}
        onSubmit={save.mutate}
      />
      {editing && (
        <button className="text-sm text-gray-500 underline" onClick={() => setEditing(null)}>
          Bearbeiten abbrechen
        </button>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <h2 className="text-lg font-semibold">Meine Einträge {year}</h2>
      <ul className="space-y-2">
        {activities.map((a) => {
          const cat = catById.get(a.category_id)
          return (
            <li key={a.id} className="flex items-center gap-3 rounded-xl bg-white p-3 shadow">
              {cat && <Icon name={cat.icon} className="text-accent" />}
              <div className="flex-1">
                <p className="font-medium">
                  {a.date} · {a.distance_km} km {cat?.name} → <b>{a.scaled_km} km</b>
                  {a.edited && <span className="ml-2 text-xs text-gray-400">(bearbeitet)</span>}
                </p>
                {(a.note || a.duration_min) && (
                  <p className="text-sm text-gray-500">
                    {a.duration_min ? `${a.duration_min} min` : ''}
                    {a.duration_min && a.note ? ' · ' : ''}
                    {a.note}
                  </p>
                )}
              </div>
              <button className="text-sm underline" onClick={() => setEditing(a)}>
                Bearbeiten
              </button>
              <button
                className="text-sm text-red-600 underline"
                onClick={() => confirm('Eintrag löschen?') && remove.mutate(a.id)}
              >
                Löschen
              </button>
            </li>
          )
        })}
        {activities.length === 0 && <p className="text-gray-500">Noch keine Einträge.</p>}
      </ul>
    </div>
  )
}
