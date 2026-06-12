# Frontend-Redesign „Neon Night" — Design-Spec

Datum: 2026-06-13 · Status: vom Nutzer freigegeben (Brainstorming-Session)

## Ziel

Komplettes visuelles Redesign des MeterMachen-Frontends: dunkler, sportlich-professioneller
Look (Schwarz + Neon-Cyan, runde Ecken, keine Emojis im UI) mit einer neuen
Schnellwahl-Eingabe als Herzstück. Die Backend-Logik bleibt unverändert bis auf zwei
kleine Felderweiterungen (`Category.default_km`, verallgemeinertes Avatar-Feld).

## Entscheidungen (aus dem Brainstorming)

| Thema | Entscheidung |
|---|---|
| Stil | Tron-Schwarz mit Cyan-Glow, aber runde Ecken („Athletic"-Rundungen) |
| Farbmodus | Dunkel (Default) + heller Modus, Toggle in der Nav, `localStorage` |
| Schnellwahl-Layout | Big-Tap-Karte: riesige km-Zahl, runde +/− Buttons |
| Felder Schnellwahl | Nur Kategorie + km; Datum/Dauer/Notiz/freie km hinter „Details"-Toggle |
| km-Startwert | Fester Standardwert **pro Kategorie**, vom Admin gepflegt (`default_km`) |
| Platzierung | Hero auf „Meine Aktivitäten" + kompakte einklappbare Variante auf Vergleichsseite |
| Emojis | Raus aus dem UI → SVG-Piktogramme; Ausnahme: User-Avatare (Emoji oder Piktogramm, wählbar in Profil-Settings) |
| Avatare | Kein Bild-Upload; Auswahl Emoji-Grid oder Piktogramm-Grid |
| Visualisierungen | Logik/Datenfluss bleibt; Optik neu: Lesbarkeit + Neon-Glow/Animationen |
| Architektur | Mini-Design-System: Theme-Tokens + eigene UI-Bausteine, kein Library-Umzug |

## 1 · Design-System & Theme

`index.css` definiert Tailwind-v4-`@theme`-Tokens auf Basis von CSS-Variablen, die per
`.dark`-Klasse auf `<html>` umgeschaltet werden. Default dunkel; Toggle (Mond/Sonne) in
der Nav, Wahl in `localStorage` persistiert.

**Dunkel (Hauptmodus):**
- Seite `#050508`, Kartenfläche `#0a0f12`, Kartenrand `rgba(0,229,255,.3)`
- Akzent Neon-Cyan `#00e5ff`, Text Weiß / Blaugrau (`#bfeef7`), gedämpft `#5a8a96` / `#3d6d77`
- Glow (box-/text-shadow in Akzentfarbe) NUR an: Primär-Buttons, aktiven Nav-Pills,
  Hero-Zahlen, Fortschrittsbalken, erreichten Meilensteinen. Nicht an jedem Rahmen.

**Hell:** Weiß/sehr helles Grau (`#f4f7f9`), Akzent `#0891b2`-Richtung, keine Glows,
identische Radii/Typo/Abstände.

**Form & Typo:** Karten ~16–20 px Radius, Buttons/Inputs 10–12 px, Stepper-Buttons rund
(50 %). Systemfont; Zahlen `font-black` + `tabular-nums`, deutlich größer als Fließtext.

**UI-Bausteine** unter `components/ui/`: `Card`, `Button` (primary = Cyan gefüllt mit
Glow, ghost = Outline, danger), `Select`, `Input`, `Stepper` (−/Wert/+), `StatValue`
(große Glow-Zahl mit Label), `Modal`, `Toast`, `Icon`. Alle Seiten nutzen ausschließlich
diese Bausteine; kein direktes Farb-Hexen in Seiten-Komponenten.

## 2 · Navigation & Layout

- Top-Nav als dunkle Glasleiste (leicht transluzent, `backdrop-blur`), unten 1 px
  Cyan-Linie: Logo „METERMACHEN" (Wortmarke, „MACHEN" in Cyan, Blitz-Piktogramm),
  Tabs Vergleich / Meine Aktivitäten / Admin als Pills (aktiv = Cyan-Outline + Glow),
  rechts Theme-Toggle, Avatar + Name (öffnet Profil-Menü), Logout.
- Mobil (< sm): Tabs wandern in eine fixe Bottom-Bar (Icon + Label, aktive Route glüht);
  Theme-Toggle und Profil bleiben oben.
- Inhaltsbreite `max-w-5xl`, Seiten-Padding wie bisher.

## 3 · Piktogramme & Icons

Eigenes SVG-Sprite `frontend/public/icons.svg` (Stroke-Stil, `currentColor`, 24er-Grid)
plus `<Icon name size>`-Komponente.

Benötigte Schlüssel:
- Sport: `laufen`, `rad`, `wandern`, `schwimmen`, `ski`, `inline`, `medaille` (Fallback)
- UI: `plus`, `minus`, `blitz`, `stift`, `papierkorb`, `chevron`, `karte`, `flagge`,
  `chart`, `zahnrad`, `mond`, `sonne`, `logout`, `kalender`, `uhr`, `notiz`, `x`
- Meilensteine: `fahne`, `berg`, `pokal`

**Datenmodell-Änderungen:**
- `Category.icon_emoji` → `Category.icon` (Icon-Schlüssel). Startup-Migration mappt
  Bestandsdaten (🏃→`laufen`, 🚴→`rad`, 🥾→`wandern`, …, unbekannt→`medaille`).
- Meilenstein-`emoji` → Icon-Schlüssel (gleiche Mapping-Logik, unbekannt→`fahne`).
- `User.avatar_emoji` → `User.avatar`: enthält entweder ein Emoji (Avatare dürfen bunt
  sein) oder einen Piktogramm-Schlüssel mit Präfix `icon:` (z. B. `icon:berg`).
  Frontend-Komponente `Avatar` rendert beides einheitlich rund.

## 4 · Schnellwahl

Komponente `SchnellwahlCard` mit Varianten `hero` (Aktivitäten-Seite) und `kompakt`
(Vergleichsseite, einzeilige Leiste, einklappbar; Zustand in `localStorage`).

Verhalten:
- Kategorie-Dropdown: nur aktive Kategorien, mit Piktogramm + Faktor; vorausgewählt ist
  die zuletzt benutzte Kategorie (`localStorage`), sonst die erste.
- km-Wert startet beim `default_km` der gewählten Kategorie (Fallback 10);
  Kategorie-Wechsel setzt den Wert auf deren Standard zurück.
- +/− ändert in 1-km-Schritten, Minimum 1; gedrückt halten wiederholt (Press-and-hold,
  Polish in Plan 2).
- Unter der Zahl live: „= X km gewertet" (Wert × Faktor, 1 Nachkommastelle) und das
  Datum („heute, 13. Juni" bzw. gewähltes Datum).
- „Details"-Toggle klappt auf: Datum (Default heute), Dauer (min), Notiz, freie
  km-Eingabe (Dezimalwerte erlaubt, überschreibt den Stepper-Wert).
- Speichern: legt Eintrag an, Wert springt auf Kategorie-Standard zurück, kurzer
  Glow-Puls auf der Karte als Bestätigung (Polish in Plan 2); Fehler als Toast.
- Bearbeiten eines Eintrags öffnet dieselbe Karte im Hero-Kontext mit aufgeklappten
  Details und den Eintragswerten (ersetzt die bisherige Formular-Wiederverwendung).

**Backend:** neues Feld `Category.default_km: float = 10` (Schema `CategoryCreate`/
`CategoryPatch` erweitert, Admin-UI pflegt es). Da kein Alembic existiert: leichte
Startup-Migration in `db.py` (PRAGMA-Spaltencheck → `ALTER TABLE ADD COLUMN`), die auch
die Icon-/Avatar-Umbenennungen abdeckt.

## 5 · Profil-Settings (neu)

Avatar in der Nav öffnet Menü → „Profil": Modal mit Anzeigename, Avatar-Wahl
(Tabs Emoji-Grid / Piktogramm-Grid) und Passwort ändern. Nutzt bestehendes
`PATCH /api/users/me` (Feld wie in §3 verallgemeinert).

## 6 · Seiten

- **Login:** zentrierte Glow-Karte, Wortmarke, zwei Inputs, Primär-Button „Los geht's";
  Fehler als roter Hinweis in der Karte.
- **Meine Aktivitäten:** SchnellwahlCard (hero) oben, darunter „Meine Einträge {Jahr}"
  mit Summenzeile (gewertete km gesamt) und Eintragskarten: Piktogramm, „X km Kategorie
  → Y km" (gewertet in Cyan), Datum/Dauer/Notiz gedämpft, Stift-/Papierkorb-Icons.
  Löschen über Bestätigungs-Modal statt `confirm()`.
- **Vergleich:** kompakte Schnellwahl-Leiste oben, Ansichts-Tabs (Karte/Rennen/Verlauf)
  als Pills mit Piktogramm, darunter die jeweilige Visualisierung als Card.
- **Admin:** drei Cards (Kategorien, Jahr, Mitglieder). Kategorien-Tabelle mit
  Piktogramm-Picker (Grid-Auswahl), Faktor, **Standard-km**, Farbe, aktiv/inaktiv;
  Anlegen neuer Kategorien bleibt (aufgewertet mit Picker). Jahr: Ziel, Meilensteine
  (Icon-Schlüssel-Picker statt Emoji-Feld), Kartenbild-Upload. Mitglieder: Liste +
  Neuanlage (Avatar-Wahl wie Profil-Modal).

## 7 · Visualisierungen (Optik neu, Logik bleibt)

Gemeinsames Fundament: feste Neon-Palette pro Person (Cyan, Eisblau, Türkis,
Violett-Blau, …) — identische Personenfarbe in allen drei Ansichten (`userColor`-Helper,
stabil über User-ID-Reihenfolge). Dezente Einblend-Animationen (Balken/Linien wachsen
beim Mount), große tabellarische Zahlen.

- **RaceBahnen:** dunkle Bahnen mit abgerundeten Glow-Fortschrittsbalken
  (Verlauf transparent→Personenfarbe), links Rang + Avatar + Name, rechts km groß;
  Meilensteine als vertikale Marker mit Piktogramm; Zeile „Abstand zu P1"; führende
  Bahn glüht am stärksten.
- **WanderKarte:** Aquarell-Bild bleibt, bekommt dunkle Rand-Vignette im Card-Rahmen;
  Route als leuchtende Cyan-Linie; erreichte Meilensteine als Glow-Badges mit
  Piktogramm; Avatare mit Namens-Chip (dunkler, lesbarer Hintergrund).
- **Jahresverlauf (Recharts):** kaum sichtbares Grid, Neon-Linien mit Glow
  (SVG-Filter), Endpunkt-Dot je Linie, Namens-Label direkt am Linienende statt
  Legende, dunkler Tooltip im Card-Stil.

## 8 · Fehlerbehandlung

Zentrale `Toast`-Komponente (dunkle Karte, roter Neon-Rand für Fehler, cyan für
Erfolg); alle Mutations-Fehler laufen darüber. Lösch-Bestätigungen als `Modal`.

## 9 · Tests

- **Frontend (Vitest/RTL):** `SchnellwahlCard` (Minimum 1 km, Kategorie-Wechsel →
  Standard-km, Details-Toggle, Submit-Payload inkl. Datum-Default heute, „gewertet"-
  Anzeige), `Icon`/`Avatar`-Rendering (Emoji vs. `icon:`-Schlüssel), Theme-Toggle
  (Klasse + `localStorage`); `pathMath.test.ts` bleibt unverändert.
- **Backend (Pytest):** `default_km` in Create/Patch/Response; Startup-Migration auf
  einer Bestands-DB (Spalten fehlen → werden ergänzt, Emoji-Mapping läuft);
  Avatar-Feld akzeptiert Emoji und `icon:`-Werte.

## 10 · Umsetzung in zwei Plänen

1. **Fundament + Eingabe:** Theme/Design-System, Icon-Sprite + `Icon`/`Avatar`,
   Nav/Layout (Bottom-Bar, Theme-Toggle, Profil-Modal), Backend-Felder + Migration,
   SchnellwahlCard, Seiten Login/Meine Aktivitäten/Admin, Toast/Modal.
2. **Visualisierungen:** RaceBahnen, WanderKarte, Jahresverlauf im neuen Look
   (nutzt Palette/Bausteine aus Plan 1), Vergleichsseite mit kompakter, einklappbarer
   Schnellwahl sowie Schnellwahl-Polish (Press-and-hold, Glow-Puls).

## Nicht-Ziele

- Kein Bild-Upload für Avatare, keine neuen Auswertungen/Statistiken, keine Änderung
  der Vergleichs-/Wertungslogik, kein Komponenten-Library-Umzug, keine PWA/Offline-
  Funktionen.
