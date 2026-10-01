# Achievements-Ausbau 2 — Design

Stand: 2026-10-01 · Branch `fix/achievements-and-bugfixes`

## 1. MM-Club (sichtbar, Leiter)

- Stufen 1k / 5k / 10k („Insane") über **gewertete MM** aller Aktivitäten
  (Kategorie-Faktor, ohne Admin-Handicap — wie Langstreckenguru).
- Keys `mm_club_1k|5k|10k`, Emojis ⚡ / 🚀 / 🤯 (tragbar).
- Der bestehende Tausender-Club (1000 rohe km) bleibt unverändert.

## 2. Zeit-Leitern je Kategorie

- Stufen 1 h → 10 h → 100 h → 1000 h, pro Kategorie (auch neu angelegte).
- Gezählt wird nur **echte Dauer** (`duration_min`); manuelle Einträge ohne
  Minuten zählen nicht. Strava-Importe speichern ab jetzt mindestens 1 min,
  sobald `moving_time > 0`.
- Fortschritt = Stunden / nächste Stufe (5 h auf dem Weg zu 10 h = halber Balken).
- Sichtbar erst ab der ersten Stunde (bzw. einer freigeschalteten Stufe).
- Keys `zeit_<category_id>_<h>h`; Kategoriename steht im Unlock-Kontext, damit
  Feed-Titel auch nach Umbenennung stabil bleiben. Nur 1000 h hat ein Emoji (⏳).

## 3. Monatssieger

- Pro abgeschlossenem Saisonmonat ab Challenge-Start (rückwirkend ab Juli 2026,
  Juli zählt ab dem 20.) bekommt die Person mit den meisten MM das Achievement
  `monatssieger_YYYY-MM` — Wertung wie Rennen-Tab inkl. Handicap. Gleichstand:
  alle Erstplatzierten.
- Fällig am Monatsersten 00:00 deutscher Zeit (= `unlocked_at` und Feed-Zeit),
  lazy + idempotent über `ensure_monatssieger` (Achievements-, Feed- und
  Vergleichs-Endpunkte).
- Emoji 🥇 (tragbar; 👑 ist schon der Wochenkönig). Nur gewonnene Monate werden
  angezeigt.

## 4. Neue Hidden-Achievements

| Key | Titel | Bedingung | Emoji |
|---|---|---|---|
| fruehaufsteher | Frühaufsteher | 5 Starts vor 06:00 | 🌅 |
| nachteule | Nachteule | 5 Starts ab 22:00 | 🦉 |
| allrounder | Allrounder | 4 Kategorien in einer ISO-Woche | 🎨 |
| doppelschicht | Doppelschicht | 2 Kategorien an einem Tag | 🔁 |
| everest | Everest | 8.848 Hm gesamt | 🗻 |
| gipfelsturm | Gipfelsturm | 2.000 Hm an einem Tag | ⛰️ |
| ueberholmanoever | Überholmanöver | an einem Tag 3 Leute in der Saisonwertung überholt | 🏎️ |
| comeback | Comeback | Aktivität nach ≥ 14 Tagen Pause | 🔙 |
| wochenendkrieger | Wochenendkrieger | 4 Wochenenden in Folge Sa + So aktiv | ⚔️ |
| schnapszahl | Schnapszahl | genau 11,11 / 22,22 / … / 99,99 km | 🎰 |
| marathon_am_stueck | Marathon am Stück | ≥ 42,2 km in einem Lauf | 🎽 |
| neujahr | Neujahrsvorsatz | Aktivität am 1. Januar | 🎆 |
| der_nimmt_alles_mit | Der nimmt alles mit | Aktivität < 1 min oder < 100 m | 🧹 |

Wie bisher maskiert, bis sie freigeschaltet sind.

## Frontend

- Neue `LadderCard` gruppiert Leitern über das API-Feld `ladder`
  (`ladder_title`, `stage`, `unit`). Monatssieger laufen als Emoji-Karte.
