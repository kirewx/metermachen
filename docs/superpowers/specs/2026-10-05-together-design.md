# Together: gemeinsame Aktivitäten erkennen — Design

Stand: 2026-10-05 · Branch `feat/together`

## Ziel

MeterMachen erkennt, wenn Mitglieder gemeinsam trainiert haben, und macht das
sichtbar (Feed, Profil) und belohnt es (Achievements). **Rein sozial:** keine
Auswirkung auf MM, Ranking, Punkte oder Wetten. Fehl-Matches sind dadurch
billig und korrigierbar.

Technische Bezeichner des neuen Subsystems sind durchgehend **englisch**
(Modelle, Felder, Status, Keys, Feed-Typ, Endpunkte). UI-Texte bleiben deutsch.

## Teil 0 — Strava-Sync-Grundlage (eigener, erster PR)

Unabhängig vom Add-on, immer aktiv.

### 0.1 Ignore-Liste

- Neue Tabelle `StravaIgnored(id, user_id, external_id, created_at)`,
  unique auf `(user_id, external_id)`.
- Löscht jemand eine Aktivität mit `source="strava"` in MeterMachen, wird sie
  weiterhin hart gelöscht **und** ein `StravaIgnored`-Eintrag geschrieben.
- `import_activity` und die Update-Behandlung prüfen die Liste zuerst und tun
  bei einem Treffer nichts. Damit kommt eine gelöschte Dublette (z. B. Uhr +
  Handy) weder per Backfill, Reconnect noch Update-Webhook zurück.
- Kein Soft-Delete auf `Activity`, weil sonst jede Auswertung (Ranking,
  Vergleich, Achievements, Wetten, Challenges, Feed) filtern müsste.
- Beim Strava-Disconnect bleiben `StravaIgnored`-Einträge erhalten.

### 0.2 Webhook `update`

- Aktivität per `fetch_activity` neu laden.
- Auf Ignore-Liste → nichts tun.
- In MeterMachen noch nicht vorhanden → normaler `import_activity`-Pfad
  (z. B. Sportart war vorher nicht gemappt).
- Vorhanden und `updated_at is None` (nie in MeterMachen bearbeitet) →
  `note` (Titel), Kategorie (falls neue Sportart gemappt ist), `distance_km`,
  `duration_min`, `elevation_m`, `date`, `start_time` überschreiben.
  `updated_at` bleibt `None` (keine „bearbeitet“-Markierung).
- Vorhanden und `updated_at` gesetzt → Aktivitätsfelder bleiben unberührt
  (Granularität: ganze Aktivität, nicht je Feld).
- Neue Sportart nicht mehr mappbar → Aktivität bleibt unverändert, keine
  Löschung.
- In allen Fällen mit vorhandener Aktivität: `ActivityTrack` aktualisieren
  (siehe 0.4). Nicht in MeterMachen editierbar, daher immer von Strava.
- Bei geänderten Werten: Payloads bestehender Feed-Events der Aktivität
  aktualisieren (kein neues Event), `check_unlocks` für den Nutzer erneut
  ausführen, Rang-Events wie beim Bearbeiten.
- Bei aktivem Add-on `together`: Matching für die Aktivität erneut ausführen.

### 0.3 Webhook `delete`

- Aktivität inkl. Feed-Events löschen (Pfad wie `delete_activity`), inkl.
  `SessionParticipant` (siehe 2.6). Kein `StravaIgnored`-Eintrag nötig.

### 0.4 `ActivityTrack`

- Tabelle `ActivityTrack(id, activity_id unique, start_utc, elapsed_s,
  start_lat, start_lng, end_lat, end_lng, polyline, geo_expires_at)`.
- Wird bei jedem Strava-Import und -Update geschrieben, aus `start_date`,
  `elapsed_time`, `start_latlng`, `end_latlng`, `map.summary_polyline`.
  Aktivitäten ohne GPS: Koordinaten und `polyline` = `NULL`.
- `geo_expires_at = start_utc + 48 h`.
- **Datenschutz-Cleanup** `purge_expired_geo(session)`: setzt Koordinaten und
  `polyline` aller Tracks mit `geo_expires_at < now` auf `NULL`. `start_utc`
  und `elapsed_s` bleiben. Aufruf bei jedem Webhook-Lauf und beim App-Start
  (kein neuer Cron).
- Gelöscht mit der Aktivität.

## Teil 1 — Matching

### 1.1 Datenerfassung und Opt-out

- `User.detect_together: bool = True` (Opt-out). Ist es `False`, wird der
  Nutzer weder automatisch gematcht noch kann er getaggt werden; bestehende
  Sessions bleiben.
- Strava-Aktivitäten mit Sichtbarkeit „Nur ich“ werden **mit** gematcht. Es
  wird nie eine Route angezeigt, nur Partner, km und Anteil.

### 1.2 Auslöser

- Nach jedem Strava-Import (Webhook und Backfill) und nach Strava-Updates:
  `together.match_activity(session, act)`, nur wenn Add-on `together` aktiv
  und `user.detect_together`.
- Läuft nach dem Import-Commit in eigenem `try/except`. Ein Fehler wird
  geloggt und bricht den Import nie.
- Asynchrone Ankunft: jeder neue Import sucht rückwärts. Wer zuerst hochlädt,
  ist egal, solange die Polyline des Partners noch nicht abgelaufen ist
  (48 h).

### 1.3 Kandidaten

Tracks **anderer** Nutzer mit `detect_together`, deren Zeitfenster
`[start_utc, start_utc + elapsed_s]` sich mit dem eigenen überlappt, um
**≥ 10 min oder ≥ 50 % der kürzeren Aktivität**. Kategorie muss nicht
übereinstimmen. Paare mit bestehendem `declined` werden übersprungen (2.3).

### 1.4 Streckenvergleich (`services/together_geo.py`, reine Funktionen)

1. Beide Polylines dekodieren (eigener Decoder für das Google-Polyline-Format,
   keine neue Abhängigkeit).
2. Für jedes Segment von A: liegt dessen Mittelpunkt innerhalb **50 m** eines
   Segments von B? (Punkt-zu-Segment-Distanz, equirektangulare Näherung.)
3. `km_together_a` = Länge der abgedeckten Segmente von A; analog B gegen A.
4. `km_together = min(km_together_a, km_together_b)`,
   `share = km_together / min(distance_a, distance_b)`.

Fehlt auf einer Seite die Polyline oder ist sie kaputt → kein Auto-Match
(dafür gibt es das manuelle Taggen).

### 1.5 Schwellen

| Bedingung | Ergebnis |
|---|---|
| `share ≥ 50 %` **und** `km_together ≥ 2` | Auto-Match: beide `confirmed` |
| sonst `share ≥ 30 %` **oder** `km_together ≥ 2` | Vorschlag: beide `suggested` |
| sonst | nichts |

Schwellen als Konstanten im Service.

### 1.6 Gruppenzuordnung

- Gehört die Partner-Aktivität schon zu einer `TrainingSession`, tritt die
  neue Aktivität dieser bei. Sonst entsteht eine neue Session.
- Würden zwei bestehende Sessions zusammenfallen, gewinnt die ältere und
  übernimmt die Teilnahmen der anderen. Deren Feed-Event wird entfernt, das
  der älteren aktualisiert.
- `TrainingSession.km_together` = Maximum der paarweisen `km_together` der
  bestätigten Teilnahmen; `share` analog.

## Teil 2 — Sessions, Bestätigung, manuelles Taggen

### 2.1 Datenmodell

- `TrainingSession(id, source "auto"|"manual", km_together, share
  nullable, created_at)`
- `SessionParticipant(id, session_id, user_id, activity_id nullable,
  status "confirmed"|"suggested"|"declined", km_together, created_at,
  responded_at nullable)`
  - unique `(session_id, user_id)`; eine Aktivität gehört zu höchstens einer
    Session (unique auf `activity_id`, wo nicht `NULL`).
- Eine Session ist **echt**, sobald ≥ 2 Teilnahmen `confirmed` sind. Nur
  echte Sessions erscheinen im Feed, im Profil und zählen für Achievements.

### 2.2 Auto-Match

Beide Teilnahmen direkt `confirmed`. Jede Seite kann rückgängig machen
(„War ich nicht dabei“ → eigene Teilnahme `declined`). Bleiben < 2
bestätigte, ist die Session nicht mehr echt (Feed-Event entfernt).

### 2.3 Kein erneuter Vorschlag

`declined` bleibt gespeichert. Das Matching überspringt jedes Aktivitätspaar,
bei dem eine Seite für diese Session `declined` hat, auch nach Update-Webhooks.

### 2.4 Vorschlag

Beide Teilnahmen `suggested`. Anzeige: „Warst du mit Anna unterwegs?
(7,1 km gemeinsam)“ mit ✅ / ❌. Echt, sobald 2 bestätigt haben. Unbeantwortete
Vorschläge laufen nach **14 Tagen** ab und gelten als `declined` (lazy beim
Abruf der Vorschläge).

### 2.5 Manuelles Taggen

- Aktivitätsformular (Anlegen und Bearbeiten, manuell und Strava) bekommt
  „Mit wem?“ (Mehrfachauswahl anderer aktiver Nutzer mit `detect_together`).
- Beim Speichern: `TrainingSession(source="manual")`, eigene Teilnahme
  `confirmed` mit eigener Aktivität, Getaggte `suggested` ohne Aktivität.
- Getaggte sehen „Erik sagt, ihr wart zusammen unterwegs“ und können
  - eine eigene Aktivität vom Tag ±1 wählen (nur solche, die noch in keiner
    Session sind),
  - eine neue anlegen (Formular vorausgefüllt mit Kategorie, Datum, Dauer und
    Distanz des Taggenden),
  - ablehnen.
- `km_together` = kürzere der beiden Distanzen.
- Entfernen eines Getaggten im Formular → dessen Teilnahme wird gelöscht,
  falls noch `suggested`; bestätigte bleiben (nur die Person selbst kann
  ablehnen).

### 2.6 Löschen

Wird eine Aktivität gelöscht (MeterMachen oder Strava), wird ihre Teilnahme
gelöscht. Hat die Session danach < 2 bestätigte Teilnahmen, ist sie nicht
mehr echt; hat sie keine Teilnahmen mehr, wird sie gelöscht.

### 2.7 Regeln

Jeder kann nur die eigene Teilnahme ändern. Benachrichtigungs-Hook
`notify(user_id, kind, payload)` wird aufgerufen bei neuem Vorschlag, neuem
Tag und Auto-Match. In diesem Projekt ein No-op; Push ist ein eigenes
Teilprojekt.

## Teil 3 — Feed, Profil, Achievements

### 3.1 Feed-Event `together`

- Entsteht, wenn eine Session echt wird. `user_id = None`,
  `season_year` aus dem Aktivitätsdatum, Payload: Teilnehmer (IDs, Namen),
  `km_together`, `share`, Kategorie der ersten Aktivität.
- Kommt jemand dazu → Payload des bestehenden Events wird aktualisiert, kein
  neues Event („Erik, Anna & Tom – 8,2 km zusammen“).
- Session nicht mehr echt → Event wird entfernt.
- Normale Aktivitäts-Events bleiben unverändert, Reaktionen funktionieren wie
  gewohnt.
- Backfill (`emit_feed=False`): Matching läuft, Achievements zählen, aber
  kein Feed-Event.

### 3.2 Profil

- Neue Karte „Trainingspartner“ auf `Profil.tsx` unter den Achievements:
  „Häufigster Trainingspartner: Anna (7×, 54 km)“ und Liste aller Partner
  mit Anzahl echter Sessions und km, sortiert nach Anzahl. Für alle
  eingeloggten Nutzer sichtbar.
- Im eigenen Profil zusätzlich: Schalter „Gemeinsame Aktivitäten erkennen“
  (`detect_together`) und die Liste offener Vorschläge.

### 3.3 Achievements

Gezählt über echte Sessions mit eigener `confirmed`-Teilnahme, all-time wie die
bestehenden, nie zurückgenommen. `check_unlocks` wird für **alle**
Teilnehmer aufgerufen, wenn eine Session echt wird oder wächst.

| Key | Titel | Bedingung | Emoji |
|---|---|---|---|
| `together_first` | Trainingspartner | 1. echte Session | 🤝 |
| `together_dream_team` | Dream Team | 10 Sessions mit derselben Person | 💞 |
| `together_pack` | Rudel | eine Session mit ≥ 4 bestätigten Teilnehmern | 🐺 |
| `together_social_butterfly` | Social Butterfly | Sessions mit 5 verschiedenen Personen | 🦋 |

Achievements nur bei aktivem Add-on `together` sichtbar und prüfbar.

## Teil 4 — API, Frontend, Rollout

### 4.1 Add-on

`together` wird wie `sidebets`/`challenges` geseedet, Standard aus. Aus heißt:
kein Matching, keine UI, keine Together-Achievements. `ActivityTrack` (Teil 0)
wird trotzdem geschrieben.

### 4.2 Migration (`db.py`)

- `ALTER TABLE "user" ADD COLUMN detect_together BOOLEAN NOT NULL DEFAULT 1`
- Neue Tabellen über `create_all`: `ActivityTrack`, `StravaIgnored`,
  `TrainingSession`, `SessionParticipant`.
- Test in `test_migration.py`.

### 4.3 API (`routers/together.py`, hinter Add-on-Check)

- `GET /together/suggestions`: eigene offene Vorschläge und Tags (inkl.
  Kandidaten-Aktivitäten vom Tag ±1 für Tags)
- `POST /together/participants/{id}/confirm`: optionaler Body
  `{activity_id}` (Pflicht bei Tags ohne Aktivität)
- `POST /together/participants/{id}/decline`: auch Undo für Auto-Matches
- `GET /together/partners/{user_id}`: Partner-Statistik fürs Profil
- `PATCH /users/me`: Feld `detect_together`
- Aktivität anlegen/bearbeiten: optionales `partner_ids: list[int]`
- `ActivityOut.together: {session_id, participant_id, partners,
  km_together} | null` für Badge und Undo

Fehler: fremde Teilnahme → 404; fremde oder schon verknüpfte `activity_id`
→ 400; Partner mit `detect_together=False` → 400.

### 4.4 Frontend (`components/together/`)

- `SuggestionsBanner` (Feed): „N offene Zusammen-Vorschläge – ansehen“
- `SuggestionList` (eigenes Profil): Vorschläge ✅/❌, Tags mit Verknüpfen /
  Neu anlegen / Ablehnen
- `PartnerCard` (Profil)
- `TogetherBadge` (Aktivitätszeile): „👥 mit Anna · 8,2 km zusammen“ und
  „War ich nicht dabei“ für die eigene Aktivität
- `PartnerPicker` (Aktivitätsformular): „Mit wem?“
- Feed-Renderer für Typ `together`
- `Regeln.tsx`: Abschnitt zur Erkennung und den Schwellen
- `Datenschutz.tsx`: Streckendaten werden verglichen und nach 48 h gelöscht;
  Opt-out; Nur-ich-Aktivitäten werden einbezogen, Routen nie angezeigt.

### 4.5 Tests (TDD)

- `test_together_geo.py`: Polyline-Decoding gegen Google-Referenzwerte;
  Overlap für identische Route, halbe Route, Parallelstraße 100 m entfernt,
  gleiche Route rückwärts; Zeitfenster-Überlappung.
- `test_together.py`: Schwellen Auto/Vorschlag/nichts; späte Ankunft des
  Partners; 3er-Gruppe und Session-Merge; Opt-out; Undo entfernt Feed-Event;
  kein erneuter Vorschlag nach Decline; 14-Tage-Ablauf; manuelles Taggen
  (verknüpfen, neu anlegen, ablehnen); Backfill ohne Feed-Event;
  Achievements für alle Teilnehmer; Add-on aus.
- `test_strava.py`: Ignore-Liste (Löschen → Backfill bringt sie nicht
  zurück); `update` mit und ohne MeterMachen-Bearbeitung; `update` für
  unbekannte Aktivität; `delete`-Webhook; Geo-Cleanup nach 48 h.
- Vitest für die neuen Komponenten.

### 4.6 PR-Aufteilung

1. Strava-Sync-Grundlage (Teil 0)
2. Together-Backend (Teile 1–3 Backend, 4.1–4.3)
3. Together-Frontend (4.4)

## Außerhalb des Umfangs

- **Push-Benachrichtigungen:** eigenes Teilprojekt (Service Worker, VAPID,
  `PushSubscription`, iOS nur als Home-Screen-App). Füllt `notify` aus 2.7.
- Wetten-Anbindung, Team-km-Rangliste.
- Strava-Streams (Option D) für Grenzfälle.

## Risiken

- **Strava-API-Bedingungen:** seit Ende 2024 eingeschränkte Anzeige von
  Strava-Daten eines Nutzers für andere. Gezeigt werden nur Partner, km und
  Anteil, nie Routen; dennoch vor dem Freischalten des Add-ons die
  Bedingungen prüfen.
- Opt-out statt Opt-in und Einbezug von Nur-ich-Aktivitäten sind bewusste
  Entscheidungen; in der Datenschutzseite transparent machen.
