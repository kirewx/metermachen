import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Bet, type Me } from '../../api/client'
import Button from '../ui/Button'
import Card from '../ui/Card'
import Input from '../ui/Input'
import Select from '../ui/Select'
import { useToast } from '../ui/Toast'

const TYP_LABEL: Record<Bet['type'], string> = {
  duell: 'Duell',
  monats_tipp: 'Monats-Tipp',
  ziel: 'Ziel-Wette',
  streak: 'Streak-Wette',
  ueber_unter: 'Über/Unter',
}

const STATUS_LABEL: Record<Bet['status'], string> = {
  offen: 'wartet auf Antwort',
  laufend: 'läuft',
  entschieden: 'entschieden',
  abgelehnt: 'abgelehnt',
  abgebrochen: 'abgebrochen',
}

function datum(d: string) {
  return new Date(`${d}T00:00:00`).toLocaleDateString('de-DE', {
    day: '2-digit',
    month: '2-digit',
  })
}

function name(bet: Bet, userId: number | undefined) {
  const p = bet.participants.find((t) => t.user_id === userId)
  return p?.display_name ?? `#${userId}`
}

export type Spieler = { user_id: number; display_name: string }

export default function BetCard({
  bet,
  me,
  spieler,
}: {
  bet: Bet
  me: Me
  spieler: Spieler[]
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [gegenEinsatz, setGegenEinsatz] = useState(5)
  const [tipp, setTipp] = useState<number | ''>('')
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['bets'] })
    queryClient.invalidateQueries({ queryKey: ['points'] })
    queryClient.invalidateQueries({ queryKey: ['pointsRanking'] })
  }
  const respond = useMutation({
    mutationFn: (b: { action: string; stake?: number; choice?: { tipp_user_id?: number } }) =>
      api.respondBet(bet.id, b),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
  const cancel = useMutation({
    mutationFn: () => api.cancelBet(bet.id),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })

  const istErsteller = bet.creator_id === me.id
  const binDabei = bet.my_role !== null
  const nochNichtGestartet = new Date(`${bet.period_start}T00:00:00`) > new Date()
  const duellGegnerId = bet.params.opponent_id
  const binGefordert =
    bet.type === 'duell' && bet.status === 'offen' && duellGegnerId === me.id

  const gewinner = bet.result.winner_ids ?? []

  return (
    <Card className={bet.status === 'entschieden' ? 'opacity-80' : ''}>
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="rounded-full border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-tech">
          {TYP_LABEL[bet.type]}
        </span>
        <span className="font-bold text-ink">{bet.title}</span>
        <span className="ml-auto font-mono text-xs text-ink-mute">
          {datum(bet.period_start)}–{datum(bet.period_end)} · {STATUS_LABEL[bet.status]}
        </span>
      </div>

      <p className="mt-2 text-sm text-ink-mute">
        Einsatz <span className="font-bold text-accent">{bet.stake} P</span>
        {bet.jackpot > 0 && (
          <span className="ml-2 text-accent">+ {bet.jackpot} P Jackpot</span>
        )}
        {bet.type === 'duell' && bet.params.vorsprung_km ? (
          <span className="ml-2">· {bet.params.vorsprung_km} km Vorsprung</span>
        ) : null}
        {bet.type === 'duell' &&
        (bet.params.factor_creator ?? 1) !== 1 ? (
          <span className="ml-2">· {name(bet, bet.creator_id)} ×{bet.params.factor_creator}</span>
        ) : null}
        {bet.type === 'duell' &&
        (bet.params.factor_opponent ?? 1) !== 1 ? (
          <span className="ml-2">· {name(bet, duellGegnerId)} ×{bet.params.factor_opponent}</span>
        ) : null}
      </p>

      {/* Live-Zwischenstand */}
      {bet.status === 'laufend' && Object.keys(bet.standing).length > 0 && (
        <p className="mt-1 font-mono text-sm tabular-nums text-ink">
          {bet.type === 'duell' && (
            <>
              {name(bet, bet.creator_id)} {bet.standing.creator_km?.toFixed(1)} km —{' '}
              {bet.standing.opponent_km?.toFixed(1)} km {name(bet, duellGegnerId)}
            </>
          )}
          {(bet.type === 'ziel' || bet.type === 'streak') && (
            <>
              Stand:{' '}
              {bet.type === 'streak'
                ? `${bet.standing.streak ?? 0} Tage Serie / ${bet.params.streak_days} nötig`
                : `${bet.standing.km?.toFixed(1) ?? 0} / ${bet.params.target_km} km`}
            </>
          )}
          {bet.type === 'ueber_unter' && (
            <>
              Gruppe: {bet.standing.gruppen_km?.toFixed(1)} / {bet.params.target_km} km
            </>
          )}
        </p>
      )}

      {/* Teilnehmer */}
      <p className="mt-2 text-xs text-ink-mute">
        {bet.participants
          .map((t) => {
            const extra =
              t.role === 'tipper' && t.choice.tipp_user_id
                ? ` tippt ${name(bet, t.choice.tipp_user_id)}`
                : t.role === 'gegenhalter'
                  ? ` hält ${t.stake} P dagegen`
                  : t.role === 'ueber' || t.role === 'unter'
                    ? ` setzt auf ${t.role === 'ueber' ? 'Über' : 'Unter'}`
                    : ''
            const won = gewinner.includes(t.user_id) ? ' ✓' : ''
            return `${t.display_name}${extra}${won}`
          })
          .join(' · ')}
      </p>

      {/* Ergebnis */}
      {bet.status === 'entschieden' && (
        <p className="mt-2 text-sm font-bold text-ink">
          {gewinner.length > 0
            ? `Gewonnen: ${gewinner.map((id) => name(bet, id)).join(', ')}`
            : 'Unentschieden — Einsätze zurück'}
          {bet.result.david && <span className="ml-2 text-accent">David gegen Goliath!</span>}
        </p>
      )}

      {/* Aktionen */}
      <div className="mt-3 flex flex-wrap items-end gap-2">
        {binGefordert && (
          <>
            <Button onClick={() => respond.mutate({ action: 'accept' })}>
              Annehmen ({bet.stake} P)
            </Button>
            <Button variant="danger" onClick={() => respond.mutate({ action: 'decline' })}>
              Ablehnen
            </Button>
          </>
        )}
        {(bet.type === 'ziel' || bet.type === 'streak') &&
          bet.status === 'laufend' &&
          nochNichtGestartet &&
          !istErsteller && (
            <>
              <Input
                label="Dagegen (P)"
                type="number"
                min="1"
                value={gegenEinsatz}
                onChange={(e) => setGegenEinsatz(Number(e.target.value))}
                className="w-24"
              />
              <Button
                variant="ghost"
                onClick={() =>
                  respond.mutate({ action: 'dagegenhalten', stake: gegenEinsatz })
                }
              >
                Dagegenhalten
              </Button>
            </>
          )}
        {bet.type === 'ueber_unter' &&
          bet.status === 'laufend' &&
          nochNichtGestartet &&
          !binDabei && (
            <>
              <Button variant="ghost" onClick={() => respond.mutate({ action: 'ueber' })}>
                Über ({bet.stake} P)
              </Button>
              <Button variant="ghost" onClick={() => respond.mutate({ action: 'unter' })}>
                Unter ({bet.stake} P)
              </Button>
            </>
          )}
        {bet.type === 'monats_tipp' && bet.status === 'laufend' && !binDabei && (
          <>
            <Select
              label="Mein Tipp"
              value={tipp}
              onChange={(e) => setTipp(Number(e.target.value))}
              className="w-40"
            >
              <option value="">– wählen –</option>
              {spieler.map((s) => (
                <option key={s.user_id} value={s.user_id}>
                  {s.display_name}
                </option>
              ))}
            </Select>
            <Button
              disabled={tipp === ''}
              onClick={() =>
                respond.mutate({ action: 'tippen', choice: { tipp_user_id: Number(tipp) } })
              }
            >
              Tippen ({bet.stake} P)
            </Button>
          </>
        )}
        {istErsteller &&
          (bet.status === 'offen' || bet.status === 'laufend') &&
          bet.type !== 'monats_tipp' &&
          nochNichtGestartet && (
            <Button variant="ghost" onClick={() => cancel.mutate()}>
              Stornieren
            </Button>
          )}
      </div>
    </Card>
  )
}
