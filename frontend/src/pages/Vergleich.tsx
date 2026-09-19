import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import Hoehenmeter from '../components/comparison/Hoehenmeter'
import JahresVerlauf from '../components/comparison/JahresVerlauf'
import { defaultMonth } from '../components/comparison/period'
import PeriodControl from '../components/comparison/PeriodControl'
import RaceBahnen from '../components/comparison/RaceBahnen'
import SportMix from '../components/comparison/SportMix'
import { useUnitMode } from '../components/comparison/unit'
import { usePeriodMode } from '../components/comparison/usePeriodMode'
import WarmupArchiv from '../components/comparison/WarmupArchiv'
import Icon from '../components/ui/Icon'
import { aktiveSeason, saisonLabel } from '../components/ui/season'
import { useToast } from '../components/ui/Toast'

const ANSICHTEN = [
  { key: 'rennen', label: 'Rennen', icon: 'fahne' },
  { key: 'verlauf', label: 'Verlauf', icon: 'chart' },
  { key: 'sportmix', label: 'Sport-Mix', icon: 'medaille' },
  { key: 'hoehenmeter', label: 'Höhenmeter', icon: 'berg' },
] as const
type Ansicht = (typeof ANSICHTEN)[number]['key']

const VIEW_KEY = 'mm_vergleich_view'

/** Last opened view tab, remembered in the browser; unknown stored values fall back to Rennen. */
function useStoredView() {
  const [ansicht, setAnsicht] = useState<Ansicht>(() => {
    const stored = localStorage.getItem(VIEW_KEY)
    return ANSICHTEN.find((a) => a.key === stored)?.key ?? 'rennen'
  })
  useEffect(() => {
    localStorage.setItem(VIEW_KEY, ansicht)
  }, [ansicht])
  return [ansicht, setAnsicht] as const
}

/** Views that can be shown per month; the others always cover the whole season. */
const MONTH_VIEWS: readonly Ansicht[] = ['rennen', 'verlauf', 'sportmix']

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
  const [ansicht, setAnsicht] = useStoredView()
  const { mode, toggle: toggleUnit } = useUnitMode()
  useStravaRedirectHinweis()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [gewaehlt, setGewaehlt] = useState<number | null>(null)
  const [archiv, setArchiv] = useState(false)
  const [period, setPeriod] = usePeriodMode()
  // The month the user stepped to; null means "the season's default month".
  const [month, setMonth] = useState<string | null>(null)
  const [today] = useState(() => new Date())
  const aktive = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const year = gewaehlt ?? aktive

  // The season query is always loaded: it carries the month axis for the stepper.
  const seasonQuery = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
    enabled: !archiv,
  })
  const months = seasonQuery.data?.months ?? []
  const shownMonth = month !== null && months.includes(month) ? month : defaultMonth(months, today)
  const monthViews = MONTH_VIEWS.includes(ansicht)
  const monthly = period === 'month' && monthViews && shownMonth !== null
  const monthQuery = useQuery({
    queryKey: ['comparison', year, shownMonth],
    queryFn: () => api.comparison(year, shownMonth ?? undefined),
    enabled: !archiv && monthly,
    // Keep the previous month on screen while stepping, instead of a blank flash.
    placeholderData: keepPreviousData,
  })
  const { data, error } = monthly ? monthQuery : seasonQuery
  const years = [...seasons]
    .sort((a, b) => a.year - b.year)
    .map((s) => ({ year: s.year, label: saisonLabel(s) }))

  if (archiv) {
    return (
      <div className="space-y-4">
        <button
          type="button"
          onClick={() => setArchiv(false)}
          className="text-sm text-ink-mute underline transition hover:text-ink"
        >
          Zurück zum Vergleich
        </button>
        <WarmupArchiv year={aktive} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        {ANSICHTEN.map((a) => (
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
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <PeriodControl
          // A season without months can only be shown as a whole.
          mode={months.length === 0 ? 'year' : period}
          showModeToggle={monthViews}
          years={years}
          year={year}
          months={months}
          month={shownMonth}
          today={today}
          onModeChange={(next) => {
            setPeriod(next)
            setMonth(null)
          }}
          onYearChange={(next) => {
            // Months belong to one season, so a season change falls back to its default month.
            setGewaehlt(next)
            setMonth(null)
          }}
          onMonthChange={setMonth}
        />
        {/* Höhenmeter sind roh — MM/km-Umschalter hat dort keine Bedeutung. */}
        {ansicht !== 'hoehenmeter' && (
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
      </div>
      {error && <p className="text-sm text-danger">{error.message}</p>}
      {data && ansicht === 'rennen' && <RaceBahnen data={data} mode={mode} />}
      {data && ansicht === 'verlauf' && <JahresVerlauf data={data} mode={mode} />}
      {data && ansicht === 'sportmix' && <SportMix data={data} mode={mode} />}
      {data && ansicht === 'hoehenmeter' && <Hoehenmeter data={data} />}
      <div className="pt-2 text-center">
        <button
          type="button"
          onClick={() => setArchiv(true)}
          className="text-xs text-ink-mute underline transition hover:text-ink"
        >
          Warm-up-Archiv
        </button>
      </div>
    </div>
  )
}
