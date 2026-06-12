import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Milestone, type Season } from '../api/client'

export default function Admin() {
  return (
    <div className="space-y-8">
      <Kategorien />
      <Jahr />
      <NeuerUser />
    </div>
  )
}

function Kategorien() {
  const queryClient = useQueryClient()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['categories'] })
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: number; factor?: number; is_active?: boolean }) =>
      api.patchCategory(id, b),
    onSuccess: refresh,
  })
  const [neu, setNeu] = useState({ name: '', factor: '1', color: '#888888', icon: 'medaille', default_km: 10 })
  const create = useMutation({
    mutationFn: () =>
      api.createCategory({ ...neu, factor: parseFloat(neu.factor) }),
    onSuccess: () => {
      setNeu({ name: '', factor: '1', color: '#888888', icon: 'medaille', default_km: 10 })
      refresh()
    },
  })

  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-bold">Kategorien & Faktoren</h2>
      <table className="w-full text-sm">
        <tbody>
          {categories.map((c) => (
            <tr key={c.id} className={`border-b ${c.is_active ? '' : 'opacity-40'}`}>
              <td className="py-1">{c.icon} {c.name}</td>
              <td>
                <input
                  type="number"
                  step="0.5"
                  defaultValue={c.factor}
                  className="w-20 rounded border p-1"
                  onBlur={(e) => {
                    const factor = parseFloat(e.target.value)
                    if (factor > 0 && factor !== c.factor) patch.mutate({ id: c.id, factor })
                  }}
                />{' '}x
              </td>
              <td className="text-right">
                <button
                  className="underline"
                  onClick={() => patch.mutate({ id: c.id, is_active: !c.is_active })}
                >
                  {c.is_active ? 'Deaktivieren' : 'Aktivieren'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex flex-wrap gap-2">
        <input className="rounded border p-1 text-sm" placeholder="Name" value={neu.name}
          onChange={(e) => setNeu({ ...neu, name: e.target.value })} />
        <input className="w-16 rounded border p-1 text-sm" placeholder="Faktor" value={neu.factor}
          onChange={(e) => setNeu({ ...neu, factor: e.target.value })} />
        <input className="w-14 rounded border p-1 text-sm" value={neu.icon}
          onChange={(e) => setNeu({ ...neu, icon: e.target.value })} />
        <input type="color" className="h-8 w-10" value={neu.color}
          onChange={(e) => setNeu({ ...neu, color: e.target.value })} />
        <button
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
          disabled={!neu.name || !(parseFloat(neu.factor) > 0)}
          onClick={() => create.mutate()}
        >
          Kategorie anlegen
        </button>
      </div>
    </section>
  )
}

function Jahr() {
  const queryClient = useQueryClient()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season: Season | undefined = seasons.find((s) => s.year === new Date().getFullYear())
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['seasons'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const [goal, setGoal] = useState('')
  const [milestones, setMilestones] = useState<Milestone[] | null>(null)
  if (!season) return null
  const ms = milestones ?? season.milestones

  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-bold">Jahr {season.year}</h2>
      <label className="text-sm">
        Ziel (skalierte km):{' '}
        <input
          type="number"
          className="w-28 rounded border p-1"
          defaultValue={season.goal_km}
          onChange={(e) => setGoal(e.target.value)}
        />
      </label>
      <h3 className="mt-3 text-sm font-semibold">Meilensteine</h3>
      {ms.map((m, i) => (
        <div key={i} className="mt-1 flex gap-2 text-sm">
          <input type="number" className="w-24 rounded border p-1" value={m.km}
            onChange={(e) => setMilestones(ms.map((x, j) => j === i ? { ...x, km: Number(e.target.value) } : x))} />
          <input className="flex-1 rounded border p-1" value={m.label}
            onChange={(e) => setMilestones(ms.map((x, j) => j === i ? { ...x, label: e.target.value } : x))} />
          <input className="w-14 rounded border p-1" value={m.icon}
            onChange={(e) => setMilestones(ms.map((x, j) => j === i ? { ...x, icon: e.target.value } : x))} />
          <button className="text-red-600" onClick={() => setMilestones(ms.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <div className="mt-2 flex gap-2">
        <button
          className="rounded border px-3 py-1 text-sm"
          onClick={() => setMilestones([...ms, { km: 0, label: '', icon: 'fahne' }])}
        >
          + Meilenstein
        </button>
        <button
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
          onClick={() =>
            api
              .patchSeason(season.id, {
                goal_km: goal ? parseFloat(goal) : undefined,
                milestones: ms,
              })
              .then(refresh)
          }
        >
          Speichern
        </button>
      </div>
      <h3 className="mt-4 text-sm font-semibold">Kartenbild (Aquarell)</h3>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="mt-1 text-sm"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) api.uploadMapImage(season.id, file).then(refresh)
        }}
      />
      {season.map_image && <p className="text-xs text-gray-500">Aktuell: {season.map_image}</p>}
    </section>
  )
}

function NeuerUser() {
  const [form, setForm] = useState({ username: '', password: '', display_name: '', avatar: 'icon:laufen' })
  const [message, setMessage] = useState('')
  const create = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: (u) => {
      setMessage(`✓ ${u.display_name} angelegt`)
      setForm({ username: '', password: '', display_name: '', avatar: 'icon:laufen' })
    },
    onError: (e) => setMessage(e.message),
  })
  return (
    <section className="rounded-2xl bg-white p-4 shadow">
      <h2 className="mb-3 text-lg font-bold">Neuen User anlegen</h2>
      <div className="flex flex-wrap gap-2">
        <input className="rounded border p-1 text-sm" placeholder="Benutzername" value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })} />
        <input className="rounded border p-1 text-sm" placeholder="Anzeigename" value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
        <input className="rounded border p-1 text-sm" placeholder="Passwort" value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <input className="w-14 rounded border p-1 text-sm" value={form.avatar}
          onChange={(e) => setForm({ ...form, avatar: e.target.value })} />
        <button
          className="rounded bg-emerald-600 px-3 py-1 text-sm text-white"
          disabled={!form.username || form.password.length < 4 || !form.display_name}
          onClick={() => create.mutate()}
        >
          Anlegen
        </button>
      </div>
      {message && <p className="mt-2 text-sm">{message}</p>}
    </section>
  )
}
