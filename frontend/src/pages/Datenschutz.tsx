import { Link } from 'react-router-dom'

/**
 * Fokussierte Datenschutz-Seite. Beschreibt v. a. den Umgang mit Strava-Daten
 * (Anforderung des Strava-API-Reviews) und ist ohne Login erreichbar, damit sie
 * vor der OAuth-Verbindung und für den Strava-Reviewer zugänglich ist.
 */
export default function Datenschutz() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4 text-sm leading-relaxed text-ink-soft">
      <div>
        <h1 className="text-xl font-black tracking-wide text-ink">Datenschutz</h1>
        <p className="mt-1 text-xs text-ink-mute">
          MeterMachen — private Fitness-Challenge im Freundeskreis (nur per Einladung)
        </p>
      </div>

      <section className="space-y-2">
        <h2 className="font-bold text-ink">Verantwortlicher</h2>
        <p>
          Erik Wimmer ·{' '}
          <a href="mailto:erikwimmer15@gmail.com" className="font-bold text-accent hover:underline">
            erikwimmer15@gmail.com
          </a>
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-bold text-ink">Welche Daten wir verarbeiten</h2>
        <p>
          Für dein Konto speichern wir Benutzername, Anzeigename, gewähltes Avatar-Bild
          sowie deine selbst oder per Strava erfassten Aktivitäten. Zur Anmeldung wird
          ein technisch notwendiges Session-Cookie gesetzt.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-bold text-ink">Strava-Verbindung</h2>
        <p>
          Wenn du dein Strava-Konto verbindest, autorisierst du uns über das offizielle
          OAuth-Verfahren von Strava. Wir rufen daraufhin ausschließlich folgende Daten
          deiner Aktivitäten ab und speichern sie:
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Sportart, Distanz, Höhenmeter, Dauer, Datum und Titel der Aktivität</li>
          <li>deine Strava-Athleten-ID sowie die Zugriffs-/Erneuerungs-Token (Access/Refresh Token)</li>
        </ul>
        <p>
          Die Token brauchen wir, um deine neuen Aktivitäten für die Challenge abzurufen.
          Sie werden auf unserem Server gespeichert und nicht an Dritte weitergegeben.
        </p>
        <p>
          <span className="font-bold text-ink">Zweck:</span> Anzeige und Wertung deiner
          Aktivitäten im gemeinsamen Gruppen-Ranking. Wir geben deine Strava-Daten
          <span className="font-bold text-ink"> nicht an Dritte weiter</span> und nutzen
          sie insbesondere <span className="font-bold text-ink">nicht für KI-/Machine-Learning-Tools</span>.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-bold text-ink">Speicherort</h2>
        <p>
          Alle Daten liegen auf einem Server in Deutschland (netcup, Nürnberg). Es findet
          keine Übermittlung in Drittländer statt.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-bold text-ink">Verbindung trennen &amp; Daten löschen</h2>
        <p>
          Du kannst die Strava-Verbindung jederzeit in deinem Profil über
          „Strava trennen" aufheben. Dabei werden deine Strava-Token sofort und
          vollständig aus unserem System gelöscht; wir rufen danach keine weiteren
          Aktivitäten mehr ab. Bereits importierte Aktivitäten kannst du einzeln in
          „Meine Aktivitäten" löschen. Für die Löschung deines gesamten Kontos wende
          dich an den oben genannten Kontakt.
        </p>
        <p>
          Unabhängig davon kannst du den Zugriff auch direkt bei Strava unter{' '}
          <a
            href="https://www.strava.com/settings/apps"
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-accent hover:underline"
          >
            strava.com/settings/apps
          </a>{' '}
          widerrufen.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="font-bold text-ink">Deine Rechte</h2>
        <p>
          Du hast das Recht auf Auskunft, Berichtigung, Löschung und Einschränkung der
          Verarbeitung deiner Daten. Wende dich dazu an den oben genannten Kontakt.
        </p>
      </section>

      <p className="border-t border-line/40 pt-4 text-xs text-ink-mute">
        Diese Anwendung nutzt die Strava-API, ist aber kein offizielles Angebot von
        Strava und wird nicht von Strava unterstützt. Powered by Strava.
      </p>

      <p className="text-xs">
        <Link to="/" className="text-accent hover:underline">
          ← Zurück
        </Link>
      </p>
    </div>
  )
}
