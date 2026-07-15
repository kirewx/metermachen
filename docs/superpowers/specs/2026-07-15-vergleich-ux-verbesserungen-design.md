# Design: UX-Verbesserungen der Vergleichs-Views

**Datum:** 2026-07-15
**Branch:** `feature/vergleich-ux-verbesserungen`
**Scope:** Vier zusammenhängende Verbesserungen der drei Vergleichs-Ansichten (Rennen, Sport-Mix, Verlauf). Ein gemeinsames Spec, eine gebündelte Umsetzung, ein PR.

## Kontext

Die Vergleichsseite hat drei Ansichten, gerendert aus dem `Comparison`-Objekt (`GET /api/comparison/{year}`):

- **Rennen** — `RaceBahnen.tsx`: horizontale Bahnen, Balkenlänge = `total_scaled_km`, gemeinsames Ziel `goal_km`.
- **Sport-Mix** — `SportMix.tsx`: gestapelter Balken pro Person, Segmente = Kategorien (`by_category`), Legende darunter.
- **Verlauf** — `JahresVerlauf.tsx`: kumulative Linien pro Person (recharts), Chips darunter (öffnen aktuell die Detailansicht).

Alle angezeigten Werte sind **faktorisiert**: `scaled_km = distance_km × category.factor × user.km_factor`. Der Vergleich wird bei jedem Request on-the-fly berechnet; es wird nichts gespeichert.

Backend: FastAPI + SQLModel + SQLite (`meter.db`). Frontend: React + TypeScript (Vite), Tailwind, Vitest.

## Ziele

1. **Feature 1 — Einheit „MM" mit km-Toggle:** faktorisierte Werte ehrlich als „MM" benennen, optional echte km einblenden.
2. **Feature 3 — Sport-Piktogramme im Balken:** Sportart im Sport-Mix ohne Blick in die Legende erkennbar.
3. **Feature 4 — Personen-Filter im Verlauf:** Kurven einzeln ein-/ausblenden.
4. **Feature 2 — „Seit deinem letzten Besuch":** beim Wiederaufruf animiert zeigen, was sich seit dem letzten Login verändert hat.

---

## Feature 1 — Einheit „MM" mit km-Toggle

**Verhalten**
- Standard-Einheitslabel wird in allen drei Views von „km" auf **„MM"** geändert (die Werte sind faktorisiert → „MM" = MeterMachen-Einheit).
- Ein **Toggle** (Segment-Switch `MM · km`) im Header der Vergleichsseite schaltet die **Zahl-Anzeige** auf echte km um.
- **Variante A (verbindlich):** Der Toggle ändert **nur die angezeigten Zahlen**. Bahnenlänge, Rangfolge und Ziel bleiben immer in MM — das Handicap-Rennen bleibt unverändert. **Der Toggle ändert das Ranking nicht.**
- Echte km werden clientseitig berechnet: `real_km = total_scaled_km / km_factor` (bzw. `scaled_km / km_factor` je Segment). **Kein Backend nötig.**
- Der Toggle wirkt in **allen drei Views**; die Einstellung wird in `localStorage` gemerkt (`mm_unit_mode: "mm" | "km"`, Default `"mm"`).

**Verlauf-Sonderfall (km-Modus)**
- Die Kurven zeigen rohe km je Person (`cumulative[i].scaled_km / km_factor`).
- Ziel- und Meilenstein-Referenzlinien werden **ausgeblendet** — sie sind in MM definiert und pro Person (unterschiedliche Faktoren) nicht auf eine gemeinsame km-Achse übertragbar.

**Umsetzung**
- Kleiner `UnitContext` (oder Prop-Durchreichung) mit `mode` + `toggle`, persistiert via `localStorage`.
- Helper `toDisplay(scaledKm, kmFactor, mode)` zentral, damit alle Views konsistent umrechnen und labeln.
- Randfall `km_factor === 1`: MM == km (nichts Besonderes nötig).

---

## Feature 3 — Sport-Piktogramme im Balken (`SportMix.tsx`)

**Verhalten**
- In jedem Segment das **monochrome Kategorie-Piktogramm** zentriert, **weiß mit dezentem Schatten** (kein buntes Emoji — sonst zu unruhig).
- Icon nur bei **ausreichender Segmentbreite** (Schwelle: Segmentanteil ≥ ~9 %); zu schmale Segmente bleiben leer.
- Balkenhöhe von `h-4` (16 px) auf ~`h-6` (24 px) anheben, damit ein Icon lesbar hineinpasst.
- **Legende bleibt** unter dem Diagramm als Fallback für zu schmale Segmente.

**Umsetzung**
- Bestehende `Icon`-Komponente nutzen: `<Icon name={c.icon} />`. Das Icon-Sprite ist monochrom (`currentColor`) → in Weiß rendern via Textfarbe + `drop-shadow`.
- `c.icon` liegt bereits im `CategoryShare` vor (Backend liefert es schon). **Kein Backend nötig.**
- Segmentbreite (%) wird schon berechnet (`(c.scaled_km / gesamt) * 100`) → Schwelle darauf anwenden.

---

## Feature 4 — Personen-Filter im Verlauf (`JahresVerlauf.tsx`)

**Verhalten**
- Die Chips unter dem Diagramm werden **Ein/Aus-Toggle** je Kurve: aktiv = farbig, aus = ausgegraut und die Kurve ausgeblendet.
- **„Alle / Keine"**-Schnellschalter vor den Chips. Startzustand: alle sichtbar.
- **Variante B:** Ein kleines **„i"** rechts am Chip öffnet die **Detailansicht** (`PersonDetail`). Toggle (Chip-Körper) und Detail („i") sind getrennte Klickziele.

**Umsetzung**
- Lokaler State `visible: Set<user_id>` (Default: alle). Beim Rendern nur `<Line>` für sichtbare User erzeugen (bzw. `hide`-Prop).
- „Alle" → alle IDs, „Keine" → leeres Set.
- Chip-Layout: Toggle-Fläche + separater „i"-Button (eigenes `onClick`, `stopPropagation`).

---

## Feature 2 — „Seit deinem letzten Besuch" (`RaceBahnen.tsx` + Backend)

**Verhalten (Rennen-Ansicht, nur Challenge-Phase)**
- **① Balken wachsen vom letzten Stand:** heller „Geist"-Balken auf Höhe des letzten Snapshots + weiße Linie („hier warst du"), der Rest wächst animiert auf den aktuellen Wert.
- **② „+X"-Delta** am Balkenende je Person (`aktuell − letzter Snapshot`, in MM).
- **③ Banner** oben: „vor N Tagen", Kurz-Highlights (wer wie viel gemacht hat) und **Überhol-Meldungen** (Rangänderungen ggü. Snapshot).

**Besuchs-Logik**
- Neu animiert + Banner nur, wenn der letzte Besuch **> 8 h** her ist.
- Innerhalb von 8 h: statische Anzeige, **kein** Überschreiben des Snapshots (sonst Deltas ≈ 0 bei jedem Reload).
- **Erstbesuch** (kein Snapshot vorhanden): normales Wachsen von 0 wie bisher, **kein** Banner.
- Nach abgespielter Animation wird der Snapshot auf den aktuellen Stand aktualisiert.

**Speicherung: konto-basiert (geräteübergreifend)**
- Neue Tabelle **`ComparisonSeen`**: `id`, `user_id` (FK, der Betrachter), `year`, `seen_at` (datetime), `snapshot_json` (Stände aller Teilnehmer zum Zeitpunkt). Unique-Constraint `(user_id, year)`.
- `snapshot_json`-Form: `[{ "user_id": int, "scaled_km": float, "rank": int }, …]`.
- Endpoints (im `comparison`-Router):
  - `GET /api/comparison/{year}/last-seen` → `{ seen_at, entries: [...] }` oder `null`.
  - `POST /api/comparison/{year}/seen` → schreibt aktuellen Stand (serverseitig aus der Vergleichsberechnung, Challenge-Phase) als neuen Snapshot für den eingeloggten User, `seen_at = now`.
- Tabelle wird über den bestehenden SQLModel-Mechanismus angelegt (create_all) — auf dem VPS beim Deploy automatisch.

**Ablauf (Frontend)**
1. Rennen lädt Vergleich (vorhanden) **und** `last-seen`.
2. Wenn Snapshot existiert und `now − seen_at > 8 h`: Deltas + Rangänderungen berechnen, animieren, Banner zeigen, danach `POST …/seen`.
3. Sonst: statisch rendern (bei Erstbesuch von 0 wachsen).

---

## Tests

**Frontend (Vitest)**
- `toDisplay`-Helper: MM- vs. km-Umrechnung inkl. `km_factor === 1` und Rundung.
- Sport-Mix: Icon erscheint/erscheint nicht je nach Segmentbreiten-Schwelle.
- Verlauf: Chip-Toggle blendet Kurve aus/ein; „Alle/Keine" setzt den State korrekt; „i" öffnet Detail (ruft `setDetail`).
- Rennen: Delta-Berechnung und Rangänderungs-Erkennung aus Snapshot vs. aktuell; Erstbesuch = kein Banner; < 8 h = statisch.

**Backend (pytest)**
- `GET …/last-seen` ohne Snapshot → `null`.
- `POST …/seen` schreibt Snapshot; erneutes `GET` liefert ihn zurück.
- Snapshot ist pro `(user_id, year)` eindeutig (zweites `POST` überschreibt).

## Nicht im Scope

- Direkte Garmin/COROS-Integration (bleibt bei Strava/manuell).
- Änderung der Handicap-/Faktor-Logik selbst.
- „Seit letztem Besuch" in Sport-Mix und Verlauf (bewusst nur Rennen).
