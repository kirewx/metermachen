import { useState } from 'react'
import type { Activity, ActivityInput, Category } from '../../api/client'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Icon from '../ui/Icon'
import Input from '../ui/Input'
import Select from '../ui/Select'
import Stepper from '../ui/Stepper'

const heute = () => new Date().toISOString().slice(0, 10)

type Props = {
  categories: Category[]
  variant?: 'hero' | 'kompakt'
  initial?: Activity
  onSubmit: (input: ActivityInput) => void | Promise<unknown>
  onCancel?: () => void
}

export default function SchnellwahlCard({
  categories,
  variant = 'hero',
  initial,
  onSubmit,
  onCancel,
}: Props) {
  const aktive = categories.filter((c) => c.is_active || c.id === initial?.category_id)
  const gemerkt = Number(localStorage.getItem('schnellwahl-kategorie'))
  const [categoryId, setCategoryId] = useState(
    initial?.category_id ??
      (aktive.some((c) => c.id === gemerkt) ? gemerkt : (aktive[0]?.id ?? 0)),
  )
  const kategorie = aktive.find((c) => c.id === categoryId)
  // String-State, damit Zwischenzustände wie "7," beim Tippen erhalten bleiben.
  const [kmText, setKmText] = useState(String(initial?.distance_km ?? kategorie?.default_km ?? 10))
  const [details, setDetails] = useState(Boolean(initial))
  const [date, setDate] = useState(initial?.date ?? heute())
  const [duration, setDuration] = useState(initial?.duration_min ? String(initial.duration_min) : '')
  const [note, setNote] = useState(initial?.note ?? '')
  const [pulsiert, setPulsiert] = useState(false)

  const km = parseFloat(kmText.replace(',', '.'))

  function wechselKategorie(id: number) {
    setCategoryId(id)
    localStorage.setItem('schnellwahl-kategorie', String(id))
    if (!initial) setKmText(String(aktive.find((c) => c.id === id)?.default_km ?? 10))
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!categoryId || !Number.isFinite(km) || km <= 0 || !date) return
    Promise.resolve(
      onSubmit({
        category_id: categoryId,
        date,
        distance_km: km,
        duration_min: duration ? parseInt(duration, 10) : null,
        note: note || null,
      }),
    )
      .then(() => {
        setPulsiert(true)
        window.setTimeout(() => setPulsiert(false), 700)
        if (!initial) {
          setKmText(String(kategorie?.default_km ?? 10))
          setDetails(false)
          setDate(heute())
          setDuration('')
          setNote('')
        }
      })
      .catch(() => {
        /* Fehler-Toast zeigt der Aufrufer; Eingaben bleiben erhalten */
      })
  }

  const gewertet = kategorie && Number.isFinite(km) ? (km * kategorie.factor).toFixed(1) : '0.0'
  const datumText = date === heute() ? 'heute' : date

  return (
    <form onSubmit={submit}>
      <Card
        glow
        className={`${variant === 'hero' ? 'mx-auto max-w-md p-6 text-center' : 'p-3'} ${pulsiert ? 'glow-puls' : ''}`}
      >
        <div className={variant === 'hero' ? 'space-y-4' : 'flex flex-wrap items-end gap-3'}>
          <Select
            label="Kategorie"
            value={categoryId}
            onChange={(e) => wechselKategorie(Number(e.target.value))}
            className={variant === 'hero' ? 'mx-auto w-56 text-left' : 'w-44'}
          >
            {aktive.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} · {c.factor}x
              </option>
            ))}
          </Select>
          <Stepper
            value={Number.isFinite(km) ? km : 0}
            onChange={(v) => setKmText(String(v))}
            size={variant === 'hero' ? 'hero' : 'kompakt'}
          />
          {variant === 'hero' && (
            <p className="text-xs text-ink-mute">
              = {gewertet} km gewertet · {datumText}
            </p>
          )}
          <Button type="submit" className={variant === 'hero' ? 'w-full' : ''}>
            <span className="inline-flex items-center gap-1">
              Eintragen <Icon name="blitz" size={14} />
            </span>
          </Button>
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              Abbrechen
            </Button>
          )}
        </div>
        <button
          type="button"
          onClick={() => setDetails(!details)}
          className="mt-3 inline-flex items-center gap-1 text-xs text-ink-mute hover:text-accent"
        >
          <Icon name="chevron" size={12} className={details ? 'rotate-180' : ''} />
          Details
        </button>
        {details && (
          <div className="mt-3 grid gap-3 text-left sm:grid-cols-2">
            <Input label="Datum" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            <Input
              label="km (frei)"
              type="text"
              inputMode="decimal"
              value={kmText}
              onChange={(e) => setKmText(e.target.value)}
            />
            <Input
              label="Dauer (min)"
              type="number"
              min="1"
              value={duration}
              onChange={(e) => setDuration(e.target.value)}
            />
            <Input label="Notiz" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
        )}
      </Card>
    </form>
  )
}
