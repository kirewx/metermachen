# Design: UI-Anpassungen + Newsfeed

**Datum:** 2026-07-25 · **Status:** Entwurf, wartet auf Ricks Review

## Ziel

Zwei Pakete:

1. **Quick-Fixes** — sechs kleine Anpassungen an Vergleich, Aktivitäten,
   Achievements und Streak-Wetten.
2. **Newsfeed** — neuer Tab mit chronologischem Gruppen-Feed (Aktivitäten,
   Überholungen, Achievements/Meilensteine, Wochen-/Monatsrückblicke) und
   Emoji-Reaktionen. Mobile-first.

**Auslieferung: zwei PRs** — PR 1 Quick-Fixes, PR 2 Newsfeed.

**Nicht in diesem Umfang:** Profilseite (später), Challenges im Feed
(existieren noch nicht), freie Emoji-Auswahl, Multi-Gruppen (wird aber durch
Season-Scoping der Events vorbereitet).

---

## Teil A: Quick-Fixes (PR 1)

### A1. Archiv ins Saison-Dropdown

- Der Tab **Archiv** verschwindet aus der Navigation
  (`frontend/src/components/ui/tabs.ts`); die Route `/archiv` entfällt.
- Das Saison-`<Select>` im Vergleichstab (`Vergleich.tsx`) bekommt unterhalb
  der Saisons eine zusätzliche Option **„Archiv (Warm-up)"** (Spezialwert
  `archiv`). Neue Saisons erscheinen automatisch darüber (Liste kommt aus
  `api.seasons()`, absteigend sortiert).
- Bei Auswahl von „Archiv" rendert der Vergleichstab statt der Renn-Ansicht
  den heutigen Archiv-Inhalt: Warm-up-Rangliste + Warm-up-Auszeichnungen.
  Der Inhalt von `pages/Archiv.tsx` wird dafür zur wiederverwendbaren
  Komponente (z. B. `components/comparison/WarmupArchiv.tsx`); die
  Unteransicht-Umschaltung (Rennen/Verlauf/Sport-Mix) und der MM/km-Toggle
  sind im Archiv-Modus ausgeblendet.

### A2. Saison-Label „2026/27"

- **Daten:** Migrationseintrag im bestehenden `db.py migrate()`-Muster: hat
  die Season 2026 kein `end_date`, wird es auf **2027-05-16** gesetzt
  (Stuttgartlauf; per Admin-Panel weiter änderbar).
- **Label:** `saisonLabel()` in `season.ts` kürzt „Saison 2026/27" auf
  **„2026/27"** (einjährige Saisons bleiben „2026").

### A3. Platzierungen ohne „P"

`P{rank}` wird überall zu `{rank}`: Renn-Ansicht
(`RaceBahnen.tsx`), Warm-up-Archiv, Punkte-Ranking (`PunkteRanking.tsx`),
Personen-Detail (`PersonDetail.tsx`).

### A4. Rückstand-Zeile entfernen

Die Zeile „−X km auf P1" unter den Verfolger-Namen in `RaceBahnen.tsx`
entfällt ersatzlos (inkl. der `abstand`-Berechnung).

### A5. Aktivitäts-Titel mehrzeilig

Strava-Titel (`Activity.note`) brechen um statt abgeschnitten zu werden
(`truncate` → mehrzeiliger Umbruch) an beiden Stellen:

- eigener Aktivitätenverlauf (`MeineAktivitaeten.tsx`, Meta-Zeile),
- Personen-Detailansicht (`PersonDetail.tsx`).

### A6. Achievement-Tooltips

- **Backend:** Der Comparison-Endpoint liefert statt `emojis: string[]` eine
  Liste `auszeichnungen: [{emoji, name, description}]` (aus den bestehenden
  Definitionen in `services/achievements.py`; `comparison.py` reichert die
  showcased Unlocks an). Blackboard-Datenquelle analog.
- **Frontend:** Jedes Emoji wird einzeln gerendert; Hover **und** Tap öffnen
  ein kleines Popover „{emoji} {name} — {description}" (z. B. „🎩 Hattrick —
  3 Aktivitäten an einem Tag"). Schließt bei Tap außerhalb. Gilt in
  `RaceBahnen.tsx` und `Blackboard.tsx`.

### A7. Streak-Wetten: 5-MM-Tagesminimum

- `bet_metrics.longest_streak`: Ein Tag zählt nur, wenn die Summe der
  **gewerteten** Kilometer des Tages ≥ **5,0 MM** ist
  (`distance_km × category.factor`, **ohne** Admin-Handicap — konsistent mit
  allen anderen Wett-Metriken, die `km_factor` bewusst ignorieren) — bisher
  ≥ 1,0 km Rohdistanz. Die Metrik braucht dafür die Kategorie-Faktoren.
- Gilt **sofort für alle Streak-Wetten, auch laufende** (der Streak wird
  ohnehin bei jeder Auflösung komplett neu berechnet — vergangene Tage werden
  damit rückwirkend nach der neuen Regel bewertet).
- Beschreibungstexte anpassen: Wett-Erstellung/Regeln erwähnen „mind. 5 MM
  pro Tag".
- **Unverändert:** Die Streak-Regel des Dauerbrenner-Achievements (≥ 1
  Eintrag pro Tag, `services/achievements.py`).

### A8. MM-Logo statt Blitz in der Top-Leiste

Das Blitz-Icon neben dem Schriftzug (`Layout.tsx`, `Icon name="blitz"`) wird
durch das MM-Logo ersetzt: der neonblaue Zickzack-„M"-Strich aus
`public/favicon.svg` (nur der leuchtende Pfad, ohne den Kasten) als eigenes
Icon in Akzentfarbe, gleiche Größe wie bisher.

### A9. Aktive Tabs/Umschalter ohne Umrandung

Aktive Zustände markieren nur noch den **Text/Icon in Akzentfarbe mit
Neon-Glow** (`[text-shadow:var(--t-glow)]`) — keine Pill-Umrandung, kein
`border`/`shadow-glow` mehr. Betrifft:

- Desktop-Tab-Leiste (`Layout.tsx`, `pill`-Klasse) — damit verhält sie sich
  wie die mobile Bottom-Bar, die das Muster schon nutzt,
- Ansichten-Umschalter Rennen/Verlauf/Sport-Mix (`Vergleich.tsx`,
  `ANSICHTEN`-Buttons) — hier verlieren auch die **inaktiven** Buttons ihre
  graue Umrandung (`border-line`).

Inaktive Zustände bleiben gedämpft (`text-ink-mute`, Hover wie bisher).
Der MM/km-Toggle daneben bleibt unverändert (gefüllte Segmente, keine
Pill-Umrandung im selben Sinn).

---

## Teil B: Newsfeed (PR 2)

### B1. Datenmodell

Drei neue Tabellen (`models.py`):

- **`FeedEvent`** — `id`, `season_year`, `type`
  (`activity | rank_change | achievement | milestone | recap_week |
  recap_month`), `user_id` (nullable; leer bei Rückblicken), `activity_id`
  (nullable; nur bei `activity`, mit Cascade-Delete beim Löschen der
  Aktivität), `payload_json`, `created_at` (UTC). Index auf
  `(season_year, created_at)`.
- **`FeedReaction`** — `id`, `event_id` (FK), `user_id`, `emoji`,
  `created_at`; Unique auf `(event_id, user_id, emoji)`. Erlaubte Emojis
  (festes Set): **👏 🔥 💪 😂 😮** — Backend validiert.
- **`FeedSeen`** — `user_id` (unique), `seen_at`; gleiches Muster wie
  `ComparisonSeen`.

`payload_json` je Typ:

- `activity`: Kategorie-Key/-Name/-Icon, `distance_km`, `scaled_km`, Titel
  (`note`), Datum/Uhrzeit der Aktivität.
- `rank_change`: Überholer (`user_id`, Name), Überholte(r), neuer Rang.
  Nur bei Änderungen der Reihenfolge in den **Top 5**.
- `achievement` / `milestone`: Key, Name, Emoji/Icon, ggf. Kontext
  (z. B. „150 MM gesamt").
- `recap_week` / `recap_month`: Zeitraum (KW bzw. Monat), Gruppen-Summe MM,
  pro Person MM des Zeitraums (sortiert), Überholungs-Liste,
  Achievement-Liste des Zeitraums.

### B2. Event-Erzeugung (`services/feed.py`)

- **Aktivität angelegt** (manuell + Strava-Webhook): `activity`-Event.
  **Kein Event beim Strava-Backfill** (Import der Historie) — sonst flutet
  der Import den Feed. `created_at` = Upload-Zeitpunkt, nicht das
  Aktivitätsdatum.
- **Rangfolge:** Bei jeder Aktivitäts-Mutation (anlegen, bearbeiten,
  löschen) wird die Top-5-Reihenfolge der Saison vor/nach verglichen; bei
  Änderung entsteht ein `rank_change`-Event pro Überholvorgang.
- **Achievements:** `check_unlocks` (`services/achievements.py`) emittiert
  beim Persistieren eines Unlocks ein `achievement`-Event.
- **Meilensteine:** Beim Aktivitäts-Schreiben wird geprüft, ob die
  Gesamt-MM des Nutzers einen Meilenstein aus `milestones_json` überschritten
  haben → `milestone`-Event.
- **Rückblicke (lazy, kein Cron):** Beim ersten `GET /api/feed` nach
  Montag 00:00 **deutscher Zeit** wird der `recap_week` der Vorwoche
  (Mo–So) erzeugt, falls er fehlt; am Monatsersten zusätzlich `recap_month`
  des Vormonats. Gleiches Muster wie `ensure_monthly_tip`
  (`services/bets.py`). Zeitzonen-Handling wie beim Challenge-Start
  (00:00 deutscher Zeit).

### B3. API (`routers/feed.py`)

- `GET /api/feed?year=…&before=…` — neueste zuerst, **30 pro Seite**,
  Cursor `before` (created_at/id des letzten Eintrags). Antwort enthält pro
  Event die Reaktions-Zähler je Emoji, die eigenen Reaktionen und die Namen
  der Reagierenden (für „wer hat reagiert"). Ruft vorab die
  Rückblick-Sicherstellung auf.
- `POST /api/feed/{event_id}/reactions` `{emoji}` — Toggle; validiert gegen
  das feste Set; Antwort: aktualisierte Zähler.
- `GET /api/feed/unseen` — `{has_new: bool}` (Events neuer als `FeedSeen`),
  leichtgewichtig für den Tab-Punkt.
- `POST /api/feed/seen` — setzt `seen_at` = jetzt (beim Öffnen des Feeds).

### B4. Frontend

- **Tab „Feed"** (`tabs.ts`): zwischen Vergleich und Aktivitäten, Route
  `/feed`, sichtbar ab Challenge-Start (`abStart: true`). Grüner Punkt am
  Tab-Label, solange `has_new`; `Layout.tsx` pollt `GET /api/feed/unseen`
  über React Query (Standard-`staleTime` 30 s genügt).
- **`pages/Feed.tsx`** mit Komponenten `FeedItem`, `RecapCard`,
  `ReactionBar`:
  - Tages-Trenner: „Heute", „Gestern", davor Wochentag, älter Datum.
  - Einträge mit **Sportart-Farbbalken** links (Farbe pro Kategorie-Key aus
    einer festen Palette: Rad blau, Lauf grün, Schwimmen türkis; weitere
    Kategorien bekommen deterministisch eine Farbe). `rank_change` violett,
    `achievement`/`milestone` und Rückblicke gold.
  - „Mehr laden"-Button (Cursor-Pagination).
  - Beim Öffnen: `POST /api/feed/seen`.
- **`ReactionBar`:** vorhandene Reaktionen als Chips mit Zähler (eigene grün
  markiert), „＋" öffnet die Auswahl mit dem festen Set; Tap auf Chip oder
  Auswahl togglet; Tap auf den Zähler zeigt die Namen der Reagierenden.
- **`RecapCard`** im „Mini-Rennen"-Design (validiertes Mockup): Kopfzeile
  „📊 Wochenrückblick · KW n" bzw. „Monatsrückblick · Monat", Zeile
  „Gruppe gesamt: X MM", darunter ein horizontaler Balken pro Person
  (Zeitraum-MM, Personen-Farben aus `userColor`), Fußzeile mit Überholungen
  (📈) und Achievements (🏆) des Zeitraums.

**Hinweis Umsetzung:** Beim Bauen des Feed-Frontends den
`frontend-design`-Skill laden — als Politur (Abstände, Typo-Hierarchie,
Interaktionszustände) innerhalb der bestehenden Designsprache der App,
keine Neugestaltung. Die validierten Mockups sind maßgeblich.

### B5. Randfälle

- Aktivität gelöscht → `activity`-Event verschwindet (Cascade); dadurch
  ausgelöste Rangänderungen erzeugen reguläre `rank_change`-Events.
- Aktivität bearbeitet → Event bleibt wie gepostet (Zahlen im Payload werden
  nicht nachgezogen); Rangfolge wird neu geprüft.
- Reaktionen auf gelöschte Events verschwinden mit (FK-Cascade).
- Erster Feed-Aufruf nach Launch: Es gibt keine rückwirkenden Events für
  die Zeit vor dem Feature — der Feed beginnt ab Deployment; Rückblicke
  werden erst ab der ersten vollen Woche/dem ersten vollen Monat nach
  Launch erzeugt.

### B6. Skalierung / Multi-Gruppen

- Events sind über `season_year` gescoped; kommt Multi-Gruppen-Fähigkeit,
  wird eine `group_id`-Spalte ergänzt und die Feed-Query filtert zusätzlich —
  kein Umbau der Architektur.
- Cursor-Pagination + Index halten die Abfrage auch bei zehntausenden
  Events schnell.

---

## Tests

- **Backend (pytest):** Event-Emission (Aktivität, Überholung inkl.
  Bearbeiten/Löschen, Achievement, Meilenstein), Backfill-Schutz,
  Recap-Erzeugung an Wochen-/Monatsgrenzen (deutsche Zeit, idempotent),
  Reaktions-Toggle + Set-Validierung, `unseen`-Logik, Streak-Metrik mit
  5-MM-Grenze (inkl. Faktoren), Season-`end_date`-Migration,
  `auszeichnungen`-Payload im Comparison-Endpoint.
- **Frontend:** bestehende Muster; mindestens Rendering der Feed-Typen und
  der Archiv-Option im Saison-Select.

## Entscheidungen (Rick, 24./25.07.2026)

- Archiv-Option zeigt den heutigen Archiv-Inhalt (nicht die volle
  Vergleichsansicht).
- Saisonende: 16.05.2027.
- 5-MM-Regel gilt sofort für alle Streak-Wetten, auch laufende.
- Titel: mehrzeilig umbrechen (beide Ansichten).
- Feed: eigener Tab, mobile-first; alle vier Event-Gruppen ab V1;
  festes Reaktions-Set; Punkt am Tab; Rückblicke wöchentlich + monatlich
  mit allen vier Inhalten; Rückblick-Design „Mini-Rennen".
- Technik: Ansatz A (materialisierte Event-Tabelle).
