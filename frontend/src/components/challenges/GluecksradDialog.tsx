import { useEffect, useRef, useState } from 'react'
import type { Challenge, ChallengeGroup, SiegerWahl } from '../../api/client'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import {
  gruppenKandidaten,
  mitgliederKandidaten,
  personenKandidaten,
  zielRotation,
  ziehe,
} from './gluecksrad'
import type { Kandidat } from './gluecksrad'

const RADIUS = 95

/** Point on the rim, `grad` clockwise from the top. */
function punkt(grad: number, r = RADIUS): [number, number] {
  const rad = (grad * Math.PI) / 180
  return [Math.sin(rad) * r, -Math.cos(rad) * r]
}

function kurz(text: string): string {
  return text.length > 12 ? `${text.slice(0, 11)}…` : text
}

function Rad({ kandidaten, rotation, dauerMs }: {
  kandidaten: Kandidat[]
  rotation: number
  dauerMs: number
}) {
  const n = kandidaten.length
  const breite = 360 / Math.max(n, 1)
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[300px]">
      {/* Zeiger oben, dreht nicht mit */}
      <div
        aria-hidden
        className="absolute left-1/2 top-0 z-10 h-0 w-0 -translate-x-1/2 border-x-[10px] border-t-[18px] border-x-transparent border-t-ink"
      />
      <div
        data-testid="rad"
        className="h-full w-full"
        style={{
          transform: `rotate(${rotation}deg)`,
          transition: `transform ${dauerMs}ms cubic-bezier(0.17, 0.67, 0.12, 0.99)`,
        }}
      >
        <svg viewBox="-100 -100 200 200" className="h-full w-full" role="img" aria-label="Glücksrad">
          {n === 0 && <circle r={RADIUS} className="fill-line" />}
          {n === 1 && <circle r={RADIUS} fill="hsl(190 65% 40%)" />}
          {n > 1 &&
            kandidaten.map((k, i) => {
              const [x0, y0] = punkt(i * breite)
              const [x1, y1] = punkt((i + 1) * breite)
              return (
                <path
                  key={k.id}
                  d={`M0 0 L${x0} ${y0} A${RADIUS} ${RADIUS} 0 ${breite > 180 ? 1 : 0} 1 ${x1} ${y1}Z`}
                  fill={`hsl(${(i * 360) / n + 190} 65% 40%)`}
                  stroke="white"
                  strokeWidth={0.8}
                />
              )
            })}
          {kandidaten.map((k, i) => (
            <text
              key={k.id}
              transform={`rotate(${(i + 0.5) * breite - 90}) translate(${n === 1 ? 0 : 58} 0)`}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="white"
              fontSize={n > 12 ? 7 : 10}
              fontWeight={700}
            >
              {kurz(k.label)}
            </text>
          ))}
          <circle r={9} className="fill-card" stroke="white" strokeWidth={1.5} />
        </svg>
      </div>
    </div>
  )
}

type Runde = { art: 'gruppe' } | { art: 'person'; gruppe: ChallengeGroup | null }

function kandidatenFuer(ch: Challenge, runde: Runde): Kandidat[] {
  if (runde.art === 'gruppe') return gruppenKandidaten(ch)
  return runde.gruppe ? mitgliederKandidaten(runde.gruppe) : personenKandidaten(ch)
}

function weniger(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

type Props = {
  ch: Challenge
  open: boolean
  onClose: () => void
  onSieger: (sieger: SiegerWahl) => void
  speichert: boolean
  dauerMs?: number
  /** Random source for tests; defaults to crypto.getRandomValues. */
  zufall?: () => number
}

/** Wheel of fortune for the prize winner of a finished target challenge.
 * The admin picks who is in the draw (qualified people/groups preselected),
 * spins on their own screen and saves the result as the winner. Group
 * challenges draw a group first, then one of its members. */
export default function GluecksradDialog({
  ch, open, onClose, onSieger, speichert, dauerMs = 4500, zufall,
}: Props) {
  const start: Runde = ch.team_mode ? { art: 'gruppe' } : { art: 'person', gruppe: null }
  const [runde, setRunde] = useState<Runde>(start)
  const kandidaten = kandidatenFuer(ch, runde)
  const [auswahl, setAuswahl] = useState<Set<number>>(
    () => new Set(kandidaten.filter((k) => k.vorgewaehlt).map((k) => k.id)),
  )
  const [rotation, setRotation] = useState(0)
  const [dreht, setDreht] = useState(false)
  const [ergebnis, setErgebnis] = useState<Kandidat | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)
  useEffect(() => () => clearTimeout(timer.current), [])

  const imRad = kandidaten.filter((k) => auswahl.has(k.id))
  const dauer = weniger() ? 0 : dauerMs

  function neueRunde(r: Runde) {
    const neu = kandidatenFuer(ch, r)
    setRunde(r)
    setAuswahl(new Set(neu.filter((k) => k.vorgewaehlt).map((k) => k.id)))
    setErgebnis(null)
  }

  function umschalten(id: number) {
    const neu = new Set(auswahl)
    if (neu.has(id)) neu.delete(id)
    else neu.add(id)
    setAuswahl(neu)
    setErgebnis(null)
  }

  function drehen() {
    const n = imRad.length
    const index = ziehe(n, zufall)
    const lage = ziehe(1000, zufall) / 1000
    setErgebnis(null)
    setDreht(true)
    setRotation((r) => zielRotation(index, n, r, lage))
    timer.current = setTimeout(() => {
      setErgebnis(imRad[index])
      setDreht(false)
    }, dauer)
  }

  const gruppenRunde = runde.art === 'gruppe'
  const mitgliederRunde = runde.art === 'person' && runde.gruppe !== null
  const gezogeneGruppe = gruppenRunde && ergebnis
    ? ch.groups.find((g) => g.id === ergebnis.id) ?? null
    : null

  return (
    <Modal open={open} onClose={onClose} title="Glücksrad">
      <div className="space-y-4">
        <p className="text-xs text-ink-mute">
          {gruppenRunde
            ? 'Runde 1: Welche Gruppe gewinnt?'
            : runde.gruppe
              ? `Runde 2: Wer aus ${runde.gruppe.name} gewinnt?`
              : 'Wer gewinnt?'}
        </p>

        <Rad kandidaten={imRad} rotation={rotation} dauerMs={dauer} />

        {ergebnis && (
          <p className="text-center text-lg font-black text-ink" role="status">
            🎉 {ergebnis.label}
          </p>
        )}

        {ergebnis ? (
          <div className="flex flex-wrap justify-center gap-2">
            {gezogeneGruppe ? (
              <>
                <Button onClick={() => neueRunde({ art: 'person', gruppe: gezogeneGruppe })}>
                  Weiter: Person auslosen
                </Button>
                <Button
                  variant="ghost"
                  disabled={speichert}
                  onClick={() => onSieger({ group_id: gezogeneGruppe.id })}
                >
                  Gruppe als Sieger eintragen
                </Button>
              </>
            ) : (
              <Button disabled={speichert} onClick={() => onSieger({ user_id: ergebnis.id })}>
                Als Sieger eintragen
              </Button>
            )}
            <Button variant="ghost" onClick={drehen}>
              Nochmal drehen
            </Button>
          </div>
        ) : (
          <div className="text-center">
            <Button onClick={drehen} disabled={dreht || imRad.length === 0}>
              {dreht ? 'Dreht…' : 'Drehen'}
            </Button>
            {imRad.length === 0 && (
              <p className="mt-1 text-[11px] text-ink-mute">Mindestens eine Auswahl nötig.</p>
            )}
          </div>
        )}

        <fieldset disabled={dreht} className="space-y-1">
          <legend className="mb-1 text-[11px] font-bold text-ink-mute">
            Im Lostopf ({imRad.length}/{kandidaten.length})
            {!mitgliederRunde && ' — wer das Ziel erreicht hat, ist vorgewählt'}
          </legend>
          <div className="max-h-40 space-y-1 overflow-y-auto">
            {kandidaten.map((k) => (
              <label key={k.id} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={auswahl.has(k.id)}
                  onChange={() => umschalten(k.id)}
                  className="accent-accent"
                />
                {k.avatar && <span aria-hidden>{k.avatar}</span>}
                <span className="flex-1 truncate">{k.label}</span>
                {k.vorgewaehlt && !mitgliederRunde && (
                  <span className="text-[10px] font-bold text-accent">geschafft</span>
                )}
              </label>
            ))}
          </div>
        </fieldset>

        {mitgliederRunde && (
          <button
            onClick={() => neueRunde({ art: 'gruppe' })}
            disabled={dreht}
            className="text-xs font-bold text-accent hover:underline disabled:opacity-50"
          >
            ← Zurück zu den Gruppen
          </button>
        )}
      </div>
    </Modal>
  )
}
