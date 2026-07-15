# Design: Regeln-Reiter, Achievements-Ausbau, Uhrzeit-Erfassung, Wetten-Blackboard

**Datum:** 2026-07-16 · **Status:** vom User freigegeben (Design), Spec-Review ausstehend

## Ziel

Vier Features vor bzw. kurz nach dem Challenge-Start am 20.07.2026:

1. Regeln-Reiter (statisch)
2. Achievements: Bronze/Silber/Gold-Stufen, Erster-Bonus, drei Hidden Achievements
3. Startzeit von Aktivitäten erfassen (Datengrundlage für spätere News-/Statistik-Auswertung)
4. Blackboard im Wetten-Tab („wer wettet gegen wen“)

**Nicht in diesem Umfang:** News-Reiter/Wochenbericht, Sportart-Filter im Vergleich,
PWA, Statistik-Auswertungen. Die Uhrzeit wird nur *gesammelt*, nicht ausgewertet.

**Auslieferung:** zwei PRs — PR 1: Regeln + Uhrzeit + Blackboard, PR 2: Achievements-Ausbau.

---

## 1. Regeln-Reiter

Nur Frontend.

- Neue Seite `frontend/src/pages/Regeln.tsx`, neuer Tab „Regeln“ in
  `components/ui/tabs.ts`, sichtbar für alle eingeloggten Nutzer (kein Add-on-Gate).
- Inhalt statisch im Code, Abschnitte:
  1. Worum geht es (Jahresziel, gemeinsame Challenge)
  2. Zeitraum (Start 20.07.2026, Warm-up-Phase davor → Archiv)
  3. Wertung: MM = gewertete km; **Faktoren-Tabelle wird live aus `GET /api/categories`
     geladen** (Sportart, Icon, Faktor), damit Admin-Änderungen automatisch stimmen
  4. Einträge: manuell oder via Strava; Fairness-Grundsätze
  5. Wetten-Kurzfassung (nur sichtbar, wenn Add-on `sidebets` aktiv ist)
- Regeltext: Entwurf durch Claude auf Basis der bestehenden Challenge-Logik,
  Korrektur durch Rick im PR-Review.

## 2. Achievements-Ausbau

### 2.1 Persistenz: Tabelle `AchievementUnlock`

```
AchievementUnlock:
  id            int PK
  user_id       int FK user.id, index
  key           str            # z. B. "stufe_rad_gold"
  unlocked_at   datetime (UTC)
  context_json  str = "{}"     # z. B. {"km": 4003.2} oder {"von": "2026-08-01", "bis": "2026-08-07"}
  UNIQUE (user_id, key)
```

- Migration im bestehenden `db.py migrate()`-Muster (`CREATE TABLE IF NOT EXISTS`
  via SQLModel-Metadata + Test in `tests/test_migration.py`).
- Fortschritt wird weiterhin live berechnet (wie bisher in
  `routers/achievements.py`). Beim ersten Erreichen wird der Unlock gespeichert.
  **Einmal freigeschaltet bleibt freigeschaltet**, auch wenn Aktivitäten später
  gelöscht/geändert werden.

### 2.2 Unlock-Prüfung (neuer Service `services/achievements.py`)

Zentrale Funktion `check_unlocks(session, user_id)`:

- aufgerufen nach Aktivitäts-Create/Update (manueller Endpoint, Strava-Webhook,
  Strava-Backfill) für den betroffenen Nutzer,
- zusätzlich beim `GET /api/achievements` für den anfragenden Nutzer
  (nötig für „Platz 1 gehalten“, das ohne eigene Aktivität eintreten kann),
- idempotent über den Unique-Constraint (Insert-or-ignore).

Die bestehende Berechnungslogik (Buckets, `bucket_for_category`) wird
wiederverwendet; der Router delegiert an den Service.

### 2.3 Neue Definitionen

**Stufen (rohe km, wie bisherige Achievements):**

| Disziplin | Bronze | Silber | Gold |
|---|---|---|---|
| Rad | 1000 | 2500 | 4000 |
| Laufen | 250 | 500 | 1000 |
| Schwimmen | 100 | 250 | 400 |

Keys: `stufe_{rad|lauf|schwimm}_{bronze|silber|gold}` (9 Unlock-Keys).

**Erster-Bonus:** `erster_gold_{rad|lauf|schwimm}` — erhält genau die Person,
deren Gold-Unlock der jeweiligen Disziplin zuerst **persistiert** wurde
(`unlocked_at`, nicht Aktivitätsdatum → Zurückdatieren klaut nichts).
Vergabe im selben `check_unlocks`-Lauf direkt nach dem Gold-Insert.

**Hidden Achievements (vor Freischaltung als „???“-Karte):**

| Key | Bedingung |
|---|---|
| `kletterkoenig` | ≥ 1000 Höhenmeter (Summe `elevation_m`) an einem Kalendertag |
| `hattrick` | ≥ 3 Aktivitäts-Einträge an einem Kalendertag |
| `wochenkoenig` | alleiniger Platz 1 der gewerteten km (gleiche Rangberechnung wie Rennen-Tab inkl. `km_factor`) an 7 aufeinanderfolgenden Kalendertagen, frühestens ab Challenge-Start (`Season.start_date`); Gleichstand zählt nicht; geprüft gegen den aktuellen Datenstand |

### 2.4 API

`GET /api/achievements` liefert weiterhin eine Liste, `AchievementOut` erweitert um:

- `hidden: bool` — bei nicht freigeschalteten Hidden Achievements werden
  `title`/`description`/`icon`/`parts` maskiert (Titel `"???"`, leere Parts,
  `progress = 0`),
- `tier: "bronze" | "silber" | "gold" | null` und `discipline: str | null`
  für die Stufen-Achievements (Frontend gruppiert damit),
- `unlocked_at: datetime | null`.

### 2.5 UI (`pages/MeineAktivitaeten.tsx`, Bereich Achievements)

- Bestehende Karten bleiben.
- **Eine Karte pro Disziplin** für die Stufen: Bronze/Silber/Gold-Badges
  (erreicht = farbig, sonst grau) + Fortschrittsbalken zur nächsten Stufe.
- Erster-Bonus als normale (nicht versteckte) Karte pro Disziplin mit Hinweis
  „bekommt nur die erste Person“. Zusatzfeld `claimed: bool` in der API: ist der
  Bonus schon an jemand anderen vergeben, zeigt die Karte „bereits vergeben“
  (ohne Namen — der Endpoint bleibt personenbezogen).
- Hidden: graue „???“-Karte ohne Beschreibung; nach Freischaltung normale
  Karte mit Titel, Beschreibung und Datum. Freischaltung ist nur für die
  jeweilige Person sichtbar (kein globaler Spoiler).

## 3. Uhrzeit-Erfassung

- Neue Spalte `Activity.start_time` (`TIME`, nullable) + Migrationseintrag.
- **Strava:** Import/Webhook/Backfill speichern künftig den Zeitanteil von
  `start_date_local`. Bereits importierte Aktivitäten bleiben ohne Zeit
  (nachziehbar per Disconnect/Reconnect — bewusst kein automatisches Nachziehen).
- **Manuell:** optionales Feld „Startzeit“ (HH:MM) im Eintrag-Formular;
  `ActivityCreate`/`ActivityPatch`/`ActivityOut` entsprechend erweitert.
  Leer = `null`, keine Pflicht, keine Defaults.
- Keine Auswertung in diesem Umfang.

## 4. Wetten-Blackboard

- **Gating:** neues Add-on `blackboard` (Muster wie `sidebets`), beim
  `migrate()`/Startup geseedet falls nicht vorhanden: `enabled = true`,
  `active_from` = derselbe Wert wie beim bestehenden `sidebets`-Add-on
  (Wetten-Scharfschaltung am 20.07.2026). Damit über die
  bestehende Admin-Add-on-Verwaltung manuell schaltbar. Sichtbar nur, wenn
  zusätzlich der Wetten-Tab selbst sichtbar ist (`sidebets` aktiv).
- **UI:** Unterbereich „Blackboard“ in `pages/Wetten.tsx` (eigener Abschnitt
  oder Segment-Umschalter, passend zum Bestand):
  - zeigt **alle offenen und laufenden** Wetten aller Nutzer als kompakte Zeilen:
    Teilnehmer (Avatare/Namen, bei Duellen „A ⚔️ B“), Wett-Typ, Titel, Einsatz,
    Zeitraum/Ende,
  - Filter: Person (Dropdown) und Wett-Typ (Dropdown/Chips),
  - Datenquelle: bestehendes `GET /api/bets` — **kein neuer Endpoint**.

## Fehlerbehandlung & Randfälle

- Unlock-Insert bei Race (Webhook + gleichzeitiger Seitenaufruf): Unique-Constraint
  fängt Doppel ab, Fehler wird geschluckt (insert-or-ignore).
- `wochenkoenig`: Rückdatierungen ändern die Historie; geprüft wird immer gegen den
  aktuellen Datenstand. Bereits vergebene Unlocks werden nie zurückgenommen.
- Aktivitäten ohne Kategorie-Bucket (unbekannte Kategorie) zählen wie bisher nur
  für „gesamt“-Ziele, `hattrick` zählt alle Einträge, `kletterkoenig` alle
  `elevation_m`.
- `start_time` wird nirgends vorausgesetzt — alle Anzeigen funktionieren mit `null`.

## Tests

- **Migration:** neue Spalte + neue Tabelle + Add-on-Seed, zweifacher Lauf idempotent.
- **Unlock-Service:** Stufen-Grenzen, Erster-Bonus (zwei Nutzer, Reihenfolge der
  Persistierung entscheidet), `kletterkoenig`/`hattrick` (Tagesgrenzen),
  `wochenkoenig` (7-Tage-Fenster, Gleichstand, Start erst ab `Season.start_date`),
  Idempotenz, Unlock bleibt nach Aktivitäts-Löschung.
- **API:** Maskierung der Hidden Achievements, `start_time` Roundtrip
  (create/patch/out), Strava-Import setzt Zeit.
- **Frontend:** bestehende Lint-/Build-Checks; Blackboard-Filterlogik als
  Komponententest, falls im Bestand üblich (sonst manueller Check).
