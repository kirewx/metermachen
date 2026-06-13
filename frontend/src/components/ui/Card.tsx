type Props = { className?: string; glow?: boolean; children: React.ReactNode }

export default function Card({ className = '', glow = false, children }: Props) {
  return (
    <section
      className={`rounded-2xl border border-line bg-card p-4 ${glow ? 'shadow-glow' : ''} ${className}`}
    >
      {children}
    </section>
  )
}
