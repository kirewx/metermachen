import { Link } from 'react-router-dom'
import type { Challenge } from '../../api/client'
import { einheit, fortschritt } from './wertung'

function restTage(bis: string): number {
  const ende = new Date(`${bis}T23:59:59`)
  return Math.max(Math.ceil((ende.getTime() - Date.now()) / 86_400_000), 0)
}

export default function ChallengeHeroCard({ ch }: { ch: Challenge }) {
  const meins = ch.mein_stand
  const wert = meins?.value ?? 0
  const pct = Math.round(fortschritt(ch, wert) * 100)
  return (
    <Link
      to={`/challenges/${ch.id}`}
      className="block min-w-[86%] shrink-0 snap-start rounded-2xl border-2 border-accent bg-card p-4"
    >
      <p className="text-[10px] font-bold uppercase tracking-widest text-accent">
        {ch.vorlaeufig ? 'Endstand vorläufig' : `noch ${restTage(ch.period_end)} Tage`}
      </p>
      <h3 className="mt-1 text-lg font-extrabold text-ink">{ch.title}</h3>
      <p className="mt-1.5 text-2xl font-extrabold text-ink">
        {wert}
        {ch.mode === 'ziel' && ch.target !== null && (
          <span className="text-sm font-semibold text-ink-mute">
            {' '}
            / {ch.target} {einheit(ch.metric)}
          </span>
        )}
      </p>
      {ch.mode === 'ziel' && (
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-line">
          <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
        </div>
      )}
      {meins && (
        <p className="mt-1 text-[11px] text-ink-mute">
          Platz {meins.rank} von {ch.standings.length}
        </p>
      )}
      {ch.prize && (
        <p className="mt-2 inline-block rounded-full bg-line px-2 py-0.5 text-[11px] font-semibold text-ink">
          🎁 {ch.prize}
        </p>
      )}
    </Link>
  )
}
