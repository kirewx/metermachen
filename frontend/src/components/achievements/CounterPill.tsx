// How often / how many on an unlocked achievement, e.g. "×3" or "Rekord: 12 Leute".
// Sits on its own line below the title so it never pushes out of narrow cards.
export default function CounterPill({ text }: { text: string }) {
  return (
    <span className="mt-1.5 inline-block max-w-full truncate rounded-full border border-accent bg-accent/10 px-2 py-0.5 align-top font-mono text-[10px] font-bold tabular-nums text-accent">
      {text}
    </span>
  )
}
