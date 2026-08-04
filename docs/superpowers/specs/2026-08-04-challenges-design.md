# Challenges — Design

**Datum:** 2026-08-04
**Status:** freigegeben
**Add-on-Gate:** `challenges`

## Worum es geht

Zeitlich begrenzte Wettbewerbe innerhalb der Gruppe, unabhängig von der
Jahreswertung. Anlass ist die laufende Aktion „August bis Stuttgartlauf": wer im
August 300 MM sammelt, kommt in die Verlosung eines Startplatzes.

Challenges ersetzen die Wetten im Tab-Bereich. Die Wetten werden über ihr
Add-on abgeschaltet, ihr Code bleibt unangetastet im Repo, bis sie überarbeitet
werden.

## Namensklärung

Die App nennt die Jahreswertung bisher „Challenge" (Warm-up → Challenge,
„Challenge-Start"). Ab dieser Spec heißt sie in allen **Anzeigetexten**
**Saison**. Das Wort „Challenge" gehört dem hier beschriebenen Feature.

Betroffen sind die deutschen Texte in `Regeln.tsx`, `Vergleich.tsx`,
`WarmupArchiv.tsx`, `season.ts` und den Feed-Rückblicken.

**Code-Bezeichner bleiben unverändert** (`phase="challenge"`,
`points.challenge_start()`, `SIDEBETS_START`). Sie stecken in API-Schemas,
Frontend-Queries und rund einem Dutzend Tests; eine Umbenennung bläht den Diff
auf, ohne für Nutzer etwas zu ändern. Stattdessen bekommen `compute_comparison`
und `points.challenge_start` je einen Kommentar, dass „challenge" dort die
Saison meint. Das ist eine bewusst in Kauf genommene Inkonsistenz zwischen
Anzeige und Code.

## Nicht in v1

- Challenges von Nicht-Admins anlegen lassen (`creator_id` existiert bereits im
  Modell, es fehlt nur die Rechteprüfung)
- Eingeschränkter Teilnehmerkreis (ausgewählte Personen)
- Kopplung an Punkte-Ledger, Wetten oder Achievements
- Automatische Verlosung unter den Qualifizierten — die App ermittelt, wer
  qualifiziert ist; gezogen wird offline

## Datenmodell

Zwei neue Tabellen in `backend/app/models.py`. Beide werden von
`SQLModel.metadata.create_all` angelegt — **kein Eintrag in `db.py:migrate()`
nötig**, da es keine Bestandstabellen zu ändern gibt.

```python
class Challenge(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    creator_id: int = Field(foreign_key="user.id", index=True)
    prize: str | None = None          # freier Text, optional

    mode: str                          # "ziel" | "rangliste"
    target: float | None = None        # mode="ziel": Schwelle
    top_n: int = 1                     # mode="rangliste": gewertete Plätze

    metric: str                        # "mm" | "streak" | "anzahl"
    category_ids_json: str = "[]"      # leer = alle Kategorien
    streak_min_mm: float = 5.0         # nur metric="streak"

    join_mode: str                     # "auto" | "opt_in"
    period_start: date_type
    period_end: date_type

    status: str = "geplant"            # "geplant" | "laufend" | "beendet" | "abgebrochen"
    result_json: str = "{}"            # bei Abschluss eingefroren
    created_at: datetime = Field(default_factory=utcnow)
    resolved_at: datetime | None = None


class ChallengeParticipant(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("challenge_id", "user_id", name="uq_challenge_user"),
    )
    id: int | None = Field(default=None, primary_key=True)
    challenge_id: int = Field(foreign_key="challenge.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    joined_at: datetime = Field(default_factory=utcnow)
```

### Entscheidungen im Modell

**Kategorie-Filter ist eine eigene Achse, keine eigene Metrik.** `category_ids_json`
wirkt auf alle drei Metriken. Dadurch ergibt sich „10 Tage am Stück laufen" aus
`metric="streak"` + Kategorie-Filter, ohne Sonderlogik.

**Bei `join_mode="auto"` existieren keine Participant-Zeilen.** Teilnehmerkreis
sind alle Nutzer mit `is_active=True`, zur Lesezeit ermittelt. Andernfalls
müsste bei jedem neuen Mitglied in alle laufenden Challenges nachgetragen
werden. `ChallengeParticipant` gibt es ausschließlich für `opt_in`.

**`streak_min_mm` ist pro Challenge konfigurierbar**, statt der fixen
`STREAK_MIN_MM = 5.0` aus `bet_metrics.py`. Bei einer auf eine Kategorie
gefilterten Streak-Challenge wäre eine feste Hürde von 5 MM/Tag untauglich.

**Add-on:** `challenges` kommt mit `enabled=False` in `KNOWN_ADDONS` in
`seed.py`, damit erst befüllt und dann scharfgeschaltet werden kann.

## Metriken

Neuer Service `backend/app/services/challenges.py` mit einer Metrik-Registry.
Alle Metriken rechnen **ohne `User.km_factor`** — das Admin-Handicap gilt nur im
Saison-Ranking. Eine 300-MM-Hürde soll für alle dieselbe Hürde sein.

| `metric` | Wert | Grundlage |
| --- | --- | --- |
| `mm` | Σ `distance_km × Kategorie-Faktor` im Zeitraum | `bet_metrics.scaled_km`, erweitert um Kategorie-Filter |
| `streak` | längste Serie zusammenhängender Tage mit ≥ `streak_min_mm` | `bet_metrics.longest_streak`, erweitert um Kategorie-Filter und konfigurierbares Minimum |
| `anzahl` | Anzahl Aktivitäten im Zeitraum | neu |

Gewertet wird stets der **komplette Challenge-Zeitraum**, auch für Personen, die
später beitreten (siehe Beitritt). Der Stand wird bei jedem Abruf frisch aus den
Activities berechnet, solange die Challenge nicht eingefroren ist — genau wie
`compute_comparison`. Dadurch ziehen Strava-Nachzügler und nachträgliche
Korrekturen automatisch mit, und es braucht keinen Cron.

### Frühzeitiger Abbruch bei Streaks

Gilt ausschließlich für `mode="ziel"` **und** `metric="streak"`. Pro Person:

```
max_erreichbar = max(beste_serie_bisher, serie_bis_gestern + resttage_ab_heute)
```

Ist `max_erreichbar < target`, gilt die Person sofort als **„nicht mehr
schaffbar"** — sichtbar in der Liste, nicht erst am Ende der Challenge.

Bewusst `serie_bis_gestern` statt `bis heute`: der laufende Tag ist noch offen
und zählt als erreichbar mit.

Bei `mm` und `anzahl` gibt es kein Tageslimit, Unmöglichkeit ist dort nie
beweisbar — die Regel greift nicht. Bei `mode="rangliste"` greift sie ebenfalls
nicht.

## Lebenszyklus

```
geplant ──(heute ≥ period_start)──> laufend ──(Einfrierzeitpunkt)──> beendet
   │                                    │
   └────────── Admin bricht ab ─────────┴──────────────> abgebrochen
```

Alle Übergänge passieren **lazy in `challenges.resolve_due(session)`**,
aufgerufen zu Beginn jedes GET auf `/api/challenges`. Dasselbe Muster verwendet
`bets.py:resolve_due` bereits. Kein Cron, kein Scheduler.

### Einfrieren des Ergebnisses

**Einfrierzeitpunkt:** `period_end + 1 Tag, 06:00` deutscher Zeit.

Umgesetzt mit dem festen Offset `_MESZ = timezone(timedelta(hours=2))`, den
`feed.py`, `achievements.py` und `seed.py` bereits verwenden. Eine im Winter
endende Challenge friert dadurch faktisch um 05:00 Ortszeit ein — dieselbe
Ungenauigkeit, die der Bestandscode bewusst in Kauf nimmt.

Zwischen `period_end` und dem Einfrieren wird der Stand **weiter live
gerechnet** und im Frontend als **„vorläufig"** ausgewiesen. Das Fenster deckt
genau zwei reale Fälle ab: einen noch ausstehenden Strava-Sync und eine
Aktivität kurz vor Mitternacht, die am Folgetag eingetragen wird.

Beim Einfrieren wird das Ergebnis einmalig berechnet und geschrieben:

```json
{
  "entries": [
    {"user_id": 3, "value": 412.0, "rank": 1, "geschafft": true},
    {"user_id": 7, "value": 187.4, "rank": 2, "geschafft": false}
  ],
  "gewinner_ids": [3]
}
```

`gewinner_ids` ist bei `mode="ziel"` die Liste aller Qualifizierten, bei
`mode="rangliste"` alle Personen mit `rank <= top_n`. Ab Status `beendet` wird
ausschließlich `result_json` gelesen, nicht mehr gerechnet.

**Gleichstand:** Personen mit identischem Wert erhalten denselben `rank`, der
nächste Rang wird entsprechend übersprungen (1, 2, 2, 4). Bei `mode="rangliste"`
kann dadurch mehr als `top_n` Gewinner geben — das ist gewollt, ein
Stichentscheid per Zufall wäre bei einem realen Preis schlechter als geteilte
Plätze.

**Inaktive Nutzer** (`is_active=False`) werden weder gewertet noch angezeigt,
auch wenn eine `ChallengeParticipant`-Zeile existiert. Beim Einfrieren fließen
sie nicht in `entries` ein.

Es gibt **keinen Recompute-Endpunkt**. Eine Korrektur, die später als der
Einfrierzeitpunkt eintrifft, ändert das Ergebnis nicht mehr. Das ist gewollt:
Ende der Challenge ist Ende der Challenge.

### Beitritt

- Nur bei `join_mode="opt_in"`. Bei `auto` sind alle aktiven Nutzer dabei.
- Beitritt ist **ab dem Anlegen bis `period_end`** möglich, also auch schon im
  Status `geplant`.
- Gewertet wird immer der **komplette Zeitraum**, auch rückwirkend vor dem
  Beitritt. Niemand wird benachteiligt, weil er die Challenge spät entdeckt.
- Austritt ist möglich, solange die Challenge `laufend` ist.

### Bearbeiten

| Feld | Änderbar |
| --- | --- |
| `title`, `description`, `prize` | jederzeit |
| `mode`, `target`, `top_n`, `metric`, `category_ids`, `streak_min_mm`, `period_start`, `period_end`, `join_mode` | nur solange `status="geplant"` |

Wertungsregeln während der Laufzeit zu ändern wäre das Erste, worüber sich
jemand zu Recht beschwert.

## API

Router `backend/app/routers/challenges.py`, Prefix `/api/challenges`, komplett
hinter `Depends(require_addon("challenges"))`.

| Endpunkt | Recht | Zweck |
| --- | --- | --- |
| `GET /api/challenges` | Login | Liste mit eigenem Stand; ruft vorab `resolve_due`. Liefert `geplant`, `laufend`, `beendet` — **`abgebrochen` wird nicht ausgeliefert** |
| `GET /api/challenges/{id}` | Login | Detail inkl. Stand aller Teilnehmer |
| `POST /api/challenges/{id}/join` | Login | Beitreten, idempotent |
| `DELETE /api/challenges/{id}/join` | Login | Austreten |
| `POST /api/challenges` | Admin | Anlegen |
| `PATCH /api/challenges/{id}` | Admin | Bearbeiten |
| `DELETE /api/challenges/{id}` | Admin | Abbrechen (Status `abgebrochen`, keine Löschung) |

### Fehlerfälle

| Fall | Code |
| --- | --- |
| Beitritt zu `join_mode="auto"` | 409 |
| Beitritt nach `period_end` | 409 |
| Austritt aus nicht laufender Challenge | 409 |
| Wertungsregeln an nicht mehr `geplant`er Challenge ändern | 409 |
| `period_end < period_start` | 422 |
| `period_end` liegt in der Vergangenheit (beim Anlegen) | 422 |
| `mode="ziel"` ohne `target` | 422 |
| `mode="rangliste"` mit `top_n < 1` | 422 |
| `metric="streak"` mit `streak_min_mm <= 0` | 422 |
| unbekannte `category_ids` | 422 |
| Add-on aus oder nicht vorhanden | 404 (`require_addon`) |
| Challenge nicht gefunden | 404 |

## Frontend

| Datei | Inhalt |
| --- | --- |
| `components/ui/tabs.ts` | Neuer Tab `{ to: '/challenges', label: 'Challenges', icon: 'pokal', addon: 'challenges' }`. Der Wetten-Eintrag bleibt unverändert stehen und verschwindet, sobald `sidebets` ausgeschaltet wird. |
| `App.tsx` | Route `/challenges` |
| `pages/Challenges.tsx` | Übersicht (Aufbau siehe unten) |
| `components/challenges/ChallengeHeroCard.tsx` | Große Karte für laufende Challenges, an denen man teilnimmt |
| `components/challenges/ChallengeInvite.tsx` | Einladungsblock für offene `opt_in`-Challenges |
| `components/challenges/ChallengeRow.tsx` | Kompakte Zeile für geplante und beendete Challenges |
| `components/challenges/ChallengeDetail.tsx` | Detailansicht |
| `pages/Admin.tsx` | Abschnitt „Challenges" zum Anlegen und Bearbeiten |

`pokal` ist in `ICON_KEYS` (`db.py`) bereits vorhanden.

### Aufbau der Übersicht

Vier Abschnitte, in dieser Reihenfolge:

1. **„Du bist dabei"** — laufende Challenges, an denen man teilnimmt, als
   horizontal wischbare Hero-Karten mit Punkt-Indikator. Sortiert nach
   `period_end` aufsteigend, die zuerst endende zuerst. Jede Karte zeigt
   Titel, eigenen Stand groß, Fortschrittsbalken, Restzeit, eigenen Platz und
   den Preis.
2. **„Mitmachen?"** — offene `opt_in`-Challenges, denen man noch nicht
   beigetreten ist, als Block mit gestricheltem Rand und Beitreten-Knopf. Der
   eigene Abschnitt sorgt dafür, dass eine Einladung nicht in einer Zeilenliste
   untergeht.
3. **„Geplant"** — kompakte Zeilen.
4. **„Beendet"** — kompakte Zeilen mit Gewinner.

Antippen einer Karte oder Zeile öffnet die Detailansicht.

### Detailansicht

Kopf mit Titel, Zeitraum, Wertung im Klartext (z. B. „Ziel: 300 MM aus allen
Sportarten") und Preis. Während des Karenzfensters zusätzlich ein Hinweis
**„vorläufiges Ergebnis"**.

Darunter **eine Zeile pro Teilnehmer** mit Avatar, Name, Wert,
Fortschrittsbalken und Status-Chip:

| Zustand | Chip | Balken |
| --- | --- | --- |
| Ziel erreicht | „geschafft", grün | voll, grün |
| unterwegs | „noch X", neutral | anteilig, Akzentfarbe |
| nicht mehr schaffbar | „nicht mehr", rot | ausgegraut, Zeile abgedunkelt |

Bei `mode="rangliste"` zeigt der Chip stattdessen den Platz, die ersten `top_n`
werden hervorgehoben, und die Balken sind relativ zur Führenden skaliert.

Bewusst kein Podest und keine Bahnen-Darstellung: die Liste skaliert auf
beliebig viele Teilnehmer, braucht kein Querscrollen und stellt alle drei
Zustände gleich deutlich dar.

## Feed-Integration

Drei neue `FeedEvent`-Typen. `FeedItem.tsx` bekommt die Darstellungen;
Reaktionen funktionieren dadurch automatisch mit.

| `type` | Wann | Payload |
| --- | --- | --- |
| `challenge_start` | `resolve_due`, Übergang nach `laufend` | `challenge_id`, `title`, `prize` |
| `challenge_qualified` | beim Berechnen, sobald jemand `target` erreicht (nur `mode="ziel"`) | `challenge_id`, `title`, `user_id` |
| `challenge_end` | `resolve_due`, beim Einfrieren | `challenge_id`, `title`, `gewinner_ids`, `prize` |

`challenge_qualified` entsteht in einer Lesefunktion, die bei jedem Request
läuft, und muss deshalb **idempotent** sein: vor dem Anlegen wird geprüft, ob
für das Paar (`challenge_id`, `user_id`) bereits ein Event existiert. Dasselbe
Muster nutzt `feed.py` bereits für Achievement-Events.

## Wetten abschalten

Kein Code wird entfernt. Der Admin schaltet das Add-on `sidebets` aus; damit
verschwinden Tab und API. Punktestände, Wetthistorie und `blackboard` bleiben
erhalten, bis die Wetten überarbeitet werden.

## Tests

**`backend/tests/test_challenges.py`**

- alle drei Metriken, jeweils mit und ohne Kategorie-Filter
- `km_factor` wirkt nachweislich **nicht**
- Streak-Abbruch inklusive Grenzfall „der heutige Tag zählt noch als erreichbar"
- Statusübergänge `geplant → laufend → beendet`, Abbruch durch Admin
- Einfrieren: vor dem Zeitpunkt live gerechnet, danach `result_json` unverändert,
  auch wenn nachträglich eine Aktivität eingetragen wird
- `join_mode="auto"` vs. `opt_in`; Beitritt wertet den kompletten Zeitraum
- Beitritt ist idempotent
- Add-on-Gating (404 bei ausgeschaltetem Add-on)
- Gleichstand: gleicher Rang, übersprungener Folgerang, mehr als `top_n` Gewinner
- inaktive Nutzer erscheinen weder im Stand noch in `result_json`
- abgebrochene Challenges tauchen in `GET /api/challenges` nicht auf
- alle Fehlercodes aus der Tabelle oben

**`backend/tests/test_feed.py`**

- die drei neuen Event-Typen
- `challenge_qualified` entsteht bei wiederholten Requests genau einmal

**Frontend**

- `Challenges.test.tsx` — die vier Abschnitte, Beitreten, leerer Zustand
- `ChallengeDetail.test.tsx` — die drei Zustands-Chips, „vorläufig"-Hinweis
- `tabs.test.ts` — Tab erscheint nur bei aktivem Add-on

## Erste Challenge

Die August-Challenge wird nach dem Deploy **im Admin-Bereich angelegt**, nicht
per Seed:

- Titel „August bis Stuttgartlauf"
- `mode="ziel"`, `target=300`, `metric="mm"`, alle Kategorien
- `join_mode="auto"`
- Zeitraum 04.08.2026 – 31.08.2026
- Preis: Verlosung eines Startplatzes
