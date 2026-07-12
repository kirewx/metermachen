# Design: Countdown/Warm-up-Phase & Sidebet-System

**Datum:** 2026-07-12
**Status:** Vom User freigegeben (Brainstorming-Session 12.07.2026)

## Ausgangslage

Die App läuft im Testmodus, die eigentliche Challenge beginnt am **20.07.2026 00:00 Uhr deutscher Zeit** (Europe/Berlin, im Juli = UTC+2). Bis dahin gesammelte Kilometer sollen erhalten bleiben, aber ab Challenge-Start nicht mehr ins Ranking einfließen. Zusätzlich kommt ein Sidebet-System mit Punktwährung, damit sich auch Mitspieler challengen können, die nicht um die KM-Krone kämpfen.

**Auslieferung:**
- Countdown/Warm-up: direkt auf `main` (Auto-Deploy auf VPS).
- Sidebet-System: als **eigener PR** (Branch `feature/sidebets`), dazu eine **Review-HTML** mit Zusammenfassung, damit Rick vor dem Merge prüfen kann.

---

## Teil 1: Countdown & Warm-up-Phase

### Konzept

- `Season` bekommt ein neues Feld `start_date: date | None` (für 2026: `2026-07-20`). `None` = Season läuft ab 1.1. (Verhalten wie bisher).
- **Vor dem Start** (heute < start_date): App funktioniert komplett normal — Ranking zeigt alle KM (Testphase, Leute sollen die App kennenlernen). Oben erscheint ein **Countdown-Banner**: „Challenge startet in 7 T 13:42:05" (live tickend, Ziel `2026-07-20T00:00:00+02:00`).
- **Ab dem Start** (heute ≥ start_date): Banner verschwindet. Der Vergleich (`/api/comparison/{year}`) zählt nur noch Aktivitäten mit `date >= start_date`. Die Warm-up-Aktivitäten bleiben in der DB und unter „Meine Aktivitäten" sichtbar, fließen aber nie mehr ins Ranking ein.

### Archiv

Neue Ansicht „Archiv" (Navigation, erst ab Challenge-Start sichtbar):
- Warm-up-Endstand: Tabelle aller Teilnehmer mit gewerteten KM aus der Warm-up-Phase (Aktivitäten mit `date < start_date` im Season-Jahr), sortiert nach KM.
- Anzeige der Warm-up-Achievements (wer hat welches gewonnen).
- Backend: `GET /api/comparison/{year}?phase=warmup` liefert dieselbe Struktur wie der normale Vergleich, nur mit Datumsfilter `< start_date`.

### Warm-up-Achievements

Vier einmalige, **relative** Auszeichnungen — werden erst ab Challenge-Start vergeben (vorher als „ausstehend" mit aktuellem Zwischenstand sichtbar), danach stehen sie fest, weil keine Aktivität vor dem Stichtag mehr dazukommen kann:

| Key | Titel | Kriterium |
|---|---|---|
| `guter_start` | Guter Start | Meiste gewertete KM gesamt im Warm-up (Anzeige mit Zahl, z.B. „123 km") |
| `warmup_laeufer` | Warm-up-Läufer | Meiste Lauf-KM (roh) im Warm-up |
| `warmup_radler` | Warm-up-Radler | Meiste Rad-KM (roh) im Warm-up |
| `warmup_schwimmer` | Warm-up-Schwimmer | Meiste Schwimm-KM (roh) im Warm-up |

- Sport-Zuordnung über das bestehende `bucket_for_category`.
- Bei Gleichstand gewinnen alle Punktgleichen.
- Gibt es in einem Bucket keine einzige Aktivität, wird das Achievement nicht vergeben.
- Die regulären Achievements (Marathon, Ironman, …) zählen weiterhin über **alle** Aktivitäten inkl. Warm-up — sie sind persönliche Lebensleistungen, kein Challenge-Ranking.

### Admin-Handicap (global)

- `User` bekommt `km_factor: float = 1.0`, editierbar in der Admin-Mitgliederverwaltung (z.B. `0.33` oder `3.0`).
- Wirkt im **Challenge-Ranking** (Vergleich): gewertete KM = `distance_km × category.factor × user.km_factor`.
- Wirkt **nicht** auf: persönliche Achievements, Warm-up-Achievements (roh bzw. nur Kategorie-Faktor), „Meine Aktivitäten"-Anzeige.
- Im Ranking wird bei `km_factor ≠ 1` ein kleiner Hinweis am Nutzer angezeigt (z.B. „×3"), damit das Ranking transparent bleibt.

---

## Teil 2: Sidebet-System

### Punkte-Ökonomie

- Jeder User startet mit **100 Punkten** (Startgutschrift als erste Transaktion).
- **Nachschub durch Sport:** +1 Punkt je 5 gewertete KM (Kategorie-Faktor × Admin-Handicap), nur Aktivitäten ab Challenge-Start. Umsetzung: Einkommen wird lazy berechnet als `floor(gewertete_km_seit_start / 5)` und mit bereits gutgeschriebenem Einkommen abgeglichen — kein Cron nötig.
- Kontostand = Summe aller Transaktionen. Einsätze sind auf den aktuellen Kontostand begrenzt, Konto kann nie unter 0 fallen.
- **Punkte-Ranking:** eigene Rangliste nach Kontostand — die zweite Meisterschaft neben den KM.

### Wettarten (alle vier in v1)

Gemeinsame Regeln:
- Wetten laufen über einen Zeitraum `period_start`–`period_end`; `period_start` muss in der Zukunft liegen (Beitritt/Dagegenhalten bis `period_start`).
- Gewertet werden KM mit Kategorie-Faktor, **ohne** Admin-Handicap (Handicaps sind in Wetten Verhandlungssache, siehe Wett-Faktoren).
- Automatische Auflösung: beim ersten API-Zugriff nach `period_end` wird abgerechnet (lazy, kein Cron). Bei Gleichstand gehen alle Einsätze zurück.
- Wetten mit Zeitraum komplett vor Challenge-Start sind nicht möglich; das System startet mit der Challenge.

**1. Duell (1 gg. 1) mit Handicap**
- „Ich mache im Zeitraum X mehr KM als Person Y."
- Herausforderer legt Einsatz und optional Handicap fest: **KM-Vorsprung** (+N km für den Gegner) und/oder **Faktor pro Person** (z.B. Gegner-KM ×3). Gegner nimmt an oder lehnt ab; Einsatz wird bei Annahme bei beiden reserviert.
- Gewinner bekommt den Pott (2× Einsatz).

**2. Monats-Tipp**
- Pro Kalendermonat eine automatische Tipprunde (wird beim ersten Zugriff im Monat erzeugt): „Wer macht diesen Monat die meisten gewerteten KM?"
- Tippen bis zum 5. des Monats, fester Einsatz 10 Punkte, ein Tipp pro Person.
- Monatsende: Pott geht zu gleichen Teilen an alle, die den Sieger richtig getippt haben. Liegt niemand richtig, wandert der Pott als Jackpot in den Folgemonat.
- Erste Tipprunde ist der erste volle Challenge-Monat (**August 2026**) — für Juli läge der Tippschluss (5.7.) vor dem Challenge-Start.

**3. Ziel-Wette / Streak-Wette (gegen sich selbst)**
- „Ich wette N Punkte, dass ich im Zeitraum X mindestens Z km mache" **oder** „… an K Tagen in Folge Sport mache (≥1 km roh pro Tag)".
- Andere können bis `period_start` mit eigenem Einsatz (bis max. N gesamt über alle Gegenhalter) **dagegenhalten**.
- Ziel erreicht → Wettende(r) bekommt alle Gegen-Einsätze. Ziel verfehlt → Gegenhalter teilen den Einsatz des Wettenden proportional zu ihrem Einsatz. Ohne Gegenhalter verfällt die Wette (Einsatz zurück).

**4. Über/Unter-Gruppenwette**
- Ersteller definiert: „Schafft die Gruppe zusammen ≥ Z km im Zeitraum X?" plus festen Einsatz.
- Jeder setzt bis `period_start` auf **Über** oder **Unter**.
- Ende: Verlierer-Seite zahlt, Pott geht proportional zum Einsatz an die Gewinner-Seite. Ist eine Seite leer, gibt es die Einsätze zurück.

### Wett-Achievements

| Key | Titel | Kriterium |
|---|---|---|
| `zocker` | Zocker | 10 Wetten abgeschlossen (egal ob gewonnen) |
| `david` | David gegen Goliath | Duell gegen jemanden gewonnen, der beim Wettende im KM-Ranking über dir stand |
| `high_roller` | High Roller | Wette mit Einsatz ≥ 50 Punkten gewonnen |
| `orakel` | Orakel | 3 Monats-Tipps richtig |

### Datenmodell (neu)

```
PointTransaction: id, user_id, amount (+/-), reason ("start"|"einkommen"|"einsatz"|"gewinn"|"rueckzahlung"), bet_id?, created_at
Bet:              id, type ("duell"|"monats_tipp"|"ziel"|"streak"|"ueber_unter"),
                  creator_id, title/params_json (Ziel-KM, Streak-Tage, Gruppenziel, Handicaps, Monat, Jackpot),
                  stake, period_start, period_end,
                  status ("offen"|"laufend"|"entschieden"|"abgelehnt"|"abgebrochen"),
                  created_at, resolved_at?
BetParticipant:   id, bet_id, user_id, role ("ersteller"|"gegner"|"tipper"|"gegenhalter"),
                  choice_json (getippter User, über/unter, …), stake, payout?
User:             + km_factor (Teil 1)
Season:           + start_date (Teil 1)
```

Migration über das bestehende Muster in `db.py` (`ALTER TABLE` für neue Spalten, `create_all` für neue Tabellen).

### API (neu)

```
GET  /api/bets                  – alle Wetten (offen/laufend/Historie), löst fällige Wetten lazy auf
POST /api/bets                  – Wette erstellen (Typ + Parameter)
POST /api/bets/{id}/respond     – annehmen/ablehnen (Duell), tippen (Monats-Tipp), dagegenhalten (Ziel), über/unter setzen
POST /api/bets/{id}/cancel      – Ersteller storniert vor period_start
GET  /api/points                – eigener Kontostand + Transaktionshistorie
GET  /api/points/ranking        – Punkte-Rangliste aller aktiven User
```

### Frontend (neu)

- **Countdown-Banner** (App-weit, vor Challenge-Start).
- **Archiv-Seite** (ab Challenge-Start): Warm-up-Endstand + Warm-up-Achievements.
- **Wetten-Seite**: Kontostand prominent, Punkte-Ranking, offene Herausforderungen (annehmen/ablehnen), laufende Wetten mit Live-Zwischenstand, Wette-erstellen-Dialog (Typ-Auswahl), Historie.
- **Admin**: `km_factor` pro Mitglied editierbar.
- Design im bestehenden Neon-Stil (siehe `2026-06-13-frontend-redesign-neon-design.md`).

---

## Fehlerbehandlung & Randfälle

- **Zeitzone:** Stichtag ist ein reines Datum (`start_date`); Aktivitäten tragen lokale Datumsangaben — kein UTC-Versatz-Problem. Der tickende Countdown im Frontend zielt auf `2026-07-20T00:00:00+02:00` (Juli = CEST, fester Offset ok).
- **Nachträglich eingetragene Aktivitäten** mit Datum vor dem 20.07. landen automatisch im Warm-up (Datumsfilter, kein Statusfeld) — Warm-up-Achievements werden deshalb bei jedem Abruf neu berechnet, nicht eingefroren gespeichert.
- **Gelöschte/deaktivierte User** in laufenden Wetten: Wette wird abgebrochen, Einsätze zurück.
- **Aktivität nachträglich geändert/gelöscht** während laufender Wette: Zwischenstände sind immer Live-Berechnungen; nach `resolved_at` wird nicht neu abgerechnet.
- **Punkte-Einkommen** wird idempotent berechnet (Soll-Einkommen vs. bereits gutgeschrieben), doppelte Gutschriften ausgeschlossen.

## Testen

- Backend: pytest für Datumsfilter (Warm-up vs. Challenge), Wett-Auflösung aller vier Typen inkl. Gleichstand/leere Seite/kein Gegenhalter, Punkte-Einkommen idempotent, Einsatz > Kontostand abgelehnt.
- Frontend: bestehendes Test-Setup (vitest) für Countdown-Anzeige-Logik und Wetten-Seite (Kernflüsse).

## Ausdrücklich NICHT in diesem Umfang

- Quoten/Odds, Buchmacher-Logik
- Echtgeld oder Preise außerhalb der Punktewährung
- Push-/E-Mail-Benachrichtigungen bei Herausforderungen
- Bailout-/Stipendium-Mechanik (Punkte kommen nur über Sport rein)
