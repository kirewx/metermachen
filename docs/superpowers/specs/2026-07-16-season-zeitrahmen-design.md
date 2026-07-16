# Design: Season-Zeitrahmen (Start–Ende statt Kalenderjahr)

**Datum:** 2026-07-16 · **Status:** von Rick freigegeben (Ansatz A + 6 Punkte)

## Ziel

Die Challenge läuft vom 20.07.2026 bis zum **Stuttgartlauf 2027** (Mai 2027,
genaues Datum folgt). Die App rechnet aber überall mit dem Kalenderjahr
(`date.year == season.year`, `Season.year == today.year`, `getFullYear()`),
womit am 01.01.2027 Ranking, Punkte, Wetten und Achievements brechen würden.

Season bekommt ein **Enddatum** (im Admin-Panel nachträglich setzbar), und alle
Jahr-Verdrahtungen werden auf ein **Season-Fenster** umgestellt.

**Entschieden (Rick):** Nach dem Saisonende **friert das Ranking ein** —
Aktivitäten bleiben eintragbar/importierbar, zählen aber nicht mehr für
Ranking, Punkte-Einkommen und saisonabhängige Achievements.

**Auslieferung:** ein PR.

---

## 1. Modell & Migration

- Neue Spalte `Season.end_date` (`DATE`, nullable) + Migrationseintrag im
  `db.py migrate()`-Muster. **Kein Backfill** — das Datum trägt Rick ein,
  sobald der Stuttgartlauf-Termin feststeht.
- `SeasonCreate`/`SeasonOut` um `end_date: date | None` erweitert;
  `SeasonPatch` mit dem bestehenden `model_fields_set`-Muster (wie
  `start_date`: explizites `null` löscht das Datum).
- Frontend-Typ `Season` um `end_date: string | null`.

## 2. Fenster-Semantik (zentrale Helper)

Neues Backend-Modul `app/services/season_window.py`:

- `season_window(season) -> (from_date, to_date | None)`:
  - `from_date` = **1. Januar des Season-Jahres** (immer — Warm-up-Aktivitäten
    vor dem Challenge-Start gehören zum Fenster; `start_date` trennt weiterhin
    nur Warm-up von Challenge).
  - `to_date` = `end_date`, falls gesetzt. Fehlt es:
    - Season **mit** `start_date` → **offen** (`None`, kein Ende — „genaues
      Datum folgt" funktioniert damit ohne Platzhalter über den Jahreswechsel),
    - Season **ohne** `start_date` → 31.12. des Season-Jahres (reines
      Kalenderjahr-Verhalten, wie bisher — Fallback für datenlose Seasons).
- `current_season(session) -> Season | None` („aktive Season"):
  1. Season, deren Fenster heute enthält (bei mehreren: spätester Fensterstart),
  2. sonst die zuletzt begonnene (größter Fensterstart ≤ heute),
  3. sonst die als Nächstes beginnende (Countdown-Phase).

Frontend-Pendant `frontend/src/components/ui/season.ts`:

- `aktiveSeason(seasons: Season[]): Season | undefined` — gleiche Regel,
- `saisonLabel(season): string` — `"2026"`, bzw. `"Saison 2026/27"` sobald das
  Enddatum in einem anderen Jahr liegt.

## 3. Fenster-Wertung (Backend-Umbauten)

Alle `a.date.year == year`-Filter werden zu „Datum im Fenster der Season
`year`" (Season per `year`-Pfadparameter; existiert keine → 404 wie bisher
bzw. Kalenderjahr-Fallback, wo heute kein Season-Lookup stattfindet):

- `routers/comparison.py compute_comparison`: Grundfilter
  `from_date <= a.date <= to_date` (bei offenem Ende nur `>= from_date`).
  Warm-up-Phase (`< start`) und Challenge-Phase (`>= start`) bleiben unverändert
  obendrauf. **Freeze:** Aktivitäten nach `end_date` fallen aus dem Grundfilter.
- `routers/activities.py list_my_activities` + `routers/users.py`
  (Personen-Detail): gleicher Fensterfilter statt `date.year == year`.
- `services/points.py`: `challenge_start` → `current_season`; Einkommen zählt
  km im Bereich `start_date <= date <= end_date` (Freeze inklusive).
- `services/achievements.py` + `routers/achievements.py` (Warm-up-Endpoint):
  Season-Lookup `Season.year == today.year` → `current_season(session)`.
  `wochenkoenig` läuft bis `min(heute, end_date)`. Die Stufen-/Hidden-
  Achievements auf rohen km bleiben bewusst all-time (kein Season-Bezug).
- `services/bets.py`: `_season_start` → `current_season`. `ensure_monthly_tip`
  erzeugt **keine neuen Monats-Tipps mehr, deren Monat nach dem Saisonende
  beginnt** (der Monat, in dem das Ende liegt, bekommt noch einen — dessen
  Wertung läuft über den vollen Monat, Wetten haben eigene Zeiträume).
  `create_bet` lehnt zusätzlich `period_start > end_date` ab
  („Wetten gibt es nur bis zum Saisonende").
- `services/strava.py backfill_current_year`: Importstart = **1. Januar des
  Jahres der aktiven Season** statt des heutigen Jahres (ein Neu-Connect im
  Frühjahr 2027 holt sonst die 2026er-km nicht). Der
  `STRAVA_IMPORT_SINCE`-Stichtag verschiebt weiterhin nach hinten.
- `seed.py`: Season wird nur noch angelegt, wenn **gar keine** Season
  existiert (statt „keine für das aktuelle Kalenderjahr") — sonst entstünde am
  01.01.2027 automatisch eine leere Season 2027, die `current_season` stört.

`ComparisonSeen.year` und die API-Pfade (`/api/comparison/{year}`,
`?year=`) behalten `Season.year` als Identifier — kein API-Bruch.

## 4. Frontend-Umbauten

Alle sieben `new Date().getFullYear()`-Stellen nutzen `aktiveSeason(seasons)`
und übergeben `season.year` an die APIs:

- `Layout.tsx` (gestartet-Flag), `CountdownBanner.tsx`, `Vergleich.tsx`
  (year-State-Init), `Wetten.tsx`, `Archiv.tsx`, `MeineAktivitaeten.tsx`,
  `Admin.tsx` (Season-Sektion zeigt die aktive Season).
- Fallback, solange `seasons` noch lädt bzw. leer ist: aktuelles Kalenderjahr
  (heutiges Verhalten).
- **Admin-Panel:** Enddatum-Feld (`type="date"`) neben dem Startdatum in der
  bestehenden Season-Sektion; leer = offen; Löschen schickt `end_date: null`.
- Überschriften mit Jahreszahl (z. B. „Meine Einträge 2026") zeigen
  `saisonLabel(season)` → „Meine Einträge Saison 2026/27", sobald das
  Enddatum gesetzt und jahresübergreifend ist.

## 5. Fehlerbehandlung & Randfälle

- `end_date < start_date` wird von der API mit 422 abgelehnt.
- Ohne gesetztes `end_date` läuft die Season 2026 **offen** weiter (kein
  stiller Abbruch am 31.12.2026); alte/datenlose Seasons verhalten sich exakt
  wie heute (Kalenderjahr).
- Aktivitäten nach dem Saisonende: Eintragen/Import bleibt erlaubt, sie
  erscheinen nur in keiner Season-Ansicht (bis ggf. eine Folge-Season sie
  abdeckt). Punkte-Einkommen und `wochenkoenig` stoppen am Enddatum;
  bestehende Wetten laufen normal aus.
- Zwei Seasons mit überlappenden Fenstern verhindert das Design nicht —
  Verantwortung liegt beim Admin; `current_season` nimmt dann den späteren
  Fensterstart.

## 6. Tests

- **Migration:** neue Spalte, zweifacher Lauf idempotent.
- **season_window/current_season (Unit):** ohne Daten (Kalenderjahr), mit
  Start ohne Ende (offen), mit Ende; aktive Season vor Start (Countdown),
  im Fenster, nach Ende, jahresübergreifend (heute = Feb 2027 → Season 2026).
- **Comparison:** Aktivität vom 15.01.2027 zählt zur Season 2026 (Challenge-
  Phase); Aktivität nach `end_date` zählt nicht (Freeze); Warm-up unverändert.
- **Activities/Users-Listen:** Fensterfilter über die Jahresgrenze.
- **Points:** Einkommen stoppt am Enddatum.
- **Bets:** kein Monats-Tipp für Monate nach Saisonende; `create_bet` lehnt
  Start nach Saisonende ab.
- **Seed:** legt keine zweite Season an, wenn schon eine existiert.
- **Seasons-API:** end_date setzen/ändern/löschen (Patch-Muster), 422 bei
  Ende vor Start.
- **Frontend:** Unit-Tests für `aktiveSeason`/`saisonLabel`; bestehende
  Lint-/Build-Checks; Admin-Feld im Komponententest, falls im Bestand üblich.
