# Frontend-Cleanup, Sport-Mix & Einladungs-Flow — Design

**Datum:** 2026-06-13
**Status:** Entwurf zur Review

## Ziel

Das Frontend ruhiger und klarer machen, drei konkrete Seiten überarbeiten
(Vergleich, Aktivitäten, Admin), die Strava-Anzeige im Profil verkleinern und
die Mitglieder-Aufnahme von „Admin tippt Zugangsdaten" auf einen
Einladungslink mit Selbstregistrierung umstellen.

Leitprinzip aller UI-Änderungen: **„Sections statt Boxen"** — Inhalt wird durch
Überschriften, Abstände und dünne Trennlinien gegliedert. Ein Rahmen/eine Card
ist die Ausnahme und nur dort erlaubt, wo etwas bewusst „hervorpoppen" soll
(z. B. das aktive Eingabeformular, eine hervorgehobene Summe).

## Umfang (7 Punkte)

1. Design-Sprache: flacher, weniger verschachtelte Boxen
2. Strava im Profil: kompakte Zeile statt großem Button
3. Vergleichsseite: Reihenfolge Rennen → Verlauf → Sport-Mix (Karte ersetzt)
4. „Hinzufügen"-Formular: aufgeräumter
5. Aktivitäten: ausklappbare Kategorie-Gruppen
6. Admin-Mapping: Sport→Kategorie-Tabelle statt Tag-Wand
7. Mitglieder: Einzel-Einladungslink + QR mit Selbstregistrierung

Punkte 1–5 sind reines Frontend. Punkt 6 ist Frontend (Backend unverändert).
Punkt 7 braucht Backend + Frontend.

---

## 1. Design-Sprache: flacher

**Entscheidung:** Variante B — überwiegend flach.

- `Card` bleibt als Komponente bestehen, wird aber nur noch sparsam eingesetzt:
  primär für das aktive Eingabeformular (`SchnellwahlCard`) und einzelne
  Hervorhebungen.
- Gegliederte Bereiche (Admin-Abschnitte, Profil-Abschnitte) verwenden
  stattdessen: kleine Versal-Überschrift (`H`) + dünne untere Trennlinie
  (`border-b border-line/40`) + vertikalen Abstand.
- Listenzeilen werden nicht mehr einzeln umrahmt, sondern durch dünne
  Trennlinien zwischen den Zeilen getrennt (`divide-y divide-line/30` oder
  `border-t` je Zeile).
- Keine Karte-in-Karte mehr. Wo heute eine Card eine weitere Card/umrahmte
  Zeilen enthält, entfällt die innere Umrahmung.

**Betroffen:** `Card.tsx` (Nutzung, nicht die Komponente selbst), `Admin.tsx`,
`ProfilModal.tsx`, `MeineAktivitaeten.tsx`.

## 2. Strava im Profil

Heute: je nach Status ein voller, randvoller Button („Mit Strava verbinden" /
„Strava trennen") in einer umrahmten Box.

**Neu:** eine schlanke Zeile innerhalb des Profil-Modals (keine eigene Box):

- **Verbunden:** `Strava ✓ Verbunden` links, rechts ein dezenter Text-Button
  `Trennen` (ghost, klein, kein `w-full`).
- **Import läuft:** `Strava · Importiere … 12 / 80` mit kleinem Spinner
  (bestehende Logik bleibt).
- **Nicht verbunden:** dezenter Link/Text-Button `Verbinden` rechts neben
  `Strava` — kein großer Button.
- Nur sichtbar wenn `strava.enabled`.

Die bestehende Backfill-Toast- und Polling-Logik in `ProfilModal.tsx` bleibt
unverändert; nur das Markup der Strava-Sektion wird ersetzt.

## 3. Vergleichsseite: Reihenfolge + Sport-Mix statt Karte

**Reihenfolge der Tabs:** `Rennen` → `Verlauf` → `Sport-Mix`. Default-Ansicht
ist jetzt `rennen` (statt `karte`).

**Karte wird ersetzt** durch eine neue Ansicht **„Sport-Mix"**:
gestapelter Balken pro Person, der zeigt, wie sich die gewerteten km auf die
Kategorien verteilen (Laufen/Fahrrad/Wandern …).

- Datenquelle: **bereits vorhanden** — `ComparisonUser.by_category`
  (`CategoryShare[]` mit `scaled_km`, `color`, `name`, `icon`). **Kein
  Backend-Change.**
- Darstellung: pro Person eine Zeile (Avatar + Name links), daneben ein
  100%-breiter gestapelter Balken, Segmente in Kategorie-Farben, sortiert nach
  `rank`. Segment-Labels/Legende über Farbe → Kategoriename. Tooltip/Beschriftung
  mit km je Segment.
- Neue Komponente: `frontend/src/components/comparison/SportMix.tsx`.

**Entfällt:**
- `WanderKarte.tsx` (Komponente und Verwendung).
- Im Admin der Upload „Kartenbild (Aquarell)".
- Backend: `map_image`-Spalte, Upload-Endpoint und `uploadMapImage`-Client
  bleiben vorerst bestehen (tote, harmlose Felder) — Aufräumen optional als
  separater Schritt, um den Scope klein zu halten. Im Plan als optionaler
  Cleanup-Task vermerken.

## 4. „Hinzufügen"-Formular aufräumen

`SchnellwahlCard` bleibt als bewusst hervorgehobene Card (Ausnahme zur flachen
Regel — es ist das aktive Eingabeelement). Aufräumen:

- Abstände und Ausrichtung der `kompakt`-Variante (in Vergleich/Leiste)
  konsistenter; weniger visuelles Gewicht.
- Genaue Feinheiten werden in der Implementierung mit `frontend-design`
  ausgearbeitet; funktional bleibt das Formular wie es ist.

## 5. Aktivitäten als ausklappbare Kategorie-Gruppen

`MeineAktivitaeten.tsx`: Einträge werden nach Kategorie gruppiert dargestellt.

- **Gruppenkopf je Kategorie:** Chevron (▸/▾) + Icon + Name + `n Einträge`
  + **gewertete km gesamt** der Gruppe (tabular-nums, Akzentfarbe).
- **Default:** alle Gruppen **eingeklappt**.
- Ausgeklappt: die Einträge der Gruppe als flache Zeilen mit Trennlinien
  (kein Rahmen je Zeile), eingerückt unter dem Kopf. Pro Zeile: `distance_km →
  scaled_km`, Datum, optional Dauer/Notiz, Strava-Badge, Bearbeiten-/Löschen-
  Aktionen (bestehende Funktionalität).
- Seiten-Gesamtsumme („… km gewertet") bleibt oben erhalten.
- Leere-Zustand wie bisher.
- Gruppierung rein im Frontend aus der bestehenden `activities`-Query
  (gruppieren nach `category_id`, Reihenfolge z. B. nach Gruppen-Summe absteigend).
- Aufklapp-Zustand als lokaler Component-State (`Set<categoryId>`).

## 6. Admin: Sport→Kategorie-Tabelle

Heute: pro Kategorie ~24 Toggle-Pills für Strava-Sportarten (Tag-Wand).

**Neu:** eine eigene Sektion „Strava-Zuordnung" mit **einer Zeile je
Strava-Sportart**:

- Links der Strava-Typ (z. B. `TrailRun`), rechts ein `Select` mit allen
  aktiven Kategorien plus Option `— ignorieren`.
- **Modell: eine Sportart → höchstens eine Kategorie.** Die UI erzwingt das:
  Wird ein Typ einer Kategorie zugewiesen, wird er aus allen anderen entfernt.
- **Backend unverändert:** Datenhaltung bleibt `strava_sport_types`-Liste je
  Kategorie. Eine Zuweisungsänderung schreibt per `patchCategory` die betroffenen
  Kategorien (neue Zielkategorie hinzufügen; ggf. alte Zielkategorie bereinigen).
  Ableitung „Typ → aktuelle Kategorie" im Frontend aus den geladenen Kategorien.
- Die Kategorien-Sektion selbst (Faktor, Standard-km, aktiv/inaktiv, anlegen)
  bleibt funktional, wird aber an die flache Optik angepasst (Punkt 1).

Optional (nice-to-have, im Plan als eigener kleiner Task): Gruppierung der
Tabellenzeilen nach Sport-Familie (Laufen/Rad/Schnee/Wasser/Gym) als reine
visuelle Hilfe.

## 7. Mitglieder: Einzel-Einladungslink + QR

**Entscheidungen:** Auth bleibt wie heute (Argon2 + signiertes Session-Cookie).
Mitglied wählt **selbst** Benutzername + Passwort. Einladung ist ein
**Einzel-Link pro Person** (einmalig nutzbar, mit Ablauf).

### Backend

Neues Modell `Invite`:

```
id: int (pk)
token: str (unique, index)         # zufällig, URL-sicher (secrets.token_urlsafe)
created_by: int (fk user.id)
display_name: str | None           # optional vom Admin vorausgefüllt
is_admin: bool = False             # legt fest, ob das neue Konto Admin wird
created_at: datetime
expires_at: datetime               # z. B. created_at + 7 Tage
used_at: datetime | None = None    # gesetzt bei Einlösung → einmalig
used_by_user_id: int | None = None
```

Neuer Router `routers/invites.py`:

| Methode | Pfad | Auth | Zweck |
|---|---|---|---|
| `POST` | `/api/invites` | admin | Einladung anlegen → gibt `token`, fertige URL, `expires_at` zurück |
| `GET` | `/api/invites` | admin | offene/erledigte Einladungen auflisten |
| `DELETE` | `/api/invites/{id}` | admin | Einladung widerrufen |
| `GET` | `/api/invites/{token}` | öffentlich | Token prüfen → `{valid, display_name?, expired, used}` |
| `POST` | `/api/invites/{token}/accept` | öffentlich | Body `{username, password, display_name, avatar}` → legt User an, markiert Invite genutzt, **loggt direkt ein** (Session-Cookie) |

Regeln für `accept`:
- Token muss existieren, nicht abgelaufen, nicht genutzt sein → sonst 4xx.
- `username` eindeutig (sonst 409), `password` min. Länge wie heute (≥4).
- `is_admin` des neuen Users kommt aus dem Invite, nicht aus dem Request.
- Bei Erfolg Invite atomar als genutzt markieren (kein Doppel-Einlösen).

Validierung der Eingaben wie beim bestehenden `UserCreate`.

### Frontend

- **Admin:** Sektion „Neues Mitglied" ersetzt das direkte Anlegen durch:
  - Button „Einladung erstellen" (optional Anzeigename + Admin-Häkchen vorab).
  - Nach dem Anlegen: die Einladungs-URL anzeigen, **Kopieren-Button** und ein
    **QR-Code** der URL.
  - Liste offener Einladungen mit Status (offen/abgelaufen/genutzt) und
    „Widerrufen".
  - QR-Erzeugung clientseitig über eine schlanke Lib (z. B. `qrcode.react`) —
    neue Frontend-Abhängigkeit.
- **Neue öffentliche Route** `/einladung/:token` (außerhalb des `Layout`,
  analog zur `Login`-Behandlung in `App.tsx`):
  - Token via `GET /api/invites/:token` prüfen.
  - Gültig → Formular: Benutzername, Anzeigename (mit Invite-Wert vorausgefüllt),
    Passwort, `AvatarWahl`. Absenden → `accept` → eingeloggt → Weiterleitung auf
    `/`.
  - Ungültig/abgelaufen/genutzt → klare Meldung.
- `api/client.ts`: neue Methoden `createInvite`, `listInvites`, `deleteInvite`,
  `getInvite(token)`, `acceptInvite(token, body)`. Das alte `createUser` entfällt
  aus der Admin-UI (Methode kann bleiben oder entfernt werden).

---

## Was sich NICHT ändert

- Auth-Mechanismus (Argon2, Session-Cookie, `SECRET_KEY`).
- Bestehende Aktivitäts-/Kategorie-/Season-/Strava-Endpoints (außer den
  Ergänzungen oben).
- Rennen- und Verlauf-Ansicht (nur Reihenfolge + flache Optik).
- Datenmodell von Kategorie-Strava-Zuordnung (bleibt Liste je Kategorie).

## Testing

- **Backend:** Tests für `invites` — anlegen (admin-only), Token prüfen,
  accept-Erfolg (User entsteht, Invite genutzt, Cookie gesetzt), accept gegen
  abgelaufenes/genutztes/unbekanntes Token, doppelte Einlösung, doppelter
  Username. (pytest, bestehende Test-Patterns.)
- **Frontend:** Komponententests analog zu bestehenden (`*.test.tsx`):
  - `SportMix` rendert Segmente aus `by_category`.
  - Aktivitäten-Gruppierung: korrekte Summen, Aufklappen.
  - Admin-Zuordnungstabelle: Zuweisung entfernt Typ aus anderer Kategorie.
  - Einladungs-Annahme-Formular: Validierung, erfolgreicher Submit.

## Offene Detailfragen (in Implementierung/Plan zu klären)

- Ablaufdauer der Einladung: Default **7 Tage** (anpassbar) — als Konstante.
- Sortierreihenfolge der Aktivitäts-Gruppen (Vorschlag: nach Gruppen-Summe
  absteigend).
- Ob `map_image`/Upload-Endpoint im Backend gleich mit entfernt wird
  (optionaler Cleanup-Task).
