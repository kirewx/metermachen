import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Bet } from '../api/client'
import BetCard, { type Spieler } from '../components/bets/BetCard'
import BetCreateDialog from '../components/bets/BetCreateDialog'
import Blackboard from '../components/bets/Blackboard'
import PunkteRanking from '../components/bets/PunkteRanking'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'

export default function Wetten() {
  const [dialogOffen, setDialogOffen] = useState(false)
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.me })
  const { data: punkte } = useQuery({ queryKey: ['points'], queryFn: api.points })
  const { data: wetten = [], error } = useQuery({ queryKey: ['bets'], queryFn: api.bets })
  const { data: achievements = [] } = useQuery({
    queryKey: ['betAchievements'],
    queryFn: api.betAchievements,
  })
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  const year = new Date().getFullYear()
  const { data: vergleich } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
  })

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (!me) return null

  const spieler: Spieler[] =
    vergleich?.users.map((u) => ({ user_id: u.user_id, display_name: u.display_name })) ?? []

  const blackboardAktiv = addons.some((a) => a.key === 'blackboard' && a.active)

  const wartetAufMich = (b: Bet) =>
    (b.status === 'offen' && b.params.opponent_id === me.id) ||
    (b.status === 'laufend' && b.my_role === null &&
      (b.type === 'monats_tipp' ||
        ((b.type === 'ziel' || b.type === 'streak' || b.type === 'ueber_unter') &&
          new Date(`${b.period_start}T00:00:00`) > new Date())))
  const offenFuerMich = wetten.filter(wartetAufMich)
  const laufend = wetten.filter((b) => !wartetAufMich(b) && (b.status === 'laufend' || b.status === 'offen'))
  const historie = wetten.filter((b) =>
    ['entschieden', 'abgelehnt', 'abgebrochen'].includes(b.status),
  )
  const erreicht = achievements.filter((a) => a.achieved)

  return (
    <div className="space-y-6">
      <Card glow className="flex flex-wrap items-center gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-ink-mute">Mein Punktekonto</p>
          <p className="text-3xl font-black tabular-nums text-accent [text-shadow:var(--t-glow)]">
            {punkte?.balance ?? '–'} <span className="text-base font-normal">Punkte</span>
          </p>
        </div>
        <p className="max-w-56 text-xs text-ink-mute">
          Nachschub gibt's über Sport: +1 Punkt je 5 gewertete km seit Challenge-Start.
        </p>
        <Button className="ml-auto" onClick={() => setDialogOffen(true)}>
          <span className="flex items-center gap-1.5">
            <Icon name="blitz" size={14} /> Neue Wette
          </span>
        </Button>
      </Card>

      {offenFuerMich.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-black uppercase tracking-wider text-accent">
            Offen für dich
          </h2>
          {offenFuerMich.map((b) => (
            <BetCard key={b.id} bet={b} me={me} spieler={spieler} />
          ))}
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-black uppercase tracking-wider text-ink-mute">
          Laufende Wetten
        </h2>
        {laufend.length === 0 && (
          <p className="text-sm text-ink-mute">
            Noch nichts los — fordere jemanden heraus!
          </p>
        )}
        {laufend.map((b) => (
          <BetCard key={b.id} bet={b} me={me} spieler={spieler} />
        ))}
      </section>

      {blackboardAktiv && (
        <section className="space-y-3">
          <h2 className="text-sm font-black uppercase tracking-wider text-ink-mute">
            Blackboard
          </h2>
          <Blackboard bets={wetten} spieler={spieler} />
        </section>
      )}

      <PunkteRanking />

      {erreicht.length > 0 && (
        <Card>
          <h2 className="text-lg font-black tracking-wide text-ink">Wett-Erfolge</h2>
          <ul className="mt-3 space-y-2">
            {erreicht.map((a) => (
              <li key={a.key} className="flex items-center gap-3 text-sm">
                <Icon name={a.icon} size={18} className="text-accent" />
                <span className="font-bold text-ink">{a.title}</span>
                <span className="text-ink-mute">{a.description}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {historie.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-black uppercase tracking-wider text-ink-mute">
            Historie
          </h2>
          {historie.map((b) => (
            <BetCard key={b.id} bet={b} me={me} spieler={spieler} />
          ))}
        </section>
      )}

      <BetCreateDialog
        open={dialogOffen}
        onClose={() => setDialogOffen(false)}
        me={me}
        spieler={spieler}
        maxEinsatz={punkte?.balance ?? 0}
      />
    </div>
  )
}
