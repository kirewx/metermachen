import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Comparison } from '../../api/client'
import { profilPfad } from '../profile/pfad'
import Card from '../ui/Card'
import Collapsible from '../ui/Collapsible'
import HoehenSaeulen from './HoehenSaeulen'
import HoehenVerlauf from './HoehenVerlauf'
import { nachHoehe, presetAuswahl, PRESETS, type Preset } from './hoehenAuswahl'
import { formatHm } from './monatsFarbe'
import { userColor } from './userColor'

const UNTERANSICHTEN = [
  { key: 'saeulen', label: 'Säulen' },
  { key: 'verlauf', label: 'Verlauf' },
] as const
type Unteransicht = (typeof UNTERANSICHTEN)[number]['key']

/**
 * Höhenmeter-Ansicht des Vergleichs-Tabs: Panorama oder Verlauf, beide auf
 * derselben Personenauswahl. Höhenmeter zählen ab Challenge-Start und bleiben
 * roh — weder Kategorie- noch Personen-Faktor greifen hier.
 */
export default function Hoehenmeter({ data }: { data: Comparison }) {
  const [unteransicht, setUnteransicht] = useState<Unteransicht>('saeulen')
  const navigate = useNavigate()
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.me })
  const meId = me?.id ?? null
  const sortiert = useMemo(() => nachHoehe(data.users), [data.users])
  const [auswahl, setAuswahl] = useState<Set<number>>(
    () => new Set(data.users.map((u) => u.user_id)),
  )
  const ids = data.users.map((u) => u.user_id)
  const gesamt = data.users.reduce((s, u) => s + u.total_elevation_m, 0)

  const istPreset = (p: Preset) => {
    const s = presetAuswahl(p, sortiert, meId)
    return s.size === auswahl.size && [...s].every((id) => auswahl.has(id))
  }

  if (gesamt === 0) {
    return (
      <Card>
        <p className="text-sm text-ink-mute">
          Noch keine Höhenmeter seit dem Start der Challenge. Sie kommen automatisch aus
          Strava — oder du trägst sie beim Erfassen einer Aktivität selbst ein.
        </p>
      </Card>
    )
  }

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded-full border border-line text-xs">
          {UNTERANSICHTEN.map((a) => (
            <button
              key={a.key}
              type="button"
              onClick={() => setUnteransicht(a.key)}
              aria-pressed={unteransicht === a.key}
              className={`px-3 py-1 font-bold transition ${
                unteransicht === a.key
                  ? 'bg-accent text-accent-ink'
                  : 'text-ink-mute hover:text-ink'
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
        <div className="ml-auto flex flex-wrap gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              onClick={() => setAuswahl(presetAuswahl(p.key, sortiert, meId))}
              aria-pressed={istPreset(p.key)}
              className={`rounded-full border px-2.5 py-1 text-xs font-bold transition ${
                istPreset(p.key)
                  ? 'border-accent text-accent'
                  : 'border-line text-ink-mute hover:text-ink'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {unteransicht === 'saeulen' ? (
        <HoehenSaeulen
          users={data.users.filter((u) => auswahl.has(u.user_id))}
          months={data.elevation_months}
          meId={meId}
          onSelect={(u) => navigate(profilPfad(u.user_id, data.year))}
        />
      ) : (
        <HoehenVerlauf data={data} auswahl={auswahl} meId={meId} />
      )}

      <Collapsible title={`Personen (${auswahl.size}/${data.users.length})`}>
        <div className="flex flex-wrap gap-1.5">
          {sortiert.map((u) => {
            const an = auswahl.has(u.user_id)
            const farbe = userColor(u.user_id, ids)
            return (
              <button
                key={u.user_id}
                type="button"
                aria-pressed={an}
                aria-label={`${u.display_name} ein-/ausblenden`}
                onClick={() =>
                  setAuswahl((prev) => {
                    const next = new Set(prev)
                    if (next.has(u.user_id)) next.delete(u.user_id)
                    else next.add(u.user_id)
                    return next
                  })
                }
                className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition ${
                  an ? 'text-ink' : 'text-ink-mute opacity-50'
                }`}
                style={{ borderColor: an ? farbe : 'var(--t-line)' }}
              >
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ background: an ? farbe : 'var(--t-ink-mute)' }}
                />
                {u.display_name}
                <span className="font-mono tabular-nums text-ink-mute">
                  {formatHm(u.total_elevation_m)}
                </span>
              </button>
            )
          })}
        </div>
      </Collapsible>
    </Card>
  )
}
