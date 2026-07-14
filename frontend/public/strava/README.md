# Strava-Marken-Assets

Der „Connect with Strava"-Button ist ein **offizielles Marken-Asset** und darf laut
Strava-Brand-Guidelines nicht selbst nachgebaut oder verändert werden.

## Enthaltene Dateien (offizielle, orange Variante)

- `connect-with-strava-orange.png` — 237 × 48 px (1x)
- `connect-with-strava-orange@2x.png` — 474 × 96 px (2x, Retina)

Die App bindet diese automatisch ein (`components/ui/StravaConnectButton.tsx`,
`srcset` für 1x/2x). Fehlt die Datei, zeigt der Button einen orangefarbenen
Text-Fallback.

Quelle: Brand-Assets-Paket unter https://developers.strava.com/guidelines/
Die weiße Variante (für dunkle Hintergründe) liegt bewusst nicht im Repo — wir
nutzen die orange, weil sie auf hell und dunkel funktioniert.

Vorgaben (Guidelines): Button-Höhe 48 px, orange oder weiß, Logo nie verändern,
muss auf `https://www.strava.com/oauth/authorize` verlinken (macht bei uns
`/api/strava/connect` per Redirect).
