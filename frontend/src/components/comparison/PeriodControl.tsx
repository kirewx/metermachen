import { isFinishedMonth, monthLabel, type PeriodMode } from './period'

type Props = {
  mode: PeriodMode
  /** False on views that always cover the whole season (Höhenmeter). */
  showModeToggle: boolean
  /** Seasons in ascending order. */
  years: { year: number; label: string }[]
  year: number
  months: string[]
  month: string | null
  today?: Date
  onModeChange: (mode: PeriodMode) => void
  onYearChange: (year: number) => void
  onMonthChange: (month: string) => void
}

const PILLS: { key: PeriodMode; label: string }[] = [
  { key: 'month', label: 'Monat' },
  { key: 'year', label: 'Jahr' },
]

export default function PeriodControl({
  mode,
  showModeToggle,
  years,
  year,
  months,
  month,
  today = new Date(),
  onModeChange,
  onYearChange,
  onMonthChange,
}: Props) {
  const monthly = showModeToggle && mode === 'month' && month !== null
  const index = monthly ? months.indexOf(month) : years.findIndex((y) => y.year === year)
  const count = monthly ? months.length : years.length
  const label = monthly ? monthLabel(month) : (years[index]?.label ?? String(year))
  const step = (delta: number) => {
    const next = index + delta
    if (index < 0 || next < 0 || next >= count) return
    if (monthly) onMonthChange(months[next])
    else onYearChange(years[next].year)
  }
  const arrow =
    'grid h-7 w-7 place-items-center rounded-full border border-line text-accent transition hover:bg-accent/10 disabled:opacity-30 disabled:hover:bg-transparent'

  return (
    <div className="flex flex-wrap items-center gap-2">
      {showModeToggle && (
        <div className="flex overflow-hidden rounded-full border border-line text-xs">
          {PILLS.map((p) => (
            <button
              key={p.key}
              type="button"
              disabled={p.key === 'month' && months.length === 0}
              onClick={() => {
                if (mode !== p.key) onModeChange(p.key)
              }}
              className={`px-3 py-1 font-bold transition disabled:opacity-40 ${
                mode === p.key ? 'bg-accent text-accent-ink' : 'text-ink-mute hover:text-ink'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          aria-label={monthly ? 'Vorheriger Monat' : 'Vorherige Saison'}
          disabled={index <= 0}
          onClick={() => step(-1)}
          className={arrow}
        >
          ‹
        </button>
        <span className="min-w-[4.5rem] text-center text-sm font-bold tabular-nums text-ink">
          {label}
        </span>
        <button
          type="button"
          aria-label={monthly ? 'Nächster Monat' : 'Nächste Saison'}
          disabled={index < 0 || index >= count - 1}
          onClick={() => step(1)}
          className={arrow}
        >
          ›
        </button>
      </div>
      {monthly && isFinishedMonth(month, today) && (
        <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-mute">
          Endstand
        </span>
      )}
    </div>
  )
}
