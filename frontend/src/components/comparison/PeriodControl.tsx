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
  /** True until the first response: the month axis is not known yet. */
  loading?: boolean
  today?: Date
  onModeChange: (mode: PeriodMode) => void
  onYearChange: (year: number) => void
  onMonthChange: (month: string) => void
  /** Started challenges in ascending order; the Challenge pill only shows when there are any. */
  challenges?: { id: number; label: string }[]
  challengeId?: number | null
  onChallengeChange?: (id: number) => void
}

const PILLS: { key: PeriodMode; label: string }[] = [
  { key: 'month', label: 'Monat' },
  { key: 'year', label: 'Jahr' },
  { key: 'challenge', label: 'Challenge' },
]

export default function PeriodControl({
  mode,
  showModeToggle,
  years,
  year,
  months,
  month,
  loading = false,
  today = new Date(),
  onModeChange,
  onYearChange,
  onMonthChange,
  challenges = [],
  challengeId = null,
  onChallengeChange,
}: Props) {
  const challengeMode = showModeToggle && mode === 'challenge' && challenges.length > 0
  if (challengeMode) {
    const ci = challenges.findIndex((c) => c.id === challengeId)
    return (
      <div className="flex flex-wrap items-center gap-2">
        <ModePills
          mode={mode}
          months={months}
          loading={loading}
          withChallenge
          onModeChange={onModeChange}
        />
        <Stepper
          label={challenges[ci]?.label ?? '…'}
          prevLabel="Vorherige Challenge"
          nextLabel="Nächste Challenge"
          canPrev={ci > 0}
          canNext={ci >= 0 && ci < challenges.length - 1}
          onStep={(delta) => onChallengeChange?.(challenges[ci + delta].id)}
        />
      </div>
    )
  }
  const monthly = showModeToggle && mode === 'month' && month !== null
  // Month mode before its first response: there is nothing to step through yet, and
  // the arrows must not fall back to stepping seasons.
  const waiting = showModeToggle && mode === 'month' && month === null && loading
  const index = waiting
    ? -1
    : monthly
      ? months.indexOf(month)
      : years.findIndex((y) => y.year === year)
  const count = monthly ? months.length : years.length
  const label = waiting ? '…' : monthly ? monthLabel(month) : (years[index]?.label ?? String(year))
  const step = (delta: number) => {
    const next = index + delta
    if (index < 0 || next < 0 || next >= count) return
    if (monthly) onMonthChange(months[next])
    else onYearChange(years[next].year)
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {showModeToggle && (
        <ModePills
          mode={mode}
          months={months}
          loading={loading}
          withChallenge={challenges.length > 0}
          onModeChange={onModeChange}
        />
      )}
      <Stepper
        label={label}
        prevLabel={monthly || waiting ? 'Vorheriger Monat' : 'Vorherige Saison'}
        nextLabel={monthly || waiting ? 'Nächster Monat' : 'Nächste Saison'}
        canPrev={index > 0}
        canNext={index >= 0 && index < count - 1}
        onStep={step}
      />
      {monthly && isFinishedMonth(month, today) && (
        <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-mute">
          Endstand
        </span>
      )}
    </div>
  )
}

function ModePills({
  mode,
  months,
  loading,
  withChallenge,
  onModeChange,
}: {
  mode: PeriodMode
  months: string[]
  loading: boolean
  withChallenge: boolean
  onModeChange: (mode: PeriodMode) => void
}) {
  return (
    <div className="flex overflow-hidden rounded-full border border-line text-xs">
      {PILLS.filter((p) => withChallenge || p.key !== 'challenge').map((p) => (
        <button
          key={p.key}
          type="button"
          disabled={p.key === 'month' && months.length === 0 && !loading}
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
  )
}

const ARROW =
  'grid h-7 w-7 place-items-center rounded-full border border-line text-accent transition hover:bg-accent/10 disabled:opacity-30 disabled:hover:bg-transparent'

function Stepper({
  label,
  prevLabel,
  nextLabel,
  canPrev,
  canNext,
  onStep,
}: {
  label: string
  prevLabel: string
  nextLabel: string
  canPrev: boolean
  canNext: boolean
  onStep: (delta: number) => void
}) {
  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        aria-label={prevLabel}
        disabled={!canPrev}
        onClick={() => onStep(-1)}
        className={ARROW}
      >
        ‹
      </button>
      <span className="min-w-[4.5rem] text-center text-sm font-bold tabular-nums text-ink">
        {label}
      </span>
      <button
        type="button"
        aria-label={nextLabel}
        disabled={!canNext}
        onClick={() => onStep(1)}
        className={ARROW}
      >
        ›
      </button>
    </div>
  )
}
