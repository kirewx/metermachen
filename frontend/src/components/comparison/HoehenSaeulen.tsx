import type { ComparisonUser } from '../../api/client'
import { BREIT_BIS, nachHoehe } from './hoehenAuswahl'
import { formatHm, monatsFarbe, monatsLabel, sichtbareBerge, skalaMax } from './monatsFarbe'

/**
 * Panorama: eine gestapelte Säule je Person, nach Höhenmetern absteigend sortiert,
 * Segmente sind die Monate ab Challenge-Start.
 *
 * Die Y-Achse skaliert immer auf den höchsten sichtbaren Wert, damit alles ohne
 * Scrollen aufs Handydisplay passt. Die Säulenbreite ergibt sich allein aus der
 * Anzahl der Ausgewählten — bei wenigen Personen entsteht daraus von selbst die
 * breite Ansicht mit Namen und Zahlen, bei vielen ein schmales Gebirgspanorama.
 */
export default function HoehenSaeulen({
  users,
  months,
  meId,
  onSelect,
}: {
  users: ComparisonUser[]
  months: string[]
  meId: number | null
  onSelect: (user: ComparisonUser) => void
}) {
  const sortiert = nachHoehe(users)
  const max = skalaMax(sortiert.map((u) => u.total_elevation_m))
  const breit = sortiert.length <= BREIT_BIS
  // Oben 8 % Luft lassen, damit die Zahl über der höchsten Säule Platz hat.
  const anteil = (meter: number) => (meter / max) * 92
  const ich = sortiert.find((u) => u.user_id === meId)
  const meinPlatz = ich ? sortiert.indexOf(ich) + 1 : null
  const monateMitDaten = months.filter((m) =>
    sortiert.some((u) => u.elevation_by_month.some((e) => e.month === m && e.meters > 0)),
  )

  return (
    <div className="space-y-3">
      <div className="relative h-64 sm:h-80">
        {sichtbareBerge(max).map((berg) => (
          <div
            key={berg.name}
            className="pointer-events-none absolute inset-x-0 flex items-center gap-1"
            style={{ bottom: `${anteil(berg.meters)}%` }}
          >
            <span className="flex-1 border-t border-dashed border-line" />
            <span className="shrink-0 text-[9px] text-ink-mute">
              {berg.name} {formatHm(berg.meters)}
            </span>
          </div>
        ))}
        <div className="absolute inset-0 flex items-end gap-px sm:gap-1">
          {sortiert.map((u) => {
            const gesamt = u.total_elevation_m
            const eigen = u.user_id === meId
            return (
              <button
                key={u.user_id}
                type="button"
                onClick={() => onSelect(u)}
                aria-label={`Details zu ${u.display_name}`}
                className={`relative flex h-full min-w-0 flex-1 flex-col justify-end transition ${
                  eigen || breit ? '' : 'opacity-50 hover:opacity-100'
                }`}
              >
                {breit && (
                  <span
                    className="pointer-events-none absolute inset-x-0 text-center font-mono text-[10px] font-bold tabular-nums text-ink"
                    style={{ bottom: `${anteil(gesamt)}%` }}
                  >
                    {formatHm(gesamt)}
                  </span>
                )}
                <span
                  className={`mx-auto flex w-full max-w-[52px] flex-col-reverse overflow-hidden rounded-t ${
                    eigen ? 'outline outline-1 outline-ink' : ''
                  }`}
                  style={{ height: gesamt > 0 ? `${anteil(gesamt)}%` : 2 }}
                >
                  {gesamt > 0 ? (
                    u.elevation_by_month.map((e) => (
                      <span
                        key={e.month}
                        title={`${monatsLabel(e.month)}: ${formatHm(e.meters)} hm`}
                        style={{
                          height: `${(e.meters / gesamt) * 100}%`,
                          background: monatsFarbe(e.month, months),
                        }}
                      />
                    ))
                  ) : (
                    <span className="h-full bg-line" />
                  )}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {breit ? (
        <div className="flex gap-px sm:gap-1">
          {sortiert.map((u) => (
            <span
              key={u.user_id}
              className={`min-w-0 flex-1 truncate text-center text-[10px] ${
                u.user_id === meId ? 'font-bold text-ink' : 'text-ink-mute'
              }`}
            >
              {u.display_name}
            </span>
          ))}
        </div>
      ) : (
        ich && (
          <p className="text-center text-xs text-ink-mute">
            <span className="font-bold text-ink">Du</span> · Platz {meinPlatz} von{' '}
            {sortiert.length} · {formatHm(ich.total_elevation_m)} hm
          </p>
        )
      )}

      <ul className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-[10px] text-ink-soft">
        {monateMitDaten.map((m) => (
          <li key={m} className="flex items-center gap-1">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: monatsFarbe(m, months) }}
            />
            {monatsLabel(m)}
          </li>
        ))}
      </ul>
    </div>
  )
}
