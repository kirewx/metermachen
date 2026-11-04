import { useId, useState } from 'react'
import type { TogetherPartner } from '../../api/client'
import Avatar from '../ui/Avatar'

type Props = {
  value: number[]
  onChange: (ids: number[]) => void
  /** Taggbare Mitglieder (`/api/together/members`: ohne einen selbst und ohne Opt-out). */
  members: TogetherPartner[]
}

/** „Mit wem?“ im Aktivitätsformular: Suchfeld, Gewählte als Chips. */
export default function PartnerPicker({ value, onChange, members }: Props) {
  const id = useId()
  const [suche, setSuche] = useState('')
  const [fokus, setFokus] = useState(false)
  const gewaehlt = value
    .map((uid) => members.find((m) => m.user_id === uid))
    .filter((m): m is TogetherPartner => !!m)
  const q = suche.trim().toLowerCase()
  // Namen, die mit der Eingabe beginnen, zuerst
  const treffer = members
    .filter((m) => !value.includes(m.user_id) && m.display_name.toLowerCase().includes(q))
    .sort(
      (a, b) =>
        Number(!a.display_name.toLowerCase().startsWith(q)) -
        Number(!b.display_name.toLowerCase().startsWith(q)),
    )

  function waehle(uid: number) {
    onChange([...value, uid])
    setSuche('')
  }

  return (
    <div className="flex flex-col gap-1 text-xs font-semibold text-ink-mute sm:col-span-2">
      <label htmlFor={id}>Mit wem? (optional)</label>
      <div className="flex min-h-11 flex-wrap items-center gap-1.5 rounded-xl border border-line bg-surface p-1.5 focus-within:border-accent">
        {gewaehlt.map((m) => (
          <span
            key={m.user_id}
            className="inline-flex items-center gap-1 rounded-full border border-accent bg-accent/15 py-0.5 pl-2.5 pr-0.5 text-sm font-bold text-ink"
          >
            {m.display_name}
            <button
              type="button"
              aria-label={`${m.display_name} entfernen`}
              onClick={() => onChange(value.filter((uid) => uid !== m.user_id))}
              className="h-7 w-7 rounded-full text-ink-soft hover:text-accent"
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          value={suche}
          onChange={(e) => setSuche(e.target.value)}
          onFocus={() => setFokus(true)}
          onBlur={() => setFokus(false)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && treffer[0]) {
              e.preventDefault()
              waehle(treffer[0].user_id)
            }
          }}
          placeholder={gewaehlt.length ? '' : 'Name suchen'}
          className="min-w-20 flex-1 bg-transparent p-1 text-sm font-normal text-ink outline-none"
        />
      </div>
      {fokus && treffer.length > 0 && (
        <ul className="overflow-hidden rounded-xl border border-line bg-card">
          {treffer.map((m) => (
            <li key={m.user_id} className="border-t border-line/30 first:border-0">
              <button
                type="button"
                // vor dem Blur des Suchfelds auswählen
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => waehle(m.user_id)}
                className="flex min-h-11 w-full items-center gap-2 px-2.5 text-left text-sm font-normal text-ink hover:bg-accent/10"
              >
                <Avatar value={m.avatar} size="sm" />
                {m.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="font-normal">Nur Leute mit aktivierter Erkennung. Sie bestätigen selbst.</p>
    </div>
  )
}
