# Strava Auto-Backfill beim ersten Connect — Design

**Datum:** 2026-06-13
**Branch:** `feature/strava-auto-backfill`
**Status:** Design abgenommen, bereit für Implementierungsplan

## Problem / Ziel

Aktuell synchronisiert die Strava-Integration nur **neue** Aktivitäten über den
Webhook (`aspect_type: "create"`). Verbindet ein Nutzer sein Strava, bleibt seine
bisherige Historie leer — er muss warten, bis er neue Aktivitäten aufzeichnet.

**Ziel:** Beim erstmaligen Verbinden eines Strava-Accounts werden automatisch alle
Aktivitäten des **laufenden Kalenderjahres** importiert. Das funktioniert für jeden
Nutzer (nicht nur Admin), läuft im Hintergrund und zeigt im UI einen Fortschritt
(„Importiere… X von Y"), gefolgt von einem dezenten Abschluss-Toast.

## Nicht-Ziele (YAGNI)

- Kein Import vergangener Jahre / keiner kompletten Historie (nur laufendes Jahr).
- Kein Update-/Delete-Sync (bleibt wie bisher: nur Neu-Import).
- Kein Auto-Recovery eines abgebrochenen Imports nach Server-Neustart.
- Kein dauerhaftes „Verlauf neu importieren"-Feature im UI.

## Kontext (bestehender Code)

- `app/models.py::StravaConnection` — eine Verbindung pro User (`user_id` unique),
  speichert `athlete_id` + Tokens.
- `app/services/strava.py::handle_webhook_event` — importiert eine Aktivität
  idempotent über `external_id`; nutzt `category_for_sport()` (Sport-Typ → Kategorie)
  und filtert `distance > 0`.
- `app/routers/strava_router.py::callback` — legt bei `conn is None` eine neue
  Verbindung an und leitet auf `/?strava=connected` um.
- `app/routers/strava_router.py::webhook_event` — nutzt bereits `BackgroundTasks`.
- `app/db.py::migrate` — Lightweight-Migration für Bestands-DBs via
  `PRAGMA table_info` + `ALTER TABLE ... ADD COLUMN` (kein Alembic).
- `frontend/src/components/ui/ProfilModal.tsx` — fragt `strava-status` per
  react-query ab, zeigt „Mit Strava verbinden" / „Strava trennen".
- `frontend/src/api/client.ts::StravaStatus` — Typ des Status-Endpoints.

## Multi-User-Hinweis (bereits gegeben)

Die Webhook-Subscription ist **App-weit** (eine pro Strava-App). Verbindet ein neuer
Nutzer sein Strava, ordnet `handle_webhook_event` eingehende Events über
`athlete_id == owner_id` dem richtigen User zu. Der Auto-Backfill ergänzt diesen
bereits funktionierenden Pfad lediglich um den initialen Import.

## Architektur (Ansatz A)

Background-Task beim Connect + Fortschritts-State auf der `StravaConnection`.
Import aus der **Summary-Liste** (`/athlete/activities`) → ein API-Call pro 100
Aktivitäten statt ein Detail-Fetch pro Aktivität. Webhook- und Backfill-Pfad teilen
sich einen gemeinsamen Import-Helper.

### Datenmodell

`StravaConnection` erhält drei Felder:

```python
backfill_state: str = "idle"   # "idle" | "running" | "done" | "error"
backfill_total: int = 0        # importierbare Aktivitäten (gemappt & distance>0)
backfill_done:  int = 0        # bereits verarbeitete
```

Migration in `db.py::migrate` (analog zu `strava_sport_types`):

```python
sc_cols = _columns(conn, "stravaconnection")
if "backfill_state" not in sc_cols:
    conn.execute(text("ALTER TABLE stravaconnection ADD COLUMN backfill_state TEXT NOT NULL DEFAULT 'idle'"))
if "backfill_total" not in sc_cols:
    conn.execute(text("ALTER TABLE stravaconnection ADD COLUMN backfill_total INTEGER NOT NULL DEFAULT 0"))
if "backfill_done" not in sc_cols:
    conn.execute(text("ALTER TABLE stravaconnection ADD COLUMN backfill_done INTEGER NOT NULL DEFAULT 0"))
```

(Tabellenname gemäß SQLModel-Default = Klassenname lowercase: `stravaconnection`.
In der Implementierung per `PRAGMA`/`sqlite_master` verifizieren.)

### Gemeinsamer Import-Helper

Kernlogik aus `handle_webhook_event` extrahieren:

```python
def import_activity(session, conn, data: dict) -> bool:
    """Mappt Sport-Typ → Kategorie, prüft Distanz>0 und Idempotenz (external_id),
    legt bei Erfolg eine Activity an. Gibt True zurück, wenn neu importiert."""
```

- `handle_webhook_event`: `fetch_activity(token, id)` → `import_activity(...)`
  (Verhalten unverändert — ein Activity-Detail-Objekt).
- Backfill: ruft `import_activity` mit den Summary-Objekten der Listen-API auf.
  Die Summary enthält die benötigten Felder (`id`, `sport_type`/`type`, `distance`,
  `moving_time`, `name`, `start_date_local`/`start_date`).

### Backfill-Funktion

```python
def backfill_current_year(user_id: int) -> None:
    # Eigene DB-Session (läuft im BackgroundTask).
    # 1. conn laden; falls weg → abbrechen. state="running", done=0, total=0.
    # 2. after = Epoch von datetime(date.today().year, 1, 1).
    #    /athlete/activities?after=...&per_page=100 paginiert holen (Summary).
    # 3. importierbare vorab zählen (gemappter Sport-Typ & distance>0) → total persistieren.
    # 4. je Aktivität: import_activity(...); done++ (periodisch committen).
    #    Vor jeder Iteration prüfen, ob conn noch existiert (Disconnect-Abbruch).
    # 5. state="done". Bei Exception: state="error" (best-effort), bereits Importierte bleiben.
```

- „Laufendes Jahr" ist dynamisch: `date.today().year`.
- `total` zählt nur importierbare Aktivitäten, damit „X von Y" nicht bei
  übersprungenen (ungemappt / Distanz 0) hängenbleibt.
- Idempotenz über `external_id` → erneuter Lauf erzeugt keine Dubletten.

### Auslöser im Callback

In `callback`: Wenn eine **neue** Verbindung entsteht (bisheriger `conn is None`-Zweig),
nach dem Commit `background_tasks.add_task(strava.backfill_current_year, user.id)`
anhängen (`callback` bekommt dafür `BackgroundTasks` injiziert). Bei Re-Connect einer
bestehenden Verbindung passiert nichts Neues. Nach Disconnect (löscht die Connection)
+ Reconnect läuft der Backfill erneut — idempotent, daher unkritisch.

### Status-Endpoint

`/api/strava/status` liefert zusätzlich einen `backfill`-Block, wenn verbunden:

```json
{ "enabled": true, "connected": true, "athlete_id": 123,
  "backfill": { "state": "running", "total": 52, "done": 23 } }
```

## Frontend

- `client.ts`: `StravaStatus` um optionales
  `backfill?: { state: 'idle'|'running'|'done'|'error'; total: number; done: number }`
  erweitern.
- `ProfilModal.tsx`:
  - `strava-status`-Query mit bedingtem Polling:
    `refetchInterval: backfill?.state === 'running' ? 1500 : false`.
  - Anzeige in der Strava-Box:
    - `running` → Spinner + „Importiere… {done} von {total}".
    - sonst → bestehende Buttons (Verbinden / Trennen).
  - Abschluss-Toast: per `useRef` den vorherigen State merken; beim live beobachteten
    Übergang `running → done` mit `total > 0` einmalig `toast('{total} Aktivitäten
    importiert', 'ok')`. Kein Persistieren — öffnet man das Modal erst nach Abschluss,
    kommt kein Toast (bewusst, nicht aufdringlich).
  - Beim Übergang auf `done` die Queries `comparison` und Aktivitäten invalidieren,
    damit Liste/Visualisierung ohne manuelles Neuladen aktualisieren.

## Fehlerbehandlung & Edge-Cases

- **Token-Refresh:** Backfill nutzt `valid_access_token()` → Ablauf während des
  Imports wird automatisch erneuert.
- **Rate-Limit / Strava-Fehler (z.B. 429):** Backfill bricht kontrolliert ab,
  `state="error"`; bereits Importierte bleiben. Erneuter Connect holt nach (idempotent).
- **Server-Neustart mitten im Import:** `state` bleibt „running" in der DB
  (bekannte Einschränkung, kein Auto-Recovery). Erneuter Connect setzt den State sauber neu.
- **Keine importierbaren Aktivitäten:** `total=0` → `state` direkt „done", keine Anzeige,
  kein Toast.
- **Disconnect während laufendem Import:** `disconnect` löscht die Connection; der Task
  bricht beim Existenz-Check zu Beginn der nächsten Iteration ab.

## Tests

**Backend (pytest, httpx gemockt):**
- `import_activity`: Mapping-Treffer/-Fehlschlag, Distanz-0-Filter, Idempotenz über
  `external_id`, Rückgabewert.
- `backfill_current_year`: mehrere Sport-Typen (gemappt/ungemappt), Dublette wird
  übersprungen, `total`/`done`-Verlauf korrekt, Paginierung, `error`-Pfad bei
  httpx-Fehler, Abbruch wenn Connection fehlt.
- Callback: BackgroundTask wird nur bei frischem Connect angehängt, nicht bei
  bestehender Verbindung.
- `/status`: liefert korrekten `backfill`-Block (inkl. ohne Verbindung).
- Bestehende Strava-Tests bleiben grün (Helper-Refactor verhält sich identisch).

**Frontend (vitest):**
- `ProfilModal` rendert „Importiere… X von Y" bei `running`, normale Buttons bei
  `idle`/`done`.
- Toast feuert beim Übergang `running → done` (mit `total > 0`), nicht bei direktem
  Öffnen im `done`-Zustand.

## Betroffene Dateien

- `backend/app/models.py` — `StravaConnection`-Felder.
- `backend/app/db.py` — Migration der drei Spalten.
- `backend/app/services/strava.py` — `import_activity`-Helper, `backfill_current_year`,
  Refactor von `handle_webhook_event`.
- `backend/app/routers/strava_router.py` — Callback-Trigger, `status` um `backfill` erweitern.
- `backend/app/schemas.py` — ggf. Status-Response-Schema.
- `backend/tests/test_strava.py` — neue Tests.
- `frontend/src/api/client.ts` — `StravaStatus`-Typ.
- `frontend/src/components/ui/ProfilModal.tsx` — Anzeige, Polling, Toast, Invalidierung.
- `frontend/src/components/ui/ProfilModal.test.tsx` — Tests.
- `README.md` — kurzer Hinweis auf den Auto-Backfill.
