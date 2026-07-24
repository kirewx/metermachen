import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import SchnellwahlLeiste from '../components/activities/SchnellwahlLeiste'
import JahresVerlauf from '../components/comparison/JahresVerlauf'
import RaceBahnen from '../components/comparison/RaceBahnen'
import SportMix from '../components/comparison/SportMix'
import { useUnitMode } from '../components/comparison/unit'
import WarmupArchiv from '../components/comparison/WarmupArchiv'
import Icon from '../components/ui/Icon'
import { aktiveSeason, saisonLabel } from '../components/ui/season'
import Select from '../components/ui/Select'
import { useToast } from '../components/ui/Toast'

const ANSICHTEN = [
  { key: 'rennen', label: 'Rennen', icon: 'fahne' },
  { key: 'verlauf', label: 'Verlauf', icon: 'chart' },
  { key: 'sportmix', label: 'Sport-Mix', icon: 'medaille' },
] as const
type Ansicht = (typeof ANSICHTEN)[number]['key']

/** Wertet den `?strava=`-Param nach dem OAuth-Rücksprung aus: Toast + Param entfernen. */
function useStravaRedirectHinweis() {
  const [params, setParams] = useSearchParams()
  const toast = useToast()
  const queryClient = useQueryClient()
  const bearbeitet = useRef(false)
  useEffect(() => {
    const s = params.get('strava')
    if (!s || bearbeitet.current) return
    bearbeitet.current = true
    if (s === 'connected') {
      toast('Mit Strava verbunden', 'ok')
      queryClient.invalidateQueries({ queryKey: ['strava-status'] })
    } else if (s === 'denied') {
      toast('Strava-Verbindung abgebrochen')
    } else if (s === 'consent') {
      toast('Bitte stimme zuerst der Anzeige deiner Aktivitäten im Ranking zu.')
    } else {
      toast('Strava-Verbindung fehlgeschlagen. Bitte erneut versuchen.')
    }
    params.delete('strava')
    setParams(params, { replace: true })
  }, [params, setParams, toast, queryClient])
}

export default function Vergleich() {
  const [ansicht, setAnsicht] = useState<Ansicht>('rennen')
  const { mode, toggle: toggleUnit } = useUnitMode()
  useStravaRedirectHinweis()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [gewaehlt, setGewaehlt] = useState<number | 'archiv' | null>(null)
  const aktive = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const archiv = gewaehlt === 'archiv'
  const year = archiv || gewaehlt === null ? aktive : gewaehlt
  const { data, error } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
    enabled: !archiv,
  })

  return (
    <div className="space-y-4">
      <SchnellwahlLeiste />
      <div className="flex flex-wrap items-end gap-2">
        {!archiv &&
          ANSICHTEN.map((a) => (
            <button
              key={a.key}
              onClick={() => setAnsicht(a.key)}
              className={`flex items-center gap-1.5 px-4 py-1 text-sm transition ${
                ansicht === a.key
                  ? 'font-bold text-accent [text-shadow:var(--t-glow)]'
                  : 'text-ink-mute hover:text-ink'
              }`}
            >
              <Icon name={a.icon} size={14} />
              {a.label}
            </button>
          ))}
        {!archiv && (
          <div className="ml-auto flex overflow-hidden rounded-full border border-line text-xs">
            <button
              type="button"
              onClick={() => {
                if (mode !== 'mm') toggleUnit()
              }}
              className={`px-3 py-1 font-bold transition ${
                mode === 'mm' ? 'bg-accent text-accent-ink' : 'text-ink-mute hover:text-ink'
              }`}
            >
              MM
            </button>
            <button
              type="button"
              onClick={() => {
                if (mode !== 'km') toggleUnit()
              }}
              className={`px-3 py-1 font-bold transition ${
                mode === 'km' ? 'bg-accent text-accent-ink' : 'text-ink-mute hover:text-ink'
              }`}
            >
              km
            </button>
          </div>
        )}
        <Select
          label="Saison"
          value={archiv ? 'archiv' : year}
          onChange={(e) =>
            setGewaehlt(e.target.value === 'archiv' ? 'archiv' : Number(e.target.value))
          }
          className="w-24"
        >
          {[...seasons].sort((a, b) => b.year - a.year).map((s) => (
            <option key={s.id} value={s.year}>
              {saisonLabel(s)}
            </option>
          ))}
          <option value="archiv">Archiv (Warm-up)</option>
        </Select>
      </div>
      {archiv && <WarmupArchiv year={aktive} />}
      {!archiv && error && <p className="text-sm text-danger">{error.message}</p>}
      {!archiv && data && ansicht === 'rennen' && <RaceBahnen data={data} mode={mode} />}
      {!archiv && data && ansicht === 'verlauf' && <JahresVerlauf data={data} mode={mode} />}
      {!archiv && data && ansicht === 'sportmix' && <SportMix data={data} mode={mode} />}
    </div>
  )
}
