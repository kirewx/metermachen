import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'

const datumKurz = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
}

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
  const togetherAktiv = addons.some((a) => a.key === 'together' && a.active)
  const aktive = categories.filter((c) => c.is_active)
  const hmAb = aktive
    .flatMap((c) => c.elevation_changes ?? [])
    .filter((e) => e.counts_elevation)
    .map((e) => e.valid_from)
    .sort()[0]
  const ohneHm = aktive.filter((c) => c.counts_elevation === false)

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Abschnitt titel="Worum geht es">
        <p>
          MeterMachen ist unsere gemeinsame Saison. Das Ziel: Wer schafft es, innerhalb
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
          Die Saison startet am <strong className="text-ink">20.07.2026</strong> und läuft bis
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
        {hmAb && (
          <p>
            Ab dem <strong className="text-ink">{datumKurz(hmAb)}</strong> zählen auch
            Höhenmeter: <strong className="text-ink">100 hm = 1 km</strong>, danach greift der
            Faktor. Also MM = (km + hm / 100) × Faktor; 100 hm beim Laufen bringen 4 MM.
            {ohneHm.length > 0 && <> Ausgenommen: {ohneHm.map((c) => c.name).join(', ')}.</>}{' '}
            Wandern hat dafür einen niedrigeren Faktor, weil die Höhenmeter dort jetzt extra
            zählen.
          </p>
        )}
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
                  {c.pending_changes.length > 0 && (
                    <div className="text-xs text-ink-mute">
                      ab {datumKurz(c.pending_changes[0].valid_from)}: ×
                      {c.pending_changes[0].factor}
                    </div>
                  )}
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

      {togetherAktiv && (
        <Abschnitt titel="Zusammen trainieren">
          <p>
            Wart ihr gemeinsam unterwegs, erkennt MeterMachen das an Zeit und Route eurer
            Strava-Aktivitäten. Überlappen sich die Routen zu mindestens{' '}
            <strong className="text-ink">50 %</strong> auf mindestens{' '}
            <strong className="text-ink">2 km</strong>, gilt die Einheit direkt als gemeinsam.
            Ab 30 % Überlappung oder 2 km gemeinsamer Strecke bekommt ihr einen Vorschlag im
            Feed, den beide bestätigen. Unbeantwortete Vorschläge verfallen nach 14 Tagen.
          </p>
          <p>
            Ohne Strava kannst du im Formular unter „Mit wem?“ Leute taggen. Sie wählen dann
            ihre eigene Aktivität dazu oder legen eine neue an.
          </p>
          <p>
            Falsch erkannt? Tipp an der Aktivität auf die Avatare und dann auf{' '}
            <strong className="text-ink">„War ich nicht dabei“</strong>. Mit diesen Leuten
            wird die Aktivität nicht wieder vorgeschlagen, mit anderen schon. Vertan? „Doch
            dabei“ macht es rückgängig.
          </p>
          <p>
            Hast du dieselbe Einheit doppelt eingetragen (z. B. von Hand und über Strava) und
            löschst die verknüpfte, verlässt du die gemeinsame Einheit. Lass dich dann einfach
            neu taggen.
          </p>
          <p className="text-xs text-ink-mute">
            Gemeinsames Training ändert nichts an MM oder Punkten. Es zählt nur für den Feed,
            die Trainingspartner im Profil und eigene Achievements.
          </p>
        </Abschnitt>
      )}

      {sidebetsAktiv && (
        <Abschnitt titel="Wetten (Kurzfassung)">
          <p>
            Im Wetten-Tab kannst du Punkte auf sportliche Duelle, Monats-Tipps, Ziel-, Streak-
            und Über/Unter-Wetten setzen. Punkte-Nachschub gibt es über Sport: +1 Punkt je 5
            gewertete km seit Saison-Start. Punkte sind Spielwährung, kein Echtgeld.
          </p>
          <p className="text-xs text-ink-mute">
            Der Wettenbereich ist noch in Bearbeitung. Details können sich ändern.
          </p>
        </Abschnitt>
      )}
    </div>
  )
}
