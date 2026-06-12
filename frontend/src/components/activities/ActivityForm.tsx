import { useState } from 'react'
import type { Activity, ActivityInput, Category } from '../../api/client'

type Props = {
  categories: Category[]
  onSubmit: (input: ActivityInput) => void
  initial?: Activity
}

export default function ActivityForm({ categories, onSubmit, initial }: Props) {
  const active = categories.filter((c) => c.is_active || c.id === initial?.category_id)
  const [categoryId, setCategoryId] = useState(initial?.category_id ?? active[0]?.id ?? 0)
  const [date, setDate] = useState(initial?.date ?? '')
  const [distance, setDistance] = useState(initial ? String(initial.distance_km) : '')
  const [duration, setDuration] = useState(initial?.duration_min ? String(initial.duration_min) : '')
  const [note, setNote] = useState(initial?.note ?? '')

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const distance_km = parseFloat(distance)
    if (!date || !categoryId || !Number.isFinite(distance_km) || distance_km <= 0) return
    onSubmit({
      category_id: categoryId,
      date,
      distance_km,
      duration_min: duration ? parseInt(duration, 10) : null,
      note: note || null,
    })
  }

  return (
    <form onSubmit={submit} className="grid gap-3 rounded-xl bg-white p-4 shadow sm:grid-cols-2">
      <label className="flex flex-col text-sm">
        Kategorie
        <select
          className="rounded border p-2"
          value={categoryId}
          onChange={(e) => setCategoryId(Number(e.target.value))}
        >
          {active.map((c) => (
            <option key={c.id} value={c.id}>
              {c.icon_emoji} {c.name} ({c.factor}x)
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col text-sm">
        Datum
        <input
          type="date"
          className="rounded border p-2"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </label>
      <label className="flex flex-col text-sm">
        Distanz (km)
        <input
          type="number"
          step="0.01"
          min="0.01"
          className="rounded border p-2"
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
        />
      </label>
      <label className="flex flex-col text-sm">
        Dauer (min, optional)
        <input
          type="number"
          min="1"
          className="rounded border p-2"
          value={duration}
          onChange={(e) => setDuration(e.target.value)}
        />
      </label>
      <label className="flex flex-col text-sm sm:col-span-2">
        Notiz
        <input
          className="rounded border p-2"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      <button className="rounded bg-emerald-600 p-2 font-semibold text-white sm:col-span-2">
        Speichern
      </button>
    </form>
  )
}
