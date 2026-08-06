# Höhenmeter-Vergleich — Design

**Stand:** 2026-08-06
**Status:** freigegeben, in Umsetzung

## Ziel

Eine vierte Ansicht im Vergleichs-Tab: Höhenmeter, gezählt ab Beginn der Challenge,
nach oben wachsend, jeder Monat in eigener Farbe. Die Gruppe umfasst rund 30 Personen,
die Ansicht wird mobile first entwickelt — auf einem Handydisplay muss die gesamte
Y-Achse ohne Scrollen sichtbar sein.

## Ausgangslage im Code

- `Activity.elevation_m` existiert bereits (`models.py`), gefüllt wird es aber nur vom
  Strava-Import (`services/strava.py`). `ActivityCreate`/`ActivityPatch` kennen kein
  Höhenmeter-Feld, das Erfassen-Formular auch nicht.
- Die Comparison-API liefert pro Person `segments` und `cumulative` mit
  `scaled_km`/`real_km` — Höhenmeter tauchen dort nicht auf.
- Der Vergleichs-Tab (`pages/Vergleich.tsx`) hat drei Ansichten (Rennen, Verlauf,
  Sport-Mix) plus MM/km-Umschalter. Personenfarben kommen aus `userColor.ts`
  (Palette mit acht Farben).

## Entscheidungen

| Frage | Entscheidung |
| --- | --- |
| Datenquelle | Optionales Höhenmeter-Feld beim Erfassen ergänzen, damit nicht nur Strava-Nutzende Werte haben |
| Darstellung | Umschaltbar zwischen Säulen-Panorama und Höhen-Verlauf |
| 30 Personen | Panorama zeigt alle als schmale Säulen; Presets und Personenliste engen die Auswahl ein |
| Referenzlinien | Feste Bergliste, eingeblendet nur wenn sie in den sichtbaren Bereich fällt |
| Monatsfarben | Farbverlauf entlang der Monatsposition seit Challenge-Start (kühl → warm) |
| Verlauf-Standard | Deine Linie plus graues Band zwischen Median und Spitzenreiter |

## 1. Einbettung

Vierter Eintrag in der Ansichtsleiste von `Vergleich.tsx`: **Rennen · Verlauf ·
Sport-Mix · Höhenmeter** (Icon `berg`). Der MM/km-Umschalter wird ausgeblendet,
solange die Höhenmeter-Ansicht aktiv ist — Höhenmeter sind roh, ohne `km_factor`
und ohne Kategorie-Faktor. Im Archiv (Warm-up) gibt es die Ansicht nicht.

Neue Dateien unter `frontend/src/components/comparison/`:

- `Hoehenmeter.tsx` — Rahmen: Unterumschalter Säulen ↔ Verlauf, Auswahl-Leiste, leerer Zustand
- `HoehenSaeulen.tsx` — das Panorama
- `HoehenVerlauf.tsx` — die Kurven
- `monatsFarbe.ts` — Monatspalette, Monatsachse, Bergreferenzen

## 2. Datenweg

### Backend

- `ActivityCreate` und `ActivityPatch` bekommen `elevation_m: float | None` mit
  `ge=0`. `patch_activity` muss `elevation_m` in die Liste der Felder aufnehmen,
  die sich explizit auf `null` zurücksetzen lassen.
- Der Strava-Import bleibt unverändert: er legt nur neue Aktivitäten an und
  überschreibt bestehende nie, manuell korrigierte Werte bleiben also erhalten.
- `ComparisonUser` bekommt `total_elevation_m: float` und
  `elevation_by_month: list[MonthElevation]` mit `{month: "2026-07", meters: 1240.0}`.
- `CumulativePoint` bekommt ein zusätzliches Feld `elevation_m: float` (kumuliert bis
  zu diesem Punkt) — keine zweite Zeitreihe im Payload.
- `ComparisonOut` bekommt `elevation_months: list[str]` als gemeinsame Monatsachse ab
  Challenge-Start, damit alle Personen dieselbe Farbzuordnung haben. Die Achse reicht
  vom Startmonat bis zum letzten Monat mit Daten (mindestens bis zum aktuellen Monat,
  sofern er im Saisonfenster liegt).
- Zeitfenster und Startdatum: exakt die bestehende Logik aus `compute_comparison`
  (`season_window` plus `start_date`), also „ab Beginn der Challenge" ohne Sonderweg.

### Frontend

Optionales Feld „Höhenmeter" im Details-Bereich der `SchnellwahlCard`, neben Dauer
und Startzeit. Leere Eingabe wird als `null` gesendet.

## 3. Panorama (Säulen)

Eine gestapelte Säule je ausgewählter Person, absteigend nach Höhenmetern sortiert.
Die Segmente sind die Monate ab Challenge-Start, eingefärbt entlang der Monatsposition.

- Die Y-Achse skaliert immer auf den höchsten sichtbaren Wert, damit das Diagramm
  ohne Scrollen aufs Display passt.
- Bergreferenzen (Zugspitze 2.962, Mont Blanc 4.808, Kilimandscharo 5.895,
  Everest 8.848) liegen als gestrichelte Linien im Diagramm, aber nur, wenn sie
  unterhalb des Höchstwerts liegen.
- Die Säulenbreite ist adaptiv, ohne eigenen Umschalter: bei vielen Personen schmale
  Säulen ohne Namen, die eigene hervorgehoben und der Rest gedimmt; bei wenigen
  breite Säulen mit Name und Zahl.
- Tippen auf eine Säule öffnet das bestehende `PersonDetail`, das Höhenmeter je
  Aktivität bereits anzeigt.

## 4. Auswahl

Eine gemeinsame Auswahl für beide Unteransichten mit drei Presets:

- **Alle** — das ganze Feld
- **Nachbarschaft** — Spitzenreiter plus zwei Plätze über und unter dir
- **Nur ich**

Darunter eine aufklappbare Liste, in der einzelne Personen an- und abgewählt werden.
Die eigene Person ermittelt sich über `api.me()`.

Beide Unteransichten reagieren adaptiv auf dieselbe Auswahl:

- **Verlauf bei mehr als acht Ausgewählten:** graues Band zwischen Median und
  Spitzenreiter plus die eigene Linie. Das ist der Zustand beim Öffnen.
- **Verlauf bei bis zu acht:** eine Linie je Person in ihrer Personenfarbe, das Band
  bleibt dezent im Hintergrund. Die Acht entspricht der Palettengröße in `userColor.ts`.

## 5. Randfälle

- Niemand hat Höhenmeter: leerer Zustand mit Hinweis auf Strava und das neue Feld.
- Personen ohne Höhenmeter bleiben mit 0 im Bild (Strich am Boden), damit keine
  Lücke im Feld entsteht.
- Höchstwert 0: feste Ersatzskala statt Division durch null.
- Negative Eingaben fängt die `ge=0`-Validierung im Schema ab.

## 6. Tests

**Backend**

- Monatsbuckets und kumulierte Höhenmeter zählen ab Challenge-Start.
- `elevation_m` wird über Create und Patch persistiert und lässt sich leeren.
- Der Strava-Import überschreibt einen korrigierten Wert nicht.

**Frontend**

- Panorama sortiert absteigend.
- Die Y-Skala richtet sich am Maximum aus.
- Eine Bergreferenz oberhalb des Maximums wird nicht gerendert.
- Die Presets setzen die richtige Personenmenge.
- Der Verlauf schaltet oberhalb von acht Ausgewählten auf Band plus eigene Linie.
