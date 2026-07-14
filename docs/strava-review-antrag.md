# Strava API — Antrag auf Athleten-Limit-Erhöhung

Vorlage zum Einreichen im Strava-Review-Formular. **Erst absenden, wenn PR #10
gemergt und live ist**, damit die Privacy-URL erreichbar ist.

- Formular: über die Strava-API-Application-Einstellungen bzw.
  <https://developers.strava.com/> → „Request an increase".
- Sprache: Englisch (die Reviewer arbeiten auf Englisch).
- **Vor dem Absenden:** unten die `Client ID` eintragen.
- Ziel: **Standard Tier (bis 9.999 Athleten)** — es gibt keine Zwischenstufe
  zwischen 10 und 10.000; die Freigabe deckt die volle Standard-Kapazität ab.

---

## Formularfelder

**App name:** MeterMachen

**Client ID:** _(hier eintragen)_

**Website / redirect domain:** https://metermachen.jasperz.de

**Privacy policy:** https://metermachen.jasperz.de/datenschutz

**Requested athlete limit:** Standard Tier (up to 9,999)

---

## Textbausteine (Englisch, zum Kopieren)

**What the app does:**

> MeterMachen is a small, private, invite-only fitness challenge among fixed
> groups of friends. Members accumulate distance across running, cycling and
> swimming, which is combined into a shared group leaderboard for a season-long
> friendly competition. It is non-commercial and not publicly discoverable —
> access is by personal invitation link only.

**How it uses Strava data:**

> After a member connects their Strava account via OAuth (scope
> `activity:read_all`), the app imports their activities (sport type, distance,
> elevation, moving time, date, title) to display and rank them in the group
> leaderboard. New activities are received via the webhook. Data is read-only —
> we never modify Strava data. Every activity displayed links back to Strava via
> a "View on Strava" link, and the official "Connect with Strava" button is used
> for authorization.

**Data handling / compliance:**

> All data is stored on our own server in Germany (netcup). We do not share
> athlete data with any third party and do not use it with any third-party AI/ML
> tools. Members can disconnect at any time (which immediately deletes their
> tokens) or revoke access at strava.com/settings/apps. Our privacy policy is
> linked in-app and publicly reachable without login.

**Why we need this capacity:**

> The app is a private, invite-only fitness-challenge platform. We already run
> one group of ~10 athletes and plan to host several separate private groups
> (different friend circles / teams), each with its own leaderboard. To onboard
> current and upcoming groups without repeatedly hitting the limit, we request
> Standard Tier access. Usage stays low-volume and read-only; we only import
> activity summaries needed for the leaderboards.

---

## Checkliste vor dem Einreichen

- [ ] PR #10 gemergt und deployt (Datenschutz-Seite live unter `/datenschutz`)
- [ ] Offizieller „Connect with Strava"-Button sichtbar im Profil
- [ ] `Client ID` oben eingetragen
- [ ] Privacy-URL im Browser erreichbar (ohne Login): https://metermachen.jasperz.de/datenschutz

## Hinweise

- Freigabe ist **nicht garantiert** und dauert erfahrungsgemäß **Wochen** —
  früh beantragen, nicht erst wenn 10/10 voll ist.
- Strava lehnt Apps ab, die Athletendaten an Dritt-KI-Tools weitergeben — das
  ist bei MeterMachen nicht der Fall (bewusst nicht einbauen).

Quellen: Strava API FAQ, Brand Guidelines (<https://developers.strava.com/guidelines/>),
API Policy 2026 (<https://www.strava.com/legal/api_policy>).
