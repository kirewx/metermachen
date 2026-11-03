// How often / how many on an unlocked achievement, e.g. "×3" or "Rekord: 12 Leute".
export default function CounterPill({ text }: { text: string }) {
  return (
    <span className="ml-auto shrink-0 rounded-full border border-accent px-2 py-0.5 font-mono text-[10px] font-bold tabular-nums text-accent">
      {text}
    </span>
  )
}
