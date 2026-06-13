type Props = { label: string; value: string; glow?: boolean }

export default function StatValue({ label, value, glow = false }: Props) {
  return (
    <div>
      <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">{label}</div>
      <div
        className={`text-2xl font-black tabular-nums text-ink ${glow ? '[text-shadow:var(--t-glow-strong)]' : ''}`}
      >
        {value}
      </div>
    </div>
  )
}
