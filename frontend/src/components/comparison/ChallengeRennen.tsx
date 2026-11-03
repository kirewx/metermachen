import { Link } from 'react-router-dom'
import type { Challenge, ChallengeGroup } from '../../api/client'
import { teamFarbe, tint } from '../challenges/teamFarben'
import { einheit } from '../challenges/wertung'
import Avatar from '../ui/Avatar'
import Card from '../ui/Card'
import { statusText } from './challengeStatus'
import { userColor } from './userColor'

const zahl = (v: number) => v.toLocaleString('de-DE', { maximumFractionDigits: 1 })

function Tauziehen({ ch, a, b }: { ch: Challenge; a: ChallengeGroup; b: ChallengeGroup }) {
  const summe = a.value + b.value
  // Before anybody has meters the bar sits in the middle.
  const anteilA = summe > 0 ? a.value / summe : 0.5
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="flex min-w-0 items-baseline gap-2">
          <span className="font-display text-2xl font-bold" style={{ color: teamFarbe(a) }}>
            {zahl(a.value)}
          </span>
          <span className="truncate text-sm font-bold text-ink">{a.name}</span>
        </span>
        <span className="hidden text-[10px] uppercase tracking-wider text-ink-mute sm:inline">
          {einheit(ch.metric)} pro Kopf
        </span>
        <span className="flex min-w-0 items-baseline gap-2">
          <span className="truncate text-sm font-bold text-ink">{b.name}</span>
          <span className="font-display text-2xl font-bold" style={{ color: teamFarbe(b) }}>
            {zahl(b.value)}
          </span>
        </span>
      </div>
      <div className="flex h-3 gap-[3px] overflow-hidden rounded-full" data-testid="tauziehen">
        <span style={{ flex: anteilA, background: teamFarbe(a) }} />
        <span style={{ flex: 1 - anteilA, background: teamFarbe(b) }} />
      </div>
    </div>
  )
}

function Teamwertung({ ch }: { ch: Challenge }) {
  const gruppen = [...ch.groups].sort((x, y) => x.rank - y.rank || x.id - y.id)
  const max = Math.max(...gruppen.map((g) => g.value), ch.target ?? 0, 1)
  return (
    <div className="space-y-2.5">
      <div className="flex items-baseline justify-between">
        <span className="font-display text-lg font-bold">Teamwertung</span>
        <span className="text-[10px] uppercase tracking-wider text-ink-mute">
          {einheit(ch.metric)} pro Kopf
        </span>
      </div>
      {gruppen.map((g) => {
        const farbe = teamFarbe(g)
        return (
          <div key={g.id} className="flex items-center gap-3" data-testid="teamzeile">
            <span className="w-5 text-sm font-black text-ink-mute">{g.rank}</span>
            <span className="w-28 truncate text-sm font-extrabold" style={{ color: farbe }}>
              {g.name}
            </span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-accent/10">
              <div
                className="h-full rounded-full"
                style={{ width: `${(g.value / max) * 100}%`, background: farbe }}
              />
            </div>
            <span className="w-16 text-right font-display text-xl font-bold" style={{ color: farbe }}>
              {zahl(g.value)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function Kennzahlen({ ch }: { ch: Challenge }) {
  const geschafft = ch.standings.filter((s) => s.geschafft).length
  const fuehrt = ch.standings.find((s) => s.rank === 1 && s.value > 0)
  const items: { wert: string; label: string }[] =
    ch.mode === 'ziel'
      ? [
          { wert: `${zahl(ch.target ?? 0)} ${einheit(ch.metric)}`, label: 'Ziel' },
          { wert: `${geschafft} von ${ch.standings.length}`, label: 'geschafft' },
        ]
      : [
          { wert: fuehrt?.display_name ?? '–', label: 'führt' },
          { wert: `Top ${ch.top_n}`, label: 'gewinnen' },
        ]
  if (ch.prize) items.push({ wert: ch.prize, label: 'Preis' })
  return (
    <div className="flex flex-wrap gap-x-8 gap-y-2">
      {items.map((i) => (
        <div key={i.label} className="min-w-0">
          <p className="truncate font-display text-2xl font-bold text-accent">{i.wert}</p>
          <p className="text-[10px] uppercase tracking-wider text-ink-mute">{i.label}</p>
        </div>
      ))}
    </div>
  )
}

/** Race lanes for one challenge: its period, metric and teams (spec 2026-11-04). */
export default function ChallengeRennen({ ch, today = new Date() }: { ch: Challenge; today?: Date }) {
  const teams = ch.team_mode && ch.groups.length >= 2
  const teamVon = new Map(ch.groups.flatMap((g) => g.members.map((m) => [m.user_id, g] as const)))
  const ids = ch.standings.map((s) => s.user_id)
  // Teams compare per head, so the per-person goal line only fits challenges without teams.
  const ziel = !teams && ch.mode === 'ziel' && ch.target ? ch.target : null
  const max = Math.max(ziel ?? 0, ...ch.standings.map((s) => s.value), 1)
  const pct = (v: number) => `${(v / max) * 100}%`
  const sortiert = [...ch.standings].sort((a, b) => a.rank - b.rank || b.value - a.value)

  return (
    <div className="space-y-3">
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/arena/challenges/${ch.id}`}
            className="min-w-0 truncate text-sm font-bold text-ink hover:text-accent"
          >
            {ch.title} →
          </Link>
          <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink-mute">
            {statusText(ch, today)}
          </span>
        </div>
        {teams && ch.groups.length === 2 && <Tauziehen ch={ch} a={ch.groups[0]} b={ch.groups[1]} />}
        {teams && ch.groups.length > 2 && <Teamwertung ch={ch} />}
        {!teams && <Kennzahlen ch={ch} />}
      </Card>
      <Card className="space-y-1.5">
        {sortiert.length === 0 && (
          <p className="p-4 text-center text-sm text-ink-mute">Noch niemand dabei.</p>
        )}
        {sortiert.map((s) => {
          const gruppe = teams ? teamVon.get(s.user_id) : undefined
          const farbe = gruppe ? teamFarbe(gruppe) : userColor(s.user_id, ids)
          const fuehrt = s.rank === 1 && s.value > 0
          const raus = !teams && s.nicht_mehr_schaffbar
          return (
            <div
              key={s.user_id}
              data-testid="challenge-bahn"
              // Phone: the bar gets its own full-width line under name and value.
              className={`flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl px-2 py-1.5 sm:flex-nowrap sm:py-1 ${
                raus ? 'opacity-55' : ''
              }`}
              style={gruppe ? { background: tint(farbe, 0.08) } : undefined}
            >
              <span
                className={`w-6 text-sm font-black tabular-nums ${
                  fuehrt ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
                }`}
              >
                {s.value > 0 ? s.rank : '–'}
              </span>
              <span
                className="rounded-full"
                style={gruppe ? { boxShadow: `0 0 0 2px ${farbe}` } : undefined}
                title={gruppe?.name}
              >
                <Avatar value={s.avatar} size="sm" />
              </span>
              <span className="flex min-w-0 flex-1 items-center gap-1.5 sm:w-36 sm:flex-none">
                <span className="truncate text-sm font-bold text-ink">{s.display_name}</span>
                {!teams && s.geschafft && ch.mode === 'ziel' && (
                  <span className="shrink-0 rounded-full border border-accent px-1.5 text-[10px] font-black text-accent">
                    ✓
                  </span>
                )}
              </span>
              <div className="relative order-last h-3 basis-full overflow-hidden rounded-full border border-line bg-surface sm:order-none sm:h-5 sm:flex-1 sm:basis-auto">
                <div
                  className="balken-wachsen absolute inset-y-0 left-0 rounded-full"
                  style={{
                    width: pct(s.value),
                    background: `linear-gradient(90deg, transparent, ${farbe})`,
                    boxShadow: fuehrt ? `0 0 14px ${farbe}` : `0 0 6px ${farbe}55`,
                  }}
                />
                {ziel !== null && (
                  <span
                    className="absolute inset-y-0 w-0.5 bg-accent/80"
                    style={{ left: pct(ziel) }}
                    title={`Ziel ${zahl(ziel)}`}
                  />
                )}
              </div>
              <p className="w-20 shrink-0 text-right text-base font-black whitespace-nowrap tabular-nums text-ink sm:w-28 sm:text-lg">
                {zahl(s.value)}{' '}
                <span className="text-xs font-normal text-ink-mute">{einheit(ch.metric)}</span>
              </p>
            </div>
          )
        })}
      </Card>
    </div>
  )
}
