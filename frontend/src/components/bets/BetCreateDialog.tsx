import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Bet, type BetParams, type Me } from '../../api/client'
import Button from '../ui/Button'
import Input from '../ui/Input'
import Modal from '../ui/Modal'
import Select from '../ui/Select'
import { useToast } from '../ui/Toast'
import type { Spieler } from './BetCard'

type Typ = Exclude<Bet['type'], 'monats_tipp'>

const TYPEN: { key: Typ; label: string; hilfe: string }[] = [
  { key: 'duell', label: 'Duell', hilfe: 'Mehr km als dein Gegner im Zeitraum — optional mit Vorsprung oder Faktor.' },
  { key: 'ziel', label: 'Ziel-Wette', hilfe: 'Du wettest, dass du dein km-Ziel schaffst. Andere können dagegenhalten.' },
  { key: 'streak', label: 'Streak-Wette', hilfe: 'N Tage in Folge Sport (mind. 1 km pro Tag). Andere halten dagegen.' },
  { key: 'ueber_unter', label: 'Über/Unter', hilfe: 'Schafft die ganze Gruppe zusammen das km-Ziel? Alle setzen Über oder Unter.' },
]

function isoInTagen(tage: number) {
  const d = new Date()
  d.setDate(d.getDate() + tage)
  return d.toISOString().slice(0, 10)
}

export default function BetCreateDialog({
  open,
  onClose,
  me,
  spieler,
  maxEinsatz,
}: {
  open: boolean
  onClose: () => void
  me: Me
  spieler: Spieler[]
  maxEinsatz: number
}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [typ, setTyp] = useState<Typ>('duell')
  const [einsatz, setEinsatz] = useState(10)
  const [von, setVon] = useState(isoInTagen(1))
  const [bis, setBis] = useState(isoInTagen(7))
  const [gegner, setGegner] = useState<number | ''>('')
  const [vorsprung, setVorsprung] = useState(0)
  const [faktorIch, setFaktorIch] = useState(1)
  const [faktorGegner, setFaktorGegner] = useState(1)
  const [zielKm, setZielKm] = useState(30)
  const [streakTage, setStreakTage] = useState(5)
  const [seite, setSeite] = useState<'ueber' | 'unter'>('ueber')

  const andere = spieler.filter((s) => s.user_id !== me.id)

  const erstellen = useMutation({
    mutationFn: () => {
      const params: BetParams = {}
      let title: string
      if (typ === 'duell') {
        const g = andere.find((s) => s.user_id === gegner)
        if (!g) throw new Error('Bitte Gegner wählen')
        params.opponent_id = g.user_id
        if (vorsprung > 0) params.vorsprung_km = vorsprung
        if (faktorIch !== 1) params.factor_creator = faktorIch
        if (faktorGegner !== 1) params.factor_opponent = faktorGegner
        title = `${me.display_name} vs. ${g.display_name}`
      } else if (typ === 'ziel') {
        params.target_km = zielKm
        title = `${me.display_name}: ${zielKm} km bis ${new Date(`${bis}T00:00:00`).toLocaleDateString('de-DE')}`
      } else if (typ === 'streak') {
        params.streak_days = streakTage
        title = `${me.display_name}: ${streakTage} Tage am Stück`
      } else {
        params.target_km = zielKm
        params.side = seite
        title = `Gruppe: ${zielKm} km — Über oder Unter?`
      }
      return api.createBet({
        type: typ,
        title,
        stake: einsatz,
        period_start: von,
        period_end: bis,
        params,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bets'] })
      queryClient.invalidateQueries({ queryKey: ['points'] })
      queryClient.invalidateQueries({ queryKey: ['pointsRanking'] })
      toast('Wette erstellt', 'ok')
      onClose()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <Modal open={open} onClose={onClose} title="Neue Wette">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-2">
          {TYPEN.map((t) => (
            <button
              key={t.key}
              onClick={() => setTyp(t.key)}
              className={`rounded-xl border p-2 text-left text-sm transition ${
                typ === t.key
                  ? 'border-accent text-accent shadow-glow'
                  : 'border-line text-ink-mute hover:text-ink'
              }`}
            >
              <span className="font-bold">{t.label}</span>
              <span className="mt-0.5 block text-xs">{t.hilfe}</span>
            </button>
          ))}
        </div>

        {typ === 'duell' && (
          <div className="space-y-2">
            <Select
              label="Gegner"
              value={gegner}
              onChange={(e) => setGegner(Number(e.target.value))}
            >
              <option value="">– wählen –</option>
              {andere.map((s) => (
                <option key={s.user_id} value={s.user_id}>
                  {s.display_name}
                </option>
              ))}
            </Select>
            <div className="flex gap-2">
              <Input
                label="Vorsprung für Gegner (km)"
                type="number"
                min="0"
                value={vorsprung}
                onChange={(e) => setVorsprung(Number(e.target.value))}
                className="flex-1"
              />
              <Input
                label="Mein Faktor"
                type="number"
                step="0.1"
                min="0.1"
                value={faktorIch}
                onChange={(e) => setFaktorIch(Number(e.target.value))}
                className="w-24"
              />
              <Input
                label="Gegner-Faktor"
                type="number"
                step="0.1"
                min="0.1"
                value={faktorGegner}
                onChange={(e) => setFaktorGegner(Number(e.target.value))}
                className="w-24"
              />
            </div>
          </div>
        )}
        {(typ === 'ziel' || typ === 'ueber_unter') && (
          <Input
            label={typ === 'ziel' ? 'Mein Ziel (km)' : 'Gruppen-Ziel (km)'}
            type="number"
            min="1"
            value={zielKm}
            onChange={(e) => setZielKm(Number(e.target.value))}
          />
        )}
        {typ === 'streak' && (
          <Input
            label="Tage in Folge"
            type="number"
            min="1"
            value={streakTage}
            onChange={(e) => setStreakTage(Number(e.target.value))}
          />
        )}
        {typ === 'ueber_unter' && (
          <Select
            label="Ich setze auf"
            value={seite}
            onChange={(e) => setSeite(e.target.value as 'ueber' | 'unter')}
          >
            <option value="ueber">Über — wir schaffen das</option>
            <option value="unter">Unter — niemals</option>
          </Select>
        )}

        <div className="flex gap-2">
          <Input
            label="Von"
            type="date"
            value={von}
            onChange={(e) => setVon(e.target.value)}
            className="flex-1"
          />
          <Input
            label="Bis"
            type="date"
            value={bis}
            onChange={(e) => setBis(e.target.value)}
            className="flex-1"
          />
        </div>
        <Input
          label={`Einsatz (max. ${maxEinsatz} P)`}
          type="number"
          min="1"
          max={maxEinsatz}
          value={einsatz}
          onChange={(e) => setEinsatz(Number(e.target.value))}
        />
        <Button
          className="w-full"
          disabled={erstellen.isPending || einsatz < 1 || einsatz > maxEinsatz}
          onClick={() => erstellen.mutate()}
        >
          Wette erstellen ({einsatz} P)
        </Button>
      </div>
    </Modal>
  )
}
