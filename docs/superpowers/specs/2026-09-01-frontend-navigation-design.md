# Design spec: Frontend navigation restructure (redesign chunk 1)

**Date:** 2026-09-01
**Status:** Approved by Erik in the brainstorming session.
**Language note:** From this spec on, code, comments, commits and docs are written in English. User-facing UI copy stays German.

## Goal

Reduce the app to four tabs, fold Wetten and Challenges into one "Arena" tab, give the quick-entry card its own "MyMeters" tab, move achievements into the profile page, merge the settings modal into the own profile page, and stop teasing locked hidden achievements in the app (the admin sees them in the Admin panel instead).

This is chunk 1 of the frontend redesign. Chunk 2 (comparison page + monthly race) and chunk 3 (monthly achievements) follow in separate specs.

## Non-goals

- No visual redesign of the Vergleich, Wetten, Challenges or Feed pages. Their content is reused as-is.
- No change to how achievements are computed or unlocked; only where they are displayed.
- No changes to comparison, feed, bets or challenges endpoints.
- No mass renames of existing German identifiers. Files that are rewritten get English names; files that are only extended keep their names.
- The compact quick-entry bar on the Vergleich home stays for now; chunk 2 decides its fate.

## Decisions (from the brainstorming)

| Topic | Decision |
| --- | --- |
| Tab set | Vergleich `/`, Feed `/feed`, Arena `/arena`, MyMeters `/mymeters` |
| Arena content | Two sub-views (Challenges, Wetten) switched by a pill row; nested routes |
| Arena name | "Arena" |
| MyMeters name | "MyMeters" (title case, brand-style name) |
| Profile access | Tapping the avatar in the top bar opens your own profile page (no modal) |
| Settings | Last section of your own profile; contains Logout and a Regeln link |
| Theme toggle | Stays in the top bar |
| Admin access | Gear icon in the top bar, admins only; no Admin tab |
| Regeln access | Footer link next to Datenschutz, plus a link in the settings section |
| Achievements | Move from the activities page into the profile page (trophy room) |
| Hidden achievements | Locked ones are not shown anywhere in the app; unlocked ones appear like any other achievement and stay showcasable; the feed keeps announcing unlocks; the Admin panel lists all hidden achievements with their unlockers |

## 1 · Navigation and routing

### Tabs

`frontend/src/components/ui/tabs.ts` defines four tabs:

| Path | Label | Icon | Rule |
| --- | --- | --- | --- |
| `/` | Vergleich | fahne | always (end match) |
| `/feed` | Feed | chart | only after season start (`abStart`) |
| `/arena` | Arena | pokal | only if at least one of the add-ons `challenges` or `sidebets` is active |
| `/mymeters` | MyMeters | blitz | always |

The `adminOnly` flag disappears from the tab type; the `addon` field becomes `addons: string[]` meaning "visible if any of these is active". `sichtbareTabs()` keeps its signature apart from that.

### Top bar (Layout)

Left to right: logo, desktop tab pills, then right-aligned: gear icon (admins only, links to `/admin`, aria-label "Admin"), theme toggle, avatar with display name (name hidden on mobile). The avatar is a link to `/profil/<me.id>`. The logout icon is removed from the bar. The mobile bottom bar renders the same four tabs. The feed unseen dot stays on the Feed tab in both bars. The countdown banner and footer stay; the footer gains a "Regeln" link before "Datenschutz".

### Routes (App.tsx, logged in)

| Path | Renders |
| --- | --- |
| `/` | Vergleich |
| `/feed` | Feed |
| `/mymeters` | MyMeters |
| `/arena` | redirect to `/arena/challenges` if the challenges add-on is active, else `/arena/wetten` if sidebets is active, else `/` |
| `/arena/challenges` | Arena with the Challenges sub-view |
| `/arena/challenges/:id` | Arena shell with ChallengeDetail |
| `/arena/wetten` | Arena with the Wetten sub-view (only if sidebets is active) |
| `/profil/:userId` | Profil |
| `/regeln` | Regeln |
| `/admin` | Admin (admins only; non-admins are redirected to `/`) |
| `/datenschutz` | Datenschutz |
| `/aktivitaeten` | redirect to `/mymeters` |
| `/challenges` | redirect to `/arena/challenges` |
| `/challenges/:id` | redirect to `/arena/challenges/:id` |
| `/wetten` | redirect to `/arena/wetten` |
| `*` | redirect to `/` |

Logged-out routes are unchanged.

## 2 · Arena

`pages/Arena.tsx` renders a pill row with "Challenges" and "Wetten" (same look as the view switcher on Vergleich, `NavLink`s so the active pill follows the URL) and an `<Outlet />` below. The pill row is hidden when only one add-on is active. The existing `pages/Challenges.tsx` and `pages/Wetten.tsx` are rendered unchanged as the sub-views. `ChallengeHeroCard` and `ChallengeRow` link to `/arena/challenges/:id`; `ChallengeDetail` links back to `/arena/challenges`.

## 3 · MyMeters

`pages/MyMeters.tsx` replaces `pages/MeineAktivitaeten.tsx`. It keeps: the season selector, the `SchnellwahlCard` hero, the per-category collapsible list of own entries with the edit and delete modals. It drops the achievements section entirely. The achievement card components that lived inside the old page move to `components/achievements/`:

- `AchievementBadge.tsx` (single badge with progress)
- `TierCard.tsx` (bronze/silver/gold tiers per discipline, was `StufenKarte`)
- `OneTimeCard.tsx` (first-to-gold and race achievements, was `EinmalKarte`)
- `TimeAtTopCard.tsx` (timer-based "Zeit an der Spitze", was `ZeitSpitzeKarte`)
- `HiddenCard.tsx` (unlocked hidden achievement with showcase toggle; the locked "???" branch is deleted)
- `AchievementsSection.tsx` (composes the cards from a list of achievements; used by the profile page)

Any "x von y" counter in the section excludes hidden achievements that are not unlocked.

## 4 · Profile page

`pages/Profil.tsx` keeps its sections in this order: header (avatar, name, rank, athlete type), radar with the compare-with-me toggle, stat tiles, sport shares, then two additions:

- **Achievements** section (after the sport shares, before "Letzte Aktivitäten"). Own profile: `AchievementsSection` fed by `GET /api/achievements` (full data, progress, showcase toggles via the existing PATCH). Other member: the same section fed by the new `GET /api/achievements/user/{user_id}`, which only contains unlocked achievements, so no progress bars and no toggles.
- **Einstellungen** section, own profile only, as the last section: `components/profile/SettingsSection.tsx`. Content is the current `ProfilModal` body moved into a card: username, display name, new password, avatar choice, Strava consent/connect/disconnect block, a "Speichern" button, a text link to `/regeln`, and a "Logout" button that calls `api.logout()` and clears the `me` query. `ProfilModal.tsx` and its test are deleted.

## 5 · Backend

Both endpoints live in `backend/app/routers/achievements.py`.

### `GET /api/achievements/user/{user_id}`

- Auth: any logged-in user.
- Returns `list[AchievementOut]` containing only achievements with `achieved == True` for the given user, hidden ones included. The computation is the existing per-user body of `achievements()` extracted into a function `achievements_for(session, user_id) -> list[AchievementOut]`; the new endpoint does not call `check_unlocks` (read-only, no side effects on behalf of another user). The existing `GET /api/achievements` keeps calling `check_unlocks` for the requester and then uses the same function.
- 404 if the user does not exist or is inactive.

### `GET /api/achievements/hidden`

- Auth: admin only (403 otherwise).
- Returns `list[HiddenAchievementAdminOut]`: `key`, `title`, `description`, `emoji`, `unlocks: list[{user_id, display_name, avatar, unlocked_at}]`, one entry per hidden definition (`HIDDEN_DEFS`), unlocks read from `AchievementUnlock` joined with active users, sorted by `unlocked_at`.
- Route order: `/hidden` and `/user/{user_id}` are declared before the catch-all `PATCH /{key}` so FastAPI does not shadow them.

## 6 · Admin panel

`components/admin/HiddenAchievementsAdmin.tsx`, rendered as the last collapsible section of `pages/Admin.tsx`, titled "Versteckte Achievements". Read-only list: emoji, title, description, then the unlockers as "Name · dd.mm.yyyy" or "noch niemand".

## 7 · API client

`api/client.ts` gains `api.userAchievements(userId)` and `api.hiddenAchievementsAdmin()` plus the `HiddenAchievementAdmin` type. `Achievement` is unchanged.

## 8 · File plan

New: `pages/Arena.tsx`, `pages/MyMeters.tsx`, `components/achievements/*` (see section 3), `components/profile/SettingsSection.tsx`, `components/admin/HiddenAchievementsAdmin.tsx`.
Deleted: `pages/MeineAktivitaeten.tsx` (+ test), `components/ui/ProfilModal.tsx` (+ test).
Extended in place: `App.tsx`, `components/ui/Layout.tsx`, `components/ui/tabs.ts`, `pages/Profil.tsx`, `pages/Admin.tsx`, `components/challenges/ChallengeHeroCard.tsx`, `ChallengeRow.tsx`, `ChallengeDetail.tsx`, `api/client.ts`, `backend/app/routers/achievements.py`.

## 9 · Error handling

- Non-admins on `/admin` are redirected to `/`; the hidden endpoint additionally enforces 403 server-side.
- Profile of an unknown member: the existing "nicht gefunden" behaviour stays; the achievements query is disabled until the member is known.
- Arena with no active add-on cannot be reached from the UI; a direct visit to `/arena` redirects to `/`.

## 10 · Testing

Tests are written before the implementation (TDD).

Backend (pytest): `user/{id}` returns only achieved entries and includes achieved hidden ones; excludes unachieved; 404 for unknown/inactive; `hidden` returns every hidden definition with correct unlockers; 403 for non-admin.

Frontend (vitest): `tabs.test.ts` (four tabs, Arena visible with either add-on, hidden with none, no admin tab); Layout (gear icon only for admins, avatar links to own profile, no logout button, footer has Regeln); Arena (pill row hidden with one add-on, `/wetten` and `/challenges/:id` redirect); Profil (achievements section for own and other member, settings section only on own profile, logout clears `me`); MyMeters (renders hero and list, no achievements heading); Admin (hidden section renders unlockers and "noch niemand"). Existing tests of the deleted page and modal are removed; tests that assert old routes are updated.

Because there is no test CI, the implementation plan ends with running `npm test`, `npm run lint`, `npx tsc -b` and backend pytest locally before the PR is opened.

## 11 · Follow-ups (not in this PR)

- Chunk 2: comparison page redesign with a month/year race toggle; decide whether the compact quick-entry bar on Vergleich stays.
- Chunk 3: monthly achievements ("Bester im Monat").
- Optional: install the `impeccable` design skill before chunk 2 and run `/impeccable init` to capture the Neon Night design system in DESIGN.md.
