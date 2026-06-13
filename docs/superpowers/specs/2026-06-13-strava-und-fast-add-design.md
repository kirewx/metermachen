# Design: Strava-Integration & Fast-Add-Absicherung

Datum: 2026-06-13
Status: Entwurf zur Freigabe

Dieses Dokument deckt zwei unabhängige Arbeitspakete ab, die zusammen angegangen
werden. Sie werden als **zwei getrennte Implementierungspläne/Branches** umgesetzt:

- **Teil A — Fast-Add-Absicherung:** klein, rein Frontend, schnell mergebar.
- **Teil B — Strava-Integration:** groß, Backend + Frontend + Deployment.

---

## Teil A — Fast-Add-Absicherung

### Problem

Die Schnellwahl-Leiste (`SchnellwahlLeiste.tsx`) rendert die Eingabe-Card sofort
live, der „Eintragen"-Button ist permanent klickbar. Das führt zu zwei Fehlern:

1. **Versehentliches Adden** durch unbeabsichtigtes Klicken in die immer
   präsente Leiste.
2. **Button-Spam** — derselbe Eintrag wird durch Doppelklick/Ungeduld mehrfach
   abgeschickt.

### Lösung

**Maßnahme 1 — Pre-Layer (nur Schnellwahl-Leiste):**

- Die Leiste startet im **sicheren Ruhezustand**: nur ein Button
  **„+ Eintrag hinzufügen"** ist sichtbar.
- Klick → die `SchnellwahlCard` (Variante `kompakt`) klappt inline auf.
- Nach **erfolgreichem** Speichern klappt die Card automatisch wieder auf den
  Button zurück — das verhindert versehentliches Sofort-Nochmal-Adden.
- Ein dezentes „Abbrechen" klappt ohne Speichern zu.
- Der bisherige `offen/zu`-localStorage-Toggle (`schnellwahl-leiste-offen`)
  entfällt; die Leiste startet bewusst immer im Button-Zustand.
- Die Hero-Card auf „Meine Aktivitäten" (`MeineAktivitaeten.tsx`) bleibt
  unverändert direkt nutzbar (kein Pre-Layer).

**Maßnahme 2 — Doppelklick-Schutz (beide Card-Varianten):**

- In `SchnellwahlCard.tsx` ein lokaler `gesperrt`-State.
- Beim Submit sofort sperren; der „Eintragen"-Button ist `disabled` während des
  laufenden Speicherns **und** für das ~700 ms Puls-Bestätigungsfenster danach.
- Bei Fehler (`catch`) wird sofort wieder entsperrt, damit der User es erneut
  versuchen kann.

### Betroffene Dateien

- `frontend/src/components/activities/SchnellwahlLeiste.tsx` (Pre-Layer-Logik,
  localStorage-Toggle entfernen).
- `frontend/src/components/activities/SchnellwahlCard.tsx` (`gesperrt`-State,
  Button `disabled`).

### Tests

- `SchnellwahlLeiste.test.tsx`: Start zeigt nur den Trigger-Button; Klick öffnet
  die Card; erfolgreicher Submit klappt zurück auf den Button; „Abbrechen"
  klappt ohne Submit zu.
- `SchnellwahlCard.test.tsx`: Button ist während des laufenden Submits
  `disabled`; ein zweiter Klick währenddessen löst keinen zweiten `onSubmit` aus;
  nach Fehler ist der Button wieder klickbar.

### Kein Backend-Change.

---

## Teil B — Strava-Integration

### Gewählte Eckpunkte

- **Sync-Mechanismus:** Auto-Sync per **Webhook** (Strava pusht neue
  Aktivitäten).
- **Sport→Kategorie-Mapping:** **Admin** pflegt pro Kategorie die zugeordneten
  Strava-Sportarten. Gilt für alle User gleich.
- **Event-Umfang v1:** nur **`create`**. Update/Delete von Strava werden
  ignoriert. **Lokale Änderungen in MeterMachen gewinnen immer.**
- **Kennzeichnung:** Strava-Einträge bekommen ein dezentes **`Strava`-Badge**;
  manuelle Einträge bleiben ohne Badge.
- **Account-Typ:** funktioniert für **kostenlose** Strava-Accounts. Premium ist
  irrelevant. Scope `activity:read_all` (auch private Aktivitäten).

### Datenmodell

Neue Tabelle (1:1 zum User):

```python
class StravaConnection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    athlete_id: int = Field(index=True)   # Strava owner_id → User-Mapping im Webhook
    access_token: str
    refresh_token: str
    expires_at: datetime                  # UTC, für Token-Refresh
    created_at: datetime = Field(default_factory=utcnow)
```

Erweiterung `Category`:

```python
strava_sport_types: str = "[]"   # JSON-Liste, z.B. ["Run","TrailRun"]
```

`Activity` bleibt strukturell unverändert — die bereits vorhandenen Felder
werden genutzt:

- `source`: `"manual"` (Default) bzw. `"strava"`.
- `external_id`: Strava-Activity-ID als String.
- Dedup: vor dem Anlegen prüfen, ob `(user_id, external_id)` mit
  `source="strava"` bereits existiert.

### Konfiguration (`config.py`)

```
STRAVA_CLIENT_ID
STRAVA_CLIENT_SECRET
STRAVA_WEBHOOK_VERIFY_TOKEN   # frei wählbarer String für die Webhook-Validierung
PUBLIC_BASE_URL               # z.B. https://meter.example.com — für OAuth-Redirect
```

Fehlt eine Pflicht-Variable, ist das Feature **still deaktiviert** (Connect-Button
im Frontend wird ausgeblendet, Router antwortet 404/disabled). Ergänzung in
`.env.example`.

### Service-Modul `services/strava.py`

- **OAuth:** Authorize-URL bauen (`scope=activity:read_all`), Code→Token-Tausch,
  Token-Refresh wenn `expires_at <= now`.
- **API-Client:** Activity-Detail holen (`GET /activities/{id}`) mit dem Token
  des Users (vorher ggf. refreshen).
- **Mapping:** Strava-`sport_type` → Kategorie über `Category.strava_sport_types`.
- **Konvertierung:** Strava-Distanz (Meter) → km; `start_date_local` → `date`.

### Router `routers/strava_router.py`

| Route | Zweck |
|---|---|
| `GET /api/strava/connect` | eingeloggt → Redirect zur Strava-Autorisierung |
| `GET /api/strava/callback` | Code tauschen, `StravaConnection` speichern, zurück ins Frontend |
| `GET /api/strava/status` | verbunden? (athlete_id / Name) |
| `DELETE /api/strava/disconnect` | Verbindung entfernen |
| `GET /api/strava/webhook` | Validierungs-Echo (`hub.challenge`) gegen `verify_token` |
| `POST /api/strava/webhook` | Event entgegennehmen, schnell mit 200 antworten, Verarbeitung via `BackgroundTasks` |

**Webhook-Verarbeitung (`POST`):**

1. Nur `object_type == "activity"` und `aspect_type == "create"` verarbeiten,
   sonst ignorieren.
2. User über `owner_id` (= `athlete_id`) finden. Keine Connection → ignorieren.
3. Activity-Detail über das Token des Users holen.
4. `sport_type` mappen. Keine gemappte Kategorie → ignorieren (geloggt).
5. Distanz ≤ 0 → ignorieren (z.B. Krafttraining).
6. Dedup-Prüfung; sonst `Activity(source="strava", external_id=<id>, ...)`
   anlegen.

**Sicherheit:** Strava signiert Payloads nicht. Ein gefälschter `owner_id` ohne
passende `StravaConnection` wird schlicht ignoriert; der Activity-Fetch läuft nur
mit dem gespeicherten Token des echten Users. Der `verify_token` schützt die
Subscription-Validierung.

### Webhook-Subscription

Einmalige Registrierung der Subscription bei Strava
(`POST /push_subscriptions` mit `callback_url = PUBLIC_BASE_URL + /api/strava/webhook`).
Wird als dokumentierter Admin-/Setup-Schritt (Skript oder Make-/CLI-Befehl)
bereitgestellt, nicht automatisch beim Start.

### Frontend

- **`ProfilModal`:** Abschnitt „Strava" — entweder „Mit Strava verbinden"
  (Redirect auf `/api/strava/connect`) oder „Verbunden · Trennen"
  (Status aus `/api/strava/status`, Trennen via `DELETE /api/strava/disconnect`).
  Abschnitt nur sichtbar, wenn Feature aktiv.
- **API-Surface:** `ActivityOut` (Backend) + `Activity` (Client-Typ) um
  `source: str` erweitern; `_to_out` gibt `source` mit aus.
- **„Meine Aktivitäten":** bei `source === "strava"` ein dezentes `Strava`-Badge
  neben dem Eintrag; manuelle Einträge ohne Badge.
- **Admin-Kategorie-Editor:** Mehrfachauswahl der Strava-Sportarten pro Kategorie
  aus einer kuratierten Liste der Strava-`sport_type`-Enum (Run, TrailRun, Ride,
  GravelRide, MountainBikeRide, Hike, Walk, Swim, …). Schreibt in
  `strava_sport_types`. Ergänzung in `CategoryCreate`/`CategoryPatch` +
  Category-Out + Client-Typ.

### Tests

- Mapping-Funktion: Sportart → Kategorie (Treffer, kein Treffer, mehrere
  Sportarten pro Kategorie).
- Webhook-Handler: `create` legt Activity an; Dedup verhindert Doppel-Import;
  unbekannter `owner_id` / ungemappte Sportart / Distanz 0 → kein Eintrag;
  `update`/`delete` ignoriert.
- Token-Refresh: abgelaufenes Token wird vor dem Fetch erneuert (Strava-Calls
  gemockt).
- Webhook-`GET`: korrektes `hub.challenge`-Echo bei passendem `verify_token`.
- `ActivityOut` enthält `source`.

### Deployment-Voraussetzung

Webhooks brauchen einen **öffentlich über HTTPS erreichbaren**
`POST /api/strava/webhook`. Für lokale Entwicklung Tunnel (z.B. ngrok) +
einmalige Subscription-Registrierung. Wird in der README/Setup-Doku festgehalten.

### Bewusst raus (YAGNI für v1)

- Update-/Delete-Sync von Strava.
- Backfill historischer Aktivitäten beim Verbinden.
- Per-User-Mapping (nur Admin-Mapping).
- Anzeige von Strava-Zusatzdaten (Segmente, Herzfrequenz etc.).
