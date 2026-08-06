import type { Achse } from './achsen'

const CX = 170
const CY = 130
const R = 92
const RINGE = [0.25, 0.5, 0.75, 1]

/** Einheitsvektor der Achse i: erste Achse zeigt nach oben, dann im Uhrzeigersinn. */
function richtung(i: number, n: number): [number, number] {
  const winkel = (-90 + (360 / n) * i) * (Math.PI / 180)
  return [Math.cos(winkel), Math.sin(winkel)]
}

function punkte(anteile: number[], skala = 1): string {
  return anteile
    .map((a, i) => {
      const [ux, uy] = richtung(i, anteile.length)
      const r = R * skala * a
      return `${(CX + ux * r).toFixed(1)},${(CY + uy * r).toFixed(1)}`
    })
    .join(' ')
}

function wertText(a: Achse): string {
  return `${Math.round(a.wert).toLocaleString('de-DE')} ${a.einheit}`
}

type Props = {
  name: string
  achsen: Achse[]
  /** Optionale zweite Kontur (gestrichelt) zum Vergleich. */
  vergleich?: { name: string; achsen: Achse[] } | null
}

/**
 * Spinnennetz über die fünf Profil-Achsen. 100 % = Bestwert der Gruppe auf
 * dieser Achse, damit sich Profile direkt vergleichen lassen.
 */
export default function Spinnennetz({ name, achsen, vergleich = null }: Props) {
  const n = achsen.length
  const eigene = achsen.map((a) => a.anteil)
  const fremde = vergleich?.achsen.map((a) => a.anteil) ?? null

  return (
    <div>
      <svg
        viewBox="0 0 340 250"
        className="w-full"
        role="img"
        aria-label={`Sportprofil von ${name}: ${achsen
          .map((a) => `${a.label} ${Math.round(a.anteil * 100)} Prozent`)
          .join(', ')}`}
      >
        {RINGE.map((f) => (
          <polygon
            key={f}
            points={punkte(achsen.map(() => f))}
            fill="none"
            stroke="var(--t-line)"
            strokeOpacity={f === 1 ? 0.9 : 0.45}
          />
        ))}
        {achsen.map((a, i) => {
          const [ux, uy] = richtung(i, n)
          return (
            <line
              key={a.key}
              x1={CX}
              y1={CY}
              x2={CX + ux * R}
              y2={CY + uy * R}
              stroke="var(--t-line)"
              strokeOpacity={0.6}
            />
          )
        })}

        {fremde && (
          <polygon
            points={punkte(fremde)}
            fill="var(--t-ink)"
            fillOpacity={0.07}
            stroke="var(--t-ink)"
            strokeOpacity={0.55}
            strokeWidth={1.5}
            strokeDasharray="4 3"
          />
        )}

        <polygon
          points={punkte(eigene)}
          fill="var(--t-accent)"
          fillOpacity={0.22}
          stroke="var(--t-accent)"
          strokeWidth={2}
        />
        {achsen.map((a, i) => {
          const [ux, uy] = richtung(i, n)
          return (
            <circle
              key={a.key}
              cx={CX + ux * R * a.anteil}
              cy={CY + uy * R * a.anteil}
              r={3}
              fill="var(--t-accent)"
            />
          )
        })}

        {achsen.map((a, i) => {
          const [ux, uy] = richtung(i, n)
          const x = CX + ux * (R + 20)
          const y = CY + uy * (R + 20)
          return (
            <text
              key={a.key}
              x={x}
              y={y}
              dy={uy < -0.3 ? -2 : uy > 0.3 ? 12 : 4}
              textAnchor={ux > 0.25 ? 'start' : ux < -0.25 ? 'end' : 'middle'}
              className="fill-ink-soft font-mono text-[10px] font-bold uppercase tracking-wider"
            >
              {a.label}
              <tspan className="fill-ink-mute"> {Math.round(a.anteil * 100)}</tspan>
            </text>
          )
        })}
      </svg>

      <ul className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
        {achsen.map((a, i) => (
          <li key={a.key} className="flex items-center gap-1.5">
            <span
              className="inline-block h-2 w-2 shrink-0 rounded-full"
              style={{ background: a.color }}
            />
            <span className="truncate text-ink-soft">{a.label}</span>
            <span className="ml-auto shrink-0 font-mono tabular-nums text-ink-mute">
              {wertText(a)}
              {fremde && vergleich ? (
                <span className="ml-1 text-ink-tech">/ {wertText(vergleich.achsen[i])}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
