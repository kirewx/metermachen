import { useState } from 'react'
import Icon from './Icon'

// Einklappbare Admin-Sektion. Der Inhalt bleibt gemountet (nur per CSS versteckt),
// damit die enthaltenen useQuery-Daten warm bleiben und nicht bei jedem Aufklappen
// neu laden.
export default function Collapsible({
  title,
  defaultOpen = false,
  children,
}: {
  title: React.ReactNode
  defaultOpen?: boolean
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="mb-3 flex w-full items-center gap-2 border-b border-line/40 pb-1.5 text-left font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-ink-tech hover:text-ink"
      >
        <Icon
          name="chevron"
          size={12}
          className={`shrink-0 text-accent transition ${open ? 'rotate-180' : ''}`}
        />
        <span className="text-accent">// </span>
        {title}
      </button>
      <div className={open ? '' : 'hidden'}>{children}</div>
    </section>
  )
}
