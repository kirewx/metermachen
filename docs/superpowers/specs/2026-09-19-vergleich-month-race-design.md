# Design spec: Vergleich month race (redesign chunk 2)

**Date:** 2026-09-19
**Status:** Approved by Erik in the brainstorming session.
**Language note:** Code, comments, commits and docs in English. User-facing UI copy stays German.

## Goal

Add a Monat/Jahr toggle to the Vergleich page so the race and the sport mix can be viewed per calendar month, browse every month of a season, remove the compact quick-entry bar, and tidy the control row so it fits a phone.

This is chunk 2 of the frontend redesign. Chunk 3 (monthly achievements, "Bester im Monat") follows in its own spec and reuses the month standings introduced here.

## Non-goals

- No visual rework of the four views (Rennen, Verlauf, Sport-Mix, Höhenmeter).
- No monthly goal and no monthly milestones.
- No month mode for Höhenmeter or the warm-up archive.
- No monthly achievements (chunk 3).
- No URL state for view, mode or month.
- No mass renames of existing German identifiers.

## Decisions (from the brainstorming)

| Topic | Decision |
| --- | --- |
| Scope | Month toggle plus control-row tidy-up; existing views keep their look |
| Month target | No goal; the month leader sets the lane scale |
| Month range | Every month of the selected season, default is the current month |
| Toggle reach | Rennen, Verlauf and Sport-Mix; Höhenmeter stays year-only (Verlauf added after Erik's review of the running page, for consistency) |
| Quick-entry bar | Removed from Vergleich; entry lives on MyMeters |
| Control layout | Row 1 view tabs; row 2 Monat/Jahr pill, stepper, MM/km. The stepper replaces the Saison select |
| Computation | Backend `month` query param on the existing comparison endpoint |

## 1 · Backend

`GET /api/comparison/{year}` gains an optional query parameter `month` in the form `YYYY-MM`.

`compute_comparison(session, year, phase="challenge", month=None)`:

- The month filter is applied after the existing season-window and start-date filters, so a partial first month only counts activities from the season start on.
- Totals, ranks, `by_category`, `segments`, `cumulative` and `elevation_by_month` are all computed from the filtered rows. `km_factor` and the factor-by-date resolver apply as in the year view.
- The month axis is computed from the unfiltered season rows (before the month filter), exactly as `elevation_months` is today.

`ComparisonOut` gains:

- `month: str | None = None`, echoing the request.
- `months: list[str] = []`, the season's month axis. Same value as `elevation_months`, which stays for the Höhenmeter view.

Errors:

- `month` not matching `^\d{4}-(0[1-9]|1[0-2])$`: 422 (FastAPI query validation).
- `month` not contained in the season's month axis: 404 "Monat liegt nicht in der Saison".
- `month` combined with `phase=warmup`: 422 "Monatsansicht gibt es nur für die Saison".

`GET /{year}/last-seen` and `POST /{year}/seen` are unchanged and stay year-only.

## 2 · Page controls

`SchnellwahlLeiste` is removed from `pages/Vergleich.tsx`; the component and its test are deleted because nothing else uses them.

Row 1: the four view tabs, unchanged.
Row 2: `PeriodControl` on the left, the MM/km pill on the right (hidden on Höhenmeter as today).

New component `components/comparison/PeriodControl.tsx` (presentational, state lives in `Vergleich`):

- Props: `mode: 'month' | 'year'`, `showModeToggle: boolean`, `years: number[]` (ascending), `year`, `months: string[]`, `month: string | null`, `onModeChange`, `onYearChange`, `onMonthChange`.
- Pill "Monat | Jahr", rendered only when `showModeToggle` is true (Rennen, Verlauf and Sport-Mix).
- Stepper `‹ label ›`. In the effective year mode the label is the season year and the arrows step through `years`. In month mode the label is the German short month plus year ("Sep 2026") and the arrows step through `months`. Arrows are disabled at both ends. aria-labels: "Vorheriger Monat", "Nächster Monat", "Vorherige Saison", "Nächste Saison".
- A finished month (earlier than the current calendar month) shows a small "Endstand" tag next to the stepper.

Pure helpers in `components/comparison/period.ts`:

- `defaultMonth(months, today)`: the current month if it is in `months`, otherwise the last entry, or `null` for an empty list.
- `monthLabel(key)`: "2026-09" to "Sep 2026".
- `isFinishedMonth(key, today)`.

State in `Vergleich`:

- `mode` comes from `usePeriodMode()` (`components/comparison/usePeriodMode.ts`): stored in localStorage under `mm_period_mode`, like the MM/km choice, and `'month'` on the first visit (added after Erik's review). A season without months is shown as a whole regardless of the stored mode.
- `month` (`string | null`), the existing `gewaehlt` season and `ansicht` stay plain component state.
- The effective mode is `'month'` only when `mode === 'month'` and the view is Rennen, Verlauf or Sport-Mix. Switching to Höhenmeter keeps `mode`, so returning restores the month view.
- The month axis comes from the year query (`['comparison', year, null]`), which is always loaded. Switching to month mode, or changing the season while in month mode, sets `month` to `defaultMonth(months, today)`.
- Data query: `['comparison', year, effectiveMonth]` with `api.comparison(year, effectiveMonth ?? undefined)`.

Warm-up archive: the "Archiv (Warm-up)" select option is replaced by a text link "Warm-up-Archiv" below the page content. While the archive is open, the control rows are hidden and a link "Zurück zum Vergleich" is shown above `WarmupArchiv`.

## 3 · Views in month mode

`RaceBahnen` reads `data.month`. When it is set:

- no goal flag, no milestone markers and no milestone ticks in the lanes;
- the lane scale is the leader's total (at least 1 to avoid division by zero);
- the since-last-seen query, banner and animation are disabled and `markComparisonSeen` is not called.

Year mode behaves exactly as before.

`SportMix` needs no change; it renders the filtered `by_category`.

`JahresVerlauf` renders the filtered `cumulative` series, which the backend restarts at zero for the month. The goal and milestone reference lines are season values and are hidden in month mode (`showsSeasonTargets(month, mode)` in `period.ts`).

Both modes: a user whose total is 0 shows rank "–" and never gets the leader glow. This prevents an arbitrary "leader" on the first day of a month.

## 4 · API client

`api.comparison(year, month?)` appends `?month=` when given. `Comparison` gains `month: string | null` and `months: string[]`.

## 5 · Errors and edge cases

- Empty month: every active user is listed with 0 and rank "–".
- 404/422 from the endpoint render in the existing error line.
- A past season only offers its own months; the default is its last month.
- A season without any month axis (no activities, not started): the Monat pill is disabled.

## 6 · File plan

New: `components/comparison/PeriodControl.tsx` (+ test), `components/comparison/period.ts` (+ test), `pages/Vergleich.test.tsx` if none exists.
Deleted: `components/activities/SchnellwahlLeiste.tsx` (+ test).
Extended in place: `pages/Vergleich.tsx`, `components/comparison/RaceBahnen.tsx` (+ test), `api/client.ts`, `backend/app/routers/comparison.py`, `backend/app/schemas.py`, `backend/tests/test_comparison.py`.

## 7 · Testing

Tests are written before the implementation (TDD).

Backend (pytest): month filter yields the right totals and ranks; partial first month respects `start_date`; `months` axis is present with and without the param; `month` is echoed; malformed month 422; month outside the season 404; month with warm-up 422; the factor-by-date resolver applies inside a month.

Frontend (vitest): `period.ts` helpers; `PeriodControl` (mode switch, month stepping, disabled ends, season stepping in year mode, hidden pill, "Endstand" tag); `RaceBahnen` (month mode hides goal and milestones, shows no banner, does not mark seen; rank "–" at zero in both modes); `Vergleich` (no quick-entry bar, archive link opens and closes the archive, month mode requests the month).

Because there is no test CI, the implementation plan ends with running `npm test`, `npm run lint`, `npx tsc -b` and backend pytest locally before the PR is opened.

## 8 · Follow-ups (not in this PR)

- Chunk 3: monthly achievements ("Bester im Monat"), built on `compute_comparison(..., month=...)`.
- Group names should be editable after a group challenge has started.
