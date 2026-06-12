import Icon from './Icon'

type Props = {
  value: number
  onChange: (v: number) => void
  min?: number
  step?: number
  size?: 'hero' | 'kompakt'
}

export default function Stepper({ value, onChange, min = 1, step = 1, size = 'hero' }: Props) {
  const hero = size === 'hero'
  const btn = hero ? 'h-13 w-13' : 'h-8 w-8'
  return (
    <div className={`flex items-center justify-center ${hero ? 'gap-5' : 'gap-2'}`}>
      <button
        type="button"
        aria-label="1 km weniger"
        onClick={() => onChange(Math.max(min, value - step))}
        className={`flex items-center justify-center rounded-full border-2 border-accent/60 text-accent ${btn}`}
      >
        <Icon name="minus" size={hero ? 24 : 14} />
      </button>
      {hero ? (
        <div className="min-w-24 text-center">
          <div
            data-testid="km-wert"
            className="text-5xl font-black tabular-nums text-ink [text-shadow:var(--t-glow-strong)]"
          >
            {value % 1 === 0 ? value : value.toFixed(1)}
          </div>
          <div className="text-xs font-bold tracking-[0.3em] text-accent">KM</div>
        </div>
      ) : (
        <div
          data-testid="km-wert"
          className="min-w-16 text-center text-lg font-black tabular-nums text-ink"
        >
          {value % 1 === 0 ? value : value.toFixed(1)} km
        </div>
      )}
      <button
        type="button"
        aria-label="1 km mehr"
        onClick={() => onChange(value + step)}
        className={`flex items-center justify-center rounded-full bg-accent text-accent-ink shadow-glow-strong ${btn}`}
      >
        <Icon name="plus" size={hero ? 24 : 14} />
      </button>
    </div>
  )
}
