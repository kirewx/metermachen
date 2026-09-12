# Design spec: Group challenges with seeded draw

**Date:** 2026-09-12
**Status:** Approved by Erik in the brainstorming session.
**Language note:** Code, comments, commits and docs in English. User-facing UI copy stays German.

## Goal

A challenge can be run as a **group challenge**: the admin sets the number of groups, the app draws balanced groups from a seeding list (strongest members spread across groups), and the admin can adjust the groups by hand before the challenge starts. Groups compete on a **per-head** value, so groups of different size are comparable. Everything else (metric, category filter, target or ranking mode, lifecycle, freezing, feed) is reused from the existing challenge feature (spec 2026-08-04).

## Non-goals

- No group streak metric. `metric="streak"` is not allowed for group challenges; a "group streak" (days in a row on which at least one member hit the daily minimum) is a possible later extension.
- No changes to groups once the challenge is running. Injuries or drop-outs are not handled in v1; the admin can cancel and recreate.
- No drag and drop in the group editor. Moves happen via a small select per person, which works reliably on phones.
- No separate feature, model or page. Group challenges are a dimension of `Challenge`.
- No third-party duel bets or monthly achievements (separate backlog items).

## Decisions (from the brainstorming)

| Topic | Decision |
| --- | --- |
| Group value | Per-head average of the active members. `target` is the value **per head**; a group of 4 must reach `4 × target` in total. Ranking mode sorts groups by per-head value. |
| Allowed metrics | `mm` and `anzahl` only, with the usual category filter. `streak` returns 422. |
| Seeding source | The challenge's own metric (metric + category filter, without `km_factor`) over the last `seeding_days` days up to and including yesterday. Default 30 days. |
| Draw | Pots of `group_count` people by seeding rank. Inside each pot the assignment to groups is random. The last, partial pot goes to random distinct groups. |
| Participants | Reuse `join_mode`. `auto`: all active users, drawn immediately on create. `opt_in`: people join, then the admin presses "Auslosen". Late joiners after the draw land in "Nicht zugeordnet" and do not count until placed. |
| Editing | Groups are rule data: editable only while `status="geplant"`. Move, remove, add, rename, redraw. |
| Winner | On finished `mode="ziel"` group challenges the admin may enter either a qualified **group** or a single **person** from a qualified group as the prize winner. |
| Storage | JSON column `groups_json` on `Challenge`, matching the existing `category_ids_json` / `result_json` style. No new tables. |

## 1 · Data model

New columns on `Challenge` (`backend/app/models.py`). `challenge` is an existing table, so `db.py:migrate()` gets `ALTER TABLE ... ADD COLUMN` statements guarded by `_columns()`, like the `user` columns.

```python
team_mode: bool = False
group_count: int | None = None      # required when team_mode, >= 2
seeding_days: int = 30              # window for the seeding list
groups_json: str = "[]"             # [{"id": 1, "name": "Gruppe A", "member_ids": [3, 7, 12]}]
groups_drawn_at: datetime | None = None
```

Group `id`s are small integers unique within the challenge (1..n), assigned by the draw and kept stable while editing. They are not database ids.

### Rules when `team_mode=True`

- `metric` must be `mm` or `anzahl` (422 otherwise). `category_ids`, `mode`, `target`, `top_n`, `join_mode`, `period_*` work as before.
- `target` is per head. A group has reached the target when its per-head value is `>= target`.
- **Group value** = sum of the metric values of the group's *active* members divided by the number of active members. An inactive member drops out of both the sum and the divisor. An empty group (all inactive) has value 0.
- `mode="rangliste"`: groups are sorted by value descending; ties share the rank and the following rank is skipped (1, 2, 2, 4), exactly like today's per-person ranking. The `top_n` best groups win.
- **Participants** are exactly the people listed in a group. Anyone not in a group at start does not take part. `svc.teilnehmer_ids` returns the union of all `member_ids` (active only) for group challenges; before the draw in `opt_in` mode it returns the joined pool so that `bin_dabei` / `kann_beitreten` keep working.
- Joining and leaving are possible **only while `geplant`** (409 otherwise). Leaving removes the person from their group as well.
- `team_mode`, `group_count`, `seeding_days` are rule fields (`REGEL_FELDER`), i.e. only changeable while `geplant`. Changing `group_count` clears `groups_json` and `groups_drawn_at`; the admin has to draw again. Other changes leave the groups untouched.
- **A group challenge without drawn groups does not start.** `resolve_due` skips it (stays `geplant`) until the admin has drawn. Once it starts late, the metric still counts from `period_start`.

### Frozen result

`_einfrieren` adds group data to `result_json`:

```json
{
  "entries": [{"user_id": 3, "value": 412.0, "rank": 1, "geschafft": true}],
  "groups": [
    {"id": 1, "name": "Gruppe A", "member_ids": [3, 7], "sum": 812.0,
     "value": 406.0, "rank": 1, "geschafft": true}
  ],
  "gewinner_ids": [3, 7],
  "gewinner_group_ids": [1],
  "sieger": {"group_id": 1, "gesetzt_am": "..."}
}
```

- `entries` stays the flat per-person list (individual contribution; `rank` and `geschafft` there are per person and only informational).
- `gewinner_ids` = members of all winning groups, so existing consumers (feed, achievements, `ChallengeRow`) keep working with people.
- `sieger` is either `{"group_id": ...}` or `{"user_id": ...}`.

## 2 · Seeding and draw

New module `backend/app/services/challenge_groups.py` so that `services/challenges.py` does not keep growing. Contents:

- `seeding(session, ch, heute) -> list[tuple[int, float]]` — `(user_id, value)` for every user in the pool, sorted by value descending, ties by `user_id`. Window: `[heute - seeding_days, heute - 1]`, computed with the same `metric_value` helpers as the challenge itself but with that window instead of `period_*`. Never uses `km_factor`.
- `pool(session, ch) -> list[int]` — `auto`: all active users; `opt_in`: joined and active.
- `draw(session, ch, heute, rng=random) -> list[dict]` — builds pots of `group_count` from the seeding order; shuffles each pot and assigns member `i` of the pot to group `i`; the partial last pot is assigned to a random sample of distinct groups. Group sizes therefore differ by at most one. Names: existing names by `id` are kept, new groups get "Gruppe A", "Gruppe B", … Writes `groups_json`, `groups_drawn_at`. Raises `ValueError` when the pool has fewer people than `group_count` (→ 422).
- `validate_groups(session, ch, groups) -> list[dict]` — normalises and checks an edited group list: exactly `group_count` groups, non-empty trimmed names, ids unique, every `member_id` at most once, only known **active** users, no empty group. Returns the cleaned list or raises `ValueError` with a German message (→ 422). In `opt_in` mode, people who are placed in a group but never joined get a `ChallengeParticipant` row so that `bin_dabei` is true for them.
- `group_standings(session, ch, heute) -> list[dict]` — per-person values via the existing `metric_value`, aggregated per group: `sum`, `value` (per head), `size`, `rank`, `geschafft`, `members` (per-person entries). Used by `_challenge_out` and `_einfrieren`.

`rng` is injectable so tests can make the draw deterministic.

## 3 · API

All under `/api/challenges`, behind the `challenges` add-on. Existing endpoints are extended; four are new.

| Endpoint | Right | Change |
| --- | --- | --- |
| `POST /api/challenges` | Admin | Body accepts `team_mode`, `group_count`, `seeding_days`. With `team_mode` and `join_mode="auto"` the groups are drawn immediately. |
| `PATCH /api/challenges/{id}` | Admin | The three new fields are rule fields (409 unless `geplant`). Changing `group_count` clears the groups. |
| `POST /api/challenges/{id}/draw` | Admin | (Re)draw the groups from the current pool. Only `team_mode`, only `geplant`. Returns `ChallengeOut`. |
| `PUT /api/challenges/{id}/groups` | Admin | Replace the whole group list: `{"groups": [{"id": 1, "name": "…", "member_ids": [..]}]}`. Only `team_mode`, only `geplant`. Returns `ChallengeOut`. |
| `GET /api/challenges/{id}/seeding` | Admin | `[{"user_id", "display_name", "avatar", "value"}]` for every active user (pool and non-pool), so the editor can show strength next to every name. |
| `PUT /api/challenges/{id}/sieger` | Admin | Body `{"user_id": 7}` **or** `{"group_id": 1}` (exactly one). Group challenges accept both; non-group challenges only `user_id`. |
| `POST` / `DELETE /{id}/join` | Login | Group challenges: 409 unless `geplant`. Leaving also removes the person from their group. |

### New error cases

| Case | Code |
| --- | --- |
| `team_mode` with `metric="streak"` | 422 |
| `team_mode` with `group_count` missing or `< 2` | 422 |
| `seeding_days < 1` | 422 |
| draw with fewer people than groups | 422 |
| group list fails validation (see §2) | 422 |
| draw / groups / `team_mode` fields outside `geplant` | 409 |
| draw / groups on a non-group challenge | 409 |
| join / leave a running group challenge | 409 |
| sieger: both or neither of `user_id` / `group_id` | 422 |
| sieger `group_id` not in `gewinner_group_ids` | 422 |
| sieger `user_id` not a member of a winning group | 422 |
| sieger `group_id` on a non-group challenge | 422 |

### `ChallengeOut` additions

```
team_mode: bool
group_count: int | None
seeding_days: int
groups_drawn: bool
groups: list[GroupOut]          # [] for non-group challenges
unassigned: list[StandingEntryOut]  # only filled while geplant; pool members without a group
meine_gruppe_id: int | None
sieger_group_id: int | None     # next to the existing sieger_id
kann_gruppen_bearbeiten: bool   # admin and team_mode and geplant
```

```
GroupOut:
  id, name, size, sum, value, rank, geschafft
  members: list[StandingEntryOut]   # sorted by value desc
```

`standings` stays the flat per-person list, `mein_stand` the own individual entry. `kann_sieger_setzen` also requires `len(gewinner_group_ids) > 0` for group challenges.

`ChallengeInput` gets the three optional fields; `GroupIn` / `GroupsIn` / `SiegerIn` (with optional `user_id` and `group_id`) are new schemas.

## 4 · Frontend

### Admin form (`components/admin/ChallengesAdmin.tsx`)

- Checkbox "Gruppen-Challenge". When checked: inputs "Anzahl Gruppen" (default 3) and "Setzliste: letzte N Tage" (default 30); the Wertung select hides Streak; the target label reads "Ziel pro Kopf".
- The challenge list below shows a "Gruppen" link for planned group challenges (→ editor route).

### Group editor (`components/challenges/GroupEditor.tsx`, route `/arena/challenges/:id/gruppen`)

Admin only; non-admins and non-planned challenges see a short notice with a link back. Data: `api.challenge(id)` plus `api.challengeSeeding(id)`.

- One card per group: editable name (text input), member rows with avatar, name and the seeding value in small muted text, group total and "pro Kopf" below.
- Per member a small select "→ Gruppe B", "→ Gruppe C", "Entfernen". Changing it moves the person locally.
- Block "Nicht zugeordnet": every active user who is in no group (pool members first, then the rest), each with a select "→ Gruppe X". This covers both adding late joiners and adding people who never joined.
- Buttons: "Neu auslosen" (calls `draw`; if there are unsaved edits, `window.confirm`-free inline confirmation "Ungespeicherte Änderungen verwerfen?" with a second click) and "Speichern" (`PUT groups`). A muted "ungespeichert" badge appears while local state differs from the server.
- Warning line when group sizes differ by more than one.
- Errors from the API are shown via the toast, like the admin form does.

### Detail view (`components/challenges/ChallengeDetail.tsx`)

For `team_mode` the flat list is replaced by one card per group, sorted by rank, own group first and highlighted:

- Header: name, chip (rank chip in ranking mode; "geschafft" / "noch X pro Kopf" in target mode), progress bar (per-head value against target; relative to the leader in ranking mode), line "812 MM · 271 pro Kopf".
- Member rows: avatar, name, individual value. No per-person chips.
- Not yet drawn: notice "Gruppen werden noch ausgelost", plus the editor link for admins. While `geplant` and drawn, admins also get the editor link at the top.
- Finished target challenges: winner band shows "Sieger: Gruppe A" or "Sieger: Ben (Gruppe A)". The admin select offers the qualified groups first, then their members, and posts `group_id` or `user_id` accordingly.

The group card and the group winner select are their own small components (`GroupCard.tsx`, inside `components/challenges/`) so `ChallengeDetail.tsx` stays readable.

### Hero card, rows, wertung

- `ChallengeHeroCard`: for group challenges "Gruppe A · 271 / 300 pro Kopf · Platz 2 von 3" using `meine_gruppe_id`.
- `wertung.ts`: `wertungText` yields "Ziel: 300 MM pro Kopf · 3 Gruppen" / "Rangliste nach MM pro Kopf · 3 Gruppen"; `fortschritt` works on the group value.
- `ChallengeRow` (finished): winner is the `sieger` person, else the single winning group name, else the winning group names joined.

### API client (`api/client.ts`)

Types: `Challenge` gets the new fields, `ChallengeGroup`, `SeedingEntry`, `ChallengeInput` gets `team_mode`, `group_count`, `seeding_days`. Functions: `drawChallengeGroups(id)`, `saveChallengeGroups(id, groups)`, `challengeSeeding(id)`; `setChallengeSieger(id, {user_id} | {group_id})`.

## 5 · Feed

No new event types. Payloads are extended:

| Event | Addition |
| --- | --- |
| `challenge_start` | `team_mode`, `group_count` |
| `challenge_qualified` | For group challenges emitted **per group** once it reaches the target: `group_id`, `group_name`, `member_ids`; `FeedEvent.user_id` is `None`. Idempotent per (`challenge_id`, `group_id`). |
| `challenge_end` | `gewinner_gruppen: [names]` next to `gewinner_ids` / `gewinner_namen` |
| `challenge_sieger` | `group_id`, `gruppe` (name) — either alone (group winner) or together with `user_id` (person from that group). The rewrite-on-correction behaviour stays. |

`FeedItem.tsx` renders: "Gruppe A hat das Ziel geknackt", "Gruppe A hat die Challenge gewonnen", "Ben (Gruppe A) hat den Preis gewonnen".

## 6 · File plan

| File | Change |
| --- | --- |
| `backend/app/models.py` | five new `Challenge` columns |
| `backend/app/db.py` | `migrate()` adds the columns to existing DBs |
| `backend/app/services/challenge_groups.py` | new: seeding, pool, draw, validate_groups, group_standings |
| `backend/app/services/challenges.py` | `teilnehmer_ids`, `_einfrieren`, `resolve_due`, `setze_sieger` learn about groups |
| `backend/app/services/feed.py` | payload additions, per-group qualified event |
| `backend/app/routers/challenges.py` | new endpoints, `_challenge_out` additions, rule checks |
| `backend/app/schemas.py` | `ChallengeIn/Out`, `GroupOut`, `GroupsIn`, `SeedingEntryOut`, `SiegerIn` |
| `frontend/src/api/client.ts` | types and functions |
| `frontend/src/components/admin/ChallengesAdmin.tsx` | checkbox, fields, editor link |
| `frontend/src/components/challenges/GroupEditor.tsx` | new page |
| `frontend/src/components/challenges/GroupCard.tsx` | new |
| `frontend/src/components/challenges/ChallengeDetail.tsx` | group view, winner select |
| `frontend/src/components/challenges/ChallengeHeroCard.tsx`, `ChallengeRow.tsx`, `wertung.ts` | group texts |
| `frontend/src/components/feed/FeedItem.tsx` | group payload rendering |
| `frontend/src/App.tsx` | editor route |

## 7 · Testing

**Backend `tests/test_challenge_groups.py`**

- Seeding window: yesterday included, today excluded, category filter applied, `km_factor` ignored, ties by `user_id`.
- Draw with a fixed `rng`: every pot spread over distinct groups, partial last pot, size difference at most one, names kept on redraw, fewer people than groups → 422.
- Group value: per-head average, target per head (3 × 300 vs 4 × 300), ranking with shared ranks, inactive member drops out of sum and divisor, empty group is 0.
- `validate_groups`: duplicate person, unknown or inactive user, wrong group count, empty group, empty name → 422; placing a non-joined person in `opt_in` creates the participant row.
- Rules: `streak` → 422, `group_count < 2` → 422, draw/groups outside `geplant` → 409, changing `group_count` clears groups, join/leave only while `geplant`, leaving removes from group, late joiner is `unassigned`.
- Lifecycle: group challenge without groups does not start; with groups it starts; freeze writes `groups`, `gewinner_ids` (members), `gewinner_group_ids`; result untouched afterwards.
- Sieger: group and person accepted; person outside a winning group → 422; `group_id` on a non-group challenge → 422; both/neither → 422; correction overwrites.
- `ChallengeOut`: `groups`, `unassigned`, `meine_gruppe_id`, `kann_gruppen_bearbeiten`, `sieger_group_id`.

**Backend `tests/test_feed.py`**

- `challenge_qualified` per group exactly once across repeated requests.
- `challenge_end` carries `gewinner_gruppen`; `challenge_sieger` carries `gruppe` and is rewritten on correction.

**Frontend**

- `GroupEditor.test.tsx`: move, remove, add from "Nicht zugeordnet", rename, save payload, "ungespeichert" badge, size warning, redraw confirmation.
- `ChallengeDetail.test.tsx`: group cards ranked, own group first, "wird noch ausgelost", winner band for group and for person, admin select posts the right body.
- `ChallengesAdmin` test: checkbox reveals the fields, Streak disappears, payload includes the new fields.
- `wertung.test.ts`, `ChallengeRow.test.tsx`, `FeedItem` cases for group texts.

## 8 · Follow-ups (not in this PR)

- Group streak metric ("at least one member per day").
- Replacing a dropped-out member while the challenge is running.
- Team achievements.
