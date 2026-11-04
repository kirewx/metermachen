import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import Avatar from '../ui/Avatar'
import Card from '../ui/Card'
import SectionTitle from '../ui/SectionTitle'
import { km, useTogetherAktiv } from './together'

/** Trainingspartner im Profil: der häufigste groß, darunter die Rangliste
 * (Platz 1 dezent hervorgehoben). Nichts ohne gemeinsame Einheiten. */
export default function PartnerCard({ userId }: { userId: number }) {
  const aktiv = useTogetherAktiv()
  const { data: partner = [] } = useQuery({
    queryKey: ['together-partners', userId],
    queryFn: () => api.togetherPartners(userId),
    enabled: aktiv,
  })
  if (!aktiv || partner.length === 0) return null
  const [top] = partner
  const max = top.sessions

  return (
    <Card>
      <SectionTitle>Trainingspartner</SectionTitle>
      <div className="flex items-center gap-3 rounded-xl border border-accent bg-accent/5 p-3 shadow-glow">
        <Avatar value={top.avatar} size="lg" />
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-bold uppercase tracking-wider text-accent">
            Häufigster Partner
          </p>
          <p className="truncate text-lg font-black text-ink">{top.display_name}</p>
        </div>
        <div className="text-right">
          <p className="font-display text-3xl font-bold leading-none text-accent">
            {top.sessions}×
          </p>
          <p className="font-mono text-xs text-ink-mute">{km(top.km_together)} km</p>
        </div>
      </div>
      <ol className="mt-3 space-y-0.5">
        {partner.map((p, i) => (
          <li
            key={p.user_id}
            className={`flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm ${
              i === 0 ? 'bg-accent/10' : ''
            }`}
          >
            <span
              className={`w-4 font-black tabular-nums ${i === 0 ? 'text-accent' : 'text-ink-mute'}`}
            >
              {i + 1}
            </span>
            <Avatar value={p.avatar} size="sm" />
            <span className="w-16 truncate font-bold text-ink">{p.display_name}</span>
            <span className="relative h-3 flex-1 overflow-hidden rounded-full border border-line bg-surface">
              <span
                className={`absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-accent/15 ${
                  i === 0 ? 'to-accent shadow-glow' : 'to-accent/70'
                }`}
                style={{ width: `${(p.sessions / max) * 100}%` }}
              />
            </span>
            <span className="w-24 shrink-0 whitespace-nowrap text-right font-mono text-xs text-ink-mute">
              <b className={i === 0 ? 'text-accent' : 'text-ink'}>{p.sessions}×</b> ·{' '}
              {km(p.km_together)} km
            </span>
          </li>
        ))}
      </ol>
    </Card>
  )
}
