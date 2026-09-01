# Design-Spec: Kategorie-Faktoren ab Stichtag ändern (zeitversionierte Multiplikatoren)

**Datum:** 2026-09-01
**Status:** Vom Admin (Erik) im Brainstorming abgenommen.

## Ziel

Der Admin kann den Multiplikator einer Kategorie ändern, ohne dass sich
bereits erbrachte Leistungen umrechnen. Beispiel: Schwimmen zählt bis zum
31.08.2026 mit ×30, ab dem 01.09.2026 mit ×25. Maßgeblich ist das
**Aktivitätsdatum**: Eine Schwimmeinheit vom 31.08. zählt ×30, auch wenn sie
erst am 02.09. eingetragen oder von Strava importiert wird.

## Nicht-Ziele

- Kein Versionieren von `User.km_factor` (Admin-Handicap). Derselbe
  Mechanismus ließe sich später wiederverwenden; jetzt YAGNI.
- Keine Neuberechnung eingefrorener Ergebnisse: Challenge-`result_json`,
  aufgelöste Wetten und persistierte Feed-Events bleiben unangetastet.
- Kein Umbau des Seeds: Die Änderung Schwimmen ×25 ab 01.09.2026 legt der
  Admin nach dem Deploy im Admin-Panel an (kein Code/Seed-Eintrag).

## Datenmodell

Neue Tabelle `CategoryFactorChange`:

| Spalte        | Typ            | Bedeutung                              |
| ------------- | -------------- | -------------------------------------- |
| `id`          | int PK         |                                        |
| `category_id` | FK category.id |                                        |
| `factor`      | float > 0      | neuer Faktor                           |
| `valid_from`  | date           | erster Tag, ab dem der Faktor gilt     |
| `created_at`  | datetime       | Audit                                  |

Unique-Constraint auf (`category_id`, `valid_from`).

`Category.factor` bleibt bestehen und ist der **Ur-Faktor**: Er gilt für alle
Aktivitätsdaten vor dem ältesten `valid_from` der Kategorie. Für ein Datum D
gilt der Eintrag mit dem jüngsten `valid_from` ≤ D, sonst der Ur-Faktor.
Jeder Fakt ist genau einmal gespeichert; der „heute gültige Faktor" wird
berechnet, nie persistiert (bewusste Entscheidung gegen eine normalisierte
Nur-Perioden-Tabelle: die bräuchte Daten-Backfill + `DROP COLUMN` in den
handgeschriebenen SQLite-Migrationen; Spalte behalten-aber-ignorieren wäre
echte Redundanz).

Migration in `db.py`: nur `CREATE TABLE` (via `SQLModel.metadata.create_all`),
kein Backfill.

## Rechenkern: `services/factors.py`

Neues Modul mit `FactorResolver`:

- `FactorResolver.load(session)` lädt alle Kategorien und Änderungen einmal.
- `resolver.factor(category_id, datum) -> float` — Ur-Faktor oder jüngste
  Änderung ≤ Datum.
- `resolver.mm(activity) -> float` — `distance_km * factor(category_id, date)`.

Alle Live-Berechnungsstellen stellen von `distance_km * cat.factor` auf den
Resolver um: `services/achievements.py`, `services/bets.py`,
`services/bet_metrics.py`, `services/challenges.py`, `services/feed.py`,
`services/points.py`, `routers/comparison.py`. Der Resolver wird pro
Request/Aufruf einmal geladen (wenige Kategorien und Änderungen — reiner
Dict-Lookup, keine Performance-Frage).

## API

### `GET /api/categories` (öffentlich, wie bisher)

`CategoryOut` erweitert:

- `factor`: der **heute gültige** Faktor (berechnet). Dadurch zeigt das
  restliche Frontend (Regeln-Tabelle, Formulare) automatisch den richtigen
  Wert.
- `base_factor`: der Ur-Faktor (fürs Admin-Panel).
- `pending_changes`: Liste `[{id, factor, valid_from}]` mit `valid_from` >
  heute, aufsteigend.
- `history`: Liste `[{id, factor, valid_from}]` mit `valid_from` ≤ heute,
  aufsteigend (wirksam gewordene Änderungen).

### `POST /api/categories/{id}/factor-changes` (Admin)

Body `{factor, valid_from}`. Validierung:

- `factor` > 0.
- `valid_from` ≥ heute (nicht rückwirkend — Kern der Anforderung).
- (`category_id`, `valid_from`) doppelt → 409 („Für diesen Tag existiert
  schon eine Änderung — erst löschen").

### `DELETE /api/categories/{id}/factor-changes/{change_id}` (Admin)

Nur solange `valid_from` ≥ heute (Vertipper am Anlagetag korrigierbar);
ältere Einträge sind Historie → 409.

### `PATCH /api/categories/{id}` (Bestand)

`factor` bleibt als **Notfall-Korrektur des Ur-Faktors** erlaubt (z.B.
Tippfehler), verschwindet aber aus dem Admin-UI, weil es rückwirkend wirkt.
Ur-Faktor und Änderungszeilen regeln disjunkte Zeiträume — kein Konflikt.

## Frontend

### Admin-Panel (Kategorien-Sektion)

Das editierbare Faktor-Feld wird ersetzt durch:

- Anzeige des aktuellen Faktors inkl. anstehender Änderung, z.B.
  „×30 → ab 01.10. ×25".
- Button „Faktor ändern": neuer Wert + Gültig-ab-Datum (Default heute).
- Liste anstehender Änderungen mit Löschen-Knopf.
- Historie (wirksam gewordene Änderungen + Ur-Faktor) aufklappbar.

### Regeln-Seite (öffentlich)

Zeigt wie bisher `factor` (jetzt automatisch der heute gültige Wert). Hat
eine Kategorie `pending_changes`, erscheint in der Zeile ein Hinweis:
„ab 01.10.2026: ×25".

## Tests

Backend (pytest):

- Resolver: vor/nach Stichtag, mehrere Änderungen, Ur-Faktor ohne Änderungen,
  Änderung genau am Aktivitätsdatum.
- API: rückwirkendes Anlegen verboten, Duplikat-409, Löschen nur ≥ heute,
  Nicht-Admin 403, `CategoryOut` liefert effektiven Faktor + Listen.
- Regression: Aktivität vom 31.08. zählt ×30, vom 01.09. ×25 — geprüft in
  Comparison und Wett-Metriken.

Frontend (vitest): Admin-Formular (Anlegen/Löschen, Validierung), Regeln-Zeile
mit Änderungs-Hinweis.

## Betrieb

Nach dem Merge/Deploy legt der Admin an: Schwimmen, Faktor 25, gültig ab
01.09.2026. Wegen der Nicht-rückwirkend-Regel muss das am 01.09. passieren;
falls der Deploy später kommt, ist der Notfall-PATCH der Ausweg (bewusst
manuell, kein Automatismus).
