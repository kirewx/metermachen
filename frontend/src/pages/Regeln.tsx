import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'

function Abschnitt({ titel, children }: { titel: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2 className="mb-2 text-sm font-black uppercase tracking-wider text-accent">{titel}</h2>
      <div className="space-y-2 text-sm text-ink-soft">{children}</div>
    </Card>
  )
}

export default function Regeln() {
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  const sidebetsAktiv = addons.some((a) => a.key === 'sidebets' && a.active)
  const aktive = categories.filter((c) => c.is_active)

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Abschnitt titel="Worum geht es">
        <p>
          MeterMachen ist unsere gemeinsame Jahres-Challenge. Das Ziel: Wer schafft es, innerhalb
          eines Jahres die meisten Meter anzusammeln? Ob Laufen, Radfahren, Schwimmen oder was
          auch immer dich bewegt. Damit unterschiedliche Sportarten fair gegeneinander antreten,
          zählen nicht die rohen Kilometer, sondern{' '}
          <strong className="text-ink">gewertete Kilometer (MM)</strong>.
        </p>
        <p>
          Wer am Ende vorn liegt, gewinnt einen{' '}
          <strong className="text-ink">phänomenalen Preis!!</strong>
        </p>
      </Abschnitt>

      <Abschnitt titel="Zeitraum">
        <p>
          Die Challenge startet am <strong className="text-ink">20.07.2026</strong> und läuft bis
          zum <strong className="text-ink">Stuttgartlauf 2027</strong>. Alles davor war Warm-up:
          Diese Kilometer zählen nicht für die Hauptwertung, bleiben aber im Archiv sichtbar,
          inklusive der Warm-up-Auszeichnungen.
        </p>
      </Abschnitt>

      <Abschnitt titel="Wertung">
        <p>
          Jede Sportart hat einen Faktor. Gewertete km (MM) = echte km × Faktor. Die Faktoren
          gleichen aus, dass ein Rad-Kilometer schneller gesammelt ist als ein Schwimm-Kilometer.
        </p>
        <table className="w-full text-left">
          <thead>
            <tr className="text-xs uppercase tracking-wider text-ink-mute">
              <th className="py-1 font-bold">Sportart</th>
              <th className="py-1 text-right font-bold">Faktor</th>
            </tr>
          </thead>
          <tbody>
            {aktive.map((c) => (
              <tr key={c.id} className="border-t border-line/30">
                <td className="flex items-center gap-2 py-1.5 font-bold text-ink">
                  <Icon name={c.icon} size={16} className="text-accent" />
                  {c.name}
                </td>
                <td className="py-1.5 text-right font-mono tabular-nums text-accent">
                  ×{c.factor}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-ink-mute">
          Die Tabelle ist live: Wenn ein Admin Faktoren anpasst, stimmt sie automatisch.
        </p>
      </Abschnitt>

      <Abschnitt titel="Einträge & Fairness">
        <p>
          Aktivitäten trägst du von Hand ein oder du verbindest Strava, dann kommen sie
          automatisch. Es gilt Ehrlichkeit vor Ehrgeiz:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Nur echte, selbst zurückgelegte Kilometer eintragen.</li>
          <li>Einträge zeitnah erfassen. Nachtragen ist ok, Fantasie-Kilometer nicht.</li>
          <li>Bei Strava-Import gilt, was Strava gemessen hat.</li>
          <li>Im Zweifel klärt die Gruppe. Der Spaß steht über der Platzierung.</li>
        </ul>
      </Abschnitt>

      {sidebetsAktiv && (
        <Abschnitt titel="Wetten (Kurzfassung)">
          <p>
            Im Wetten-Tab kannst du Punkte auf sportliche Duelle, Monats-Tipps, Ziel-, Streak-
            und Über/Unter-Wetten setzen. Punkte-Nachschub gibt es über Sport: +1 Punkt je 5
            gewertete km seit Challenge-Start. Punkte sind Spielwährung, kein Echtgeld.
          </p>
          <p className="text-xs text-ink-mute">
            Der Wettenbereich ist noch in Bearbeitung. Details können sich ändern.
          </p>
        </Abschnitt>
      )}
    </div>
  )
}
