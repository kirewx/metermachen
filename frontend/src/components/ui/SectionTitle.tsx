export default function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 border-b border-line/40 pb-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-ink-tech">
      <span className="text-accent">// </span>
      {children}
    </h2>
  )
}
