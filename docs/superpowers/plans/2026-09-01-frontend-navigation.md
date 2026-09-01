# Frontend Navigation Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Four tabs (Vergleich, Feed, Arena, MyMeters), achievements and settings on the profile page, hidden achievements out of the app and into the Admin panel.

**Architecture:** Pure route/composition change in the React frontend plus two read-only FastAPI endpoints in the existing achievements router. Existing pages (Vergleich, Feed, Challenges, Wetten) are reused unchanged; the activities page is rewritten as MyMeters without its achievements block; the achievement cards become a `components/achievements/` folder consumed by the profile page; the settings modal becomes a profile section.

**Tech Stack:** React 19, react-router-dom 7, TanStack Query 5, Tailwind v4, Vitest + Testing Library; FastAPI + SQLModel + pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-frontend-navigation-design.md`

**Conventions for this plan:**
- New code, comments, commit messages and test names in English. UI strings stay German.
- Frontend commands run in `frontend/`: `npx vitest run <file>`, `npx eslint .`, `npx tsc -b`.
- Backend commands run in `backend/` with `.venv/Scripts/python.exe -m pytest tests/<file> -q`.
- Every commit ends with the two trailer lines:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_0144KhsATUHrUHW6eYm8r6yy`

---

## File map

| Action | Path | Responsibility |
| --- | --- | --- |
| Modify | `backend/app/routers/achievements.py` | `achievements_for()` extraction; `GET /user/{user_id}`; `GET /hidden` |
| Create | `backend/tests/test_achievements_profile.py` | tests for both endpoints |
| Modify | `frontend/src/api/client.ts` | `userAchievements`, `hiddenAchievementsAdmin`, types |
| Modify | `frontend/src/api/client.test.ts` | URL tests for the two calls |
| Modify | `frontend/src/components/ui/tabs.ts` (+test) | four tabs, `addons: string[]`, `arenaEntryPath()` |
| Create | `frontend/src/components/achievements/constants.ts` | tier order/labels, no-race keys |
| Create | `frontend/src/components/achievements/ShowcaseToggle.tsx` | emoji showcase toggle (was `EmojiToggle`) |
| Create | `frontend/src/components/achievements/AchievementBadge.tsx` | classic km badge |
| Create | `frontend/src/components/achievements/TierCard.tsx` | bronze/silver/gold card (was `StufenKarte`) |
| Create | `frontend/src/components/achievements/OneTimeCard.tsx` | one-time/race card (was `EinmalKarte`) |
| Create | `frontend/src/components/achievements/TimeAtTopCard.tsx` | timer card (was `ZeitSpitzeKarte`) |
| Create | `frontend/src/components/achievements/HiddenCard.tsx` | unlocked hidden card, no locked branch |
| Create | `frontend/src/components/achievements/AchievementsSection.tsx` (+test) | presentational grid from a list |
| Create | `frontend/src/components/achievements/ProfileAchievements.tsx` | queries + mutation for own/other profile |
| Create | `frontend/src/pages/MyMeters.tsx` (+test) | quick entry + own list (replaces MeineAktivitaeten) |
| Delete | `frontend/src/pages/MeineAktivitaeten.tsx` (+test) | |
| Create | `frontend/src/components/profile/SettingsSection.tsx` (+test) | settings card with logout (replaces ProfilModal) |
| Delete | `frontend/src/components/ui/ProfilModal.tsx` (+test) | |
| Modify | `frontend/src/pages/Profil.tsx` (+test) | achievements card + settings section |
| Create | `frontend/src/pages/Arena.tsx` (+test) | pill row + outlet |
| Modify | `frontend/src/App.tsx` (+new test) | routes, redirects, admin guard |
| Modify | `frontend/src/components/challenges/ChallengeHeroCard.tsx`, `ChallengeRow.tsx`, `ChallengeDetail.tsx` | links to `/arena/challenges/...` |
| Modify | `frontend/src/components/ui/Layout.tsx` (+new test) | gear icon, avatar link, no logout, footer Regeln |
| Create | `frontend/src/components/admin/HiddenAchievementsAdmin.tsx` | admin list |
| Modify | `frontend/src/pages/Admin.tsx` (+test) | mount the new section |

---

### Task 1: Backend `GET /api/achievements/user/{user_id}`

**Files:**
- Modify: `backend/app/routers/achievements.py:183-369`
- Create: `backend/tests/test_achievements_profile.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_achievements_profile.py
"""Profile-facing achievement endpoints: another member's unlocked list and
the admin overview of hidden achievements."""

from datetime import date

from app.models import AchievementUnlock, Activity
from tests.conftest import login, make_category, make_user


def add_activity(session, user, cat, km, d=date(2026, 7, 12)):
    session.add(Activity(user_id=user.id, category_id=cat.id, date=d, distance_km=km))
    session.commit()


def test_user_achievements_requires_login(client):
    assert client.get("/api/achievements/user/1").status_code == 401


def test_user_achievements_returns_only_unlocked(client, session):
    make_user(session)  # erik, the requester
    lisa = make_user(session, username="lisa")
    cat = make_category(session, name="Laufen", icon="laufen")
    add_activity(session, lisa, cat, 5.0)
    session.add(AchievementUnlock(user_id=lisa.id, key="hattrick"))
    session.commit()
    login(client)

    r = client.get(f"/api/achievements/user/{lisa.id}")
    assert r.status_code == 200
    body = {a["key"]: a for a in r.json()}
    assert all(a["achieved"] for a in body.values())
    assert "startschuss" in body  # computed live from activities
    assert body["hattrick"]["title"] == "Hattrick"  # hidden but unlocked: revealed
    assert body["hattrick"]["hidden"] is True
    assert "kletterkoenig" not in body  # hidden and locked: absent
    assert "ironman" not in body  # visible but not achieved: absent


def test_user_achievements_404_for_unknown_or_inactive(client, session):
    make_user(session)
    tom = make_user(session, username="tom")
    tom.is_active = False
    session.add(tom)
    session.commit()
    login(client)
    assert client.get("/api/achievements/user/999").status_code == 404
    assert client.get(f"/api/achievements/user/{tom.id}").status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_achievements_profile.py -q`
Expected: 2 failures with 404 or 405 instead of 200/404 (route does not exist; `/user/1` currently falls through to nothing).

- [ ] **Step 3: Extract `achievements_for()` and add the endpoint**

In `backend/app/routers/achievements.py` replace the `achievements` endpoint (lines 183-369) with:

```python
def achievements_for(session: Session, user: User) -> list[AchievementOut]:
    """Full achievement list (achieved and open) for one user. Pure read."""
    cats = {c.id: c for c in session.exec(select(Category)).all()}
    user_acts = session.exec(
        select(Activity).where(Activity.user_id == user.id)
    ).all()
    # ... the existing body from `sums: dict[str, float] = defaultdict(float)`
    # down to the final `return out`, unchanged, still referring to `user.id`.


@router.get("", response_model=list[AchievementOut])
def achievements(
    user: User = Depends(get_current_user), session: Session = Depends(get_session)
):
    # "Platz 1 gehalten"/Testphasen-Sieg can trigger without an own activity,
    # so unlocks are checked for the requesting person on every read (spec §2.2).
    check_unlocks(session, user.id)
    return achievements_for(session, user)


@router.get(
    "/user/{user_id}",
    response_model=list[AchievementOut],
    dependencies=[Depends(get_current_user)],
)
def user_achievements(user_id: int, session: Session = Depends(get_session)):
    """Unlocked achievements of another member (hidden ones included once
    unlocked). Read-only: no unlock check on someone else's behalf."""
    target = session.get(User, user_id)
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="Mitglied nicht gefunden")
    return [a for a in achievements_for(session, target) if a.achieved]
```

Concretely: cut lines 191-369 (from `cats = {...}` to `return out`) into `achievements_for`, keep every line as it is (they only use `user.id`, `user_acts`, `session`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_achievements_profile.py tests/test_achievements.py -q`
Expected: all pass (the existing achievements tests guard the extraction).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/achievements.py backend/tests/test_achievements_profile.py
git commit -m "feat(achievements): read-only endpoint for another member's unlocked achievements"
```

---

### Task 2: Backend `GET /api/achievements/hidden` (admin)

**Files:**
- Modify: `backend/app/routers/achievements.py`
- Modify: `backend/tests/test_achievements_profile.py`

- [ ] **Step 1: Write the failing tests** (append to the test file)

```python
HIDDEN_KEYS = {
    "kletterkoenig", "hattrick", "wochenkoenig", "psychopath", "langstreckenguru",
    "kurzstreckenprofi", "dauerbrenner_bronze", "dauerbrenner_silber", "dauerbrenner_gold",
}


def test_hidden_admin_lists_every_definition_with_unlockers(client, session):
    make_user(session, username="chef", is_admin=True)
    lisa = make_user(session, username="lisa")
    tom = make_user(session, username="tom")
    tom.is_active = False
    session.add(tom)
    session.add(AchievementUnlock(user_id=lisa.id, key="hattrick"))
    session.add(AchievementUnlock(user_id=tom.id, key="hattrick"))  # inactive: not listed
    session.commit()
    login(client, username="chef")

    r = client.get("/api/achievements/hidden")
    assert r.status_code == 200
    body = {h["key"]: h for h in r.json()}
    assert set(body) == HIDDEN_KEYS
    assert body["hattrick"]["title"] == "Hattrick"
    assert body["hattrick"]["emoji"] == "🎩"
    assert [u["display_name"] for u in body["hattrick"]["unlocks"]] == ["Lisa"]
    assert body["hattrick"]["unlocks"][0]["unlocked_at"]
    assert body["kletterkoenig"]["unlocks"] == []


def test_hidden_admin_forbidden_for_members(client, session):
    make_user(session)
    login(client)
    assert client.get("/api/achievements/hidden").status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_achievements_profile.py -q`
Expected: the two new tests fail (404 or 405).

- [ ] **Step 3: Add the models and endpoint**

In `backend/app/routers/achievements.py`: import `require_admin` from `..deps`, then add directly above `class ShowcasePatch`:

```python
class HiddenUnlockOut(BaseModel):
    user_id: int
    display_name: str
    avatar: str
    unlocked_at: datetime


class HiddenAchievementAdminOut(BaseModel):
    key: str
    title: str
    description: str
    emoji: str | None
    unlocks: list[HiddenUnlockOut]


@router.get(
    "/hidden",
    response_model=list[HiddenAchievementAdminOut],
    dependencies=[Depends(require_admin)],
)
def hidden_achievements_admin(session: Session = Depends(get_session)):
    """Admin overview: every hidden definition and who unlocked it when."""
    hidden_keys = [key for key, *_ in HIDDEN_DEFS]
    rows = session.exec(
        select(AchievementUnlock, User)
        .join(User, AchievementUnlock.user_id == User.id)
        .where(AchievementUnlock.key.in_(hidden_keys), User.is_active)
        .order_by(AchievementUnlock.unlocked_at)
    ).all()
    by_key: dict[str, list[HiddenUnlockOut]] = defaultdict(list)
    for ul, u in rows:
        by_key[ul.key].append(HiddenUnlockOut(
            user_id=u.id, display_name=u.display_name, avatar=u.avatar,
            unlocked_at=ul.unlocked_at,
        ))
    return [
        HiddenAchievementAdminOut(
            key=key, title=title, description=description,
            emoji=EMOJIS.get(key), unlocks=by_key.get(key, []),
        )
        for key, title, description, _icon in HIDDEN_DEFS
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_achievements_profile.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/achievements.py backend/tests/test_achievements_profile.py
git commit -m "feat(achievements): admin overview of hidden achievements and their unlockers"
```

---

### Task 3: API client calls

**Files:**
- Modify: `frontend/src/api/client.ts` (types near line 160, calls near line 482)
- Modify: `frontend/src/api/client.test.ts`

- [ ] **Step 1: Write the failing tests** (append to `client.test.ts`)

```ts
describe('achievement endpoints', () => {
  it('userAchievements calls /api/achievements/user/<id>', async () => {
    mockFetch(200, [])
    await api.userAchievements(7)
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/achievements/user/7', expect.anything())
  })

  it('hiddenAchievementsAdmin calls /api/achievements/hidden', async () => {
    mockFetch(200, [])
    await api.hiddenAchievementsAdmin()
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/achievements/hidden', expect.anything())
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: 2 failures, `api.userAchievements is not a function`.

- [ ] **Step 3: Add types and calls**

After the `Achievement` type:

```ts
export type HiddenUnlock = {
  user_id: number
  display_name: string
  avatar: string
  unlocked_at: string
}
export type HiddenAchievementAdmin = {
  key: string
  title: string
  description: string
  emoji: string | null
  unlocks: HiddenUnlock[]
}
```

After `patchAchievement` in `api`:

```ts
  userAchievements: (userId: number) =>
    request<Achievement[]>(`/api/achievements/user/${userId}`),
  hiddenAchievementsAdmin: () =>
    request<HiddenAchievementAdmin[]>('/api/achievements/hidden'),
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/api/client.test.ts`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(api): client calls for member achievements and hidden admin list"
```

---

### Task 4: Four tabs and `arenaEntryPath`

**Files:**
- Modify: `frontend/src/components/ui/tabs.ts`
- Modify: `frontend/src/components/ui/tabs.test.ts` (rewrite)

- [ ] **Step 1: Rewrite the test file**

```ts
import { describe, expect, it } from 'vitest'
import { arenaEntryPath, sichtbareTabs, TABS } from './tabs'

const labels = (opts: { gestartet: boolean; aktiveAddons: Set<string> }) =>
  sichtbareTabs(TABS, opts).map((t) => t.label)

describe('sichtbareTabs', () => {
  it('shows exactly four tabs when everything is active', () => {
    const l = labels({ gestartet: true, aktiveAddons: new Set(['challenges', 'sidebets']) })
    expect(l).toEqual(['Vergleich', 'Feed', 'Arena', 'MyMeters'])
  })

  it('has no Admin and no Aktivitäten tab any more', () => {
    const l = labels({ gestartet: true, aktiveAddons: new Set(['challenges', 'sidebets']) })
    expect(l).not.toContain('Admin')
    expect(l).not.toContain('Aktivitäten')
  })

  it('hides Feed before the season starts', () => {
    expect(labels({ gestartet: false, aktiveAddons: new Set() })).not.toContain('Feed')
    expect(labels({ gestartet: true, aktiveAddons: new Set() })).toContain('Feed')
  })

  it('shows Arena when either add-on is active and hides it when none is', () => {
    expect(labels({ gestartet: true, aktiveAddons: new Set() })).not.toContain('Arena')
    expect(labels({ gestartet: true, aktiveAddons: new Set(['challenges']) })).toContain('Arena')
    expect(labels({ gestartet: true, aktiveAddons: new Set(['sidebets']) })).toContain('Arena')
  })

  it('MyMeters points at /mymeters', () => {
    expect(TABS.find((t) => t.label === 'MyMeters')?.to).toBe('/mymeters')
  })
})

describe('arenaEntryPath', () => {
  it('prefers challenges, then wetten, then home', () => {
    expect(arenaEntryPath(new Set(['challenges', 'sidebets']))).toBe('/arena/challenges')
    expect(arenaEntryPath(new Set(['sidebets']))).toBe('/arena/wetten')
    expect(arenaEntryPath(new Set())).toBe('/')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/ui/tabs.test.ts`
Expected: type/runtime failures (`arenaEntryPath` missing, labels differ).

- [ ] **Step 3: Rewrite `tabs.ts`**

```ts
export type Tab = {
  to: string
  label: string
  icon: string
  end: boolean
  abStart: boolean
  // Visible if at least one of these add-ons is active.
  addons?: string[]
}

export const TABS: Tab[] = [
  { to: '/', label: 'Vergleich', icon: 'fahne', end: true, abStart: false },
  { to: '/feed', label: 'Feed', icon: 'chart', end: false, abStart: true },
  {
    to: '/arena',
    label: 'Arena',
    icon: 'pokal',
    end: false,
    abStart: false,
    addons: ['challenges', 'sidebets'],
  },
  { to: '/mymeters', label: 'MyMeters', icon: 'blitz', end: false, abStart: false },
]

export function sichtbareTabs(
  tabs: Tab[],
  opts: { gestartet: boolean; aktiveAddons: Set<string> },
): Tab[] {
  return tabs.filter(
    (t) =>
      (!t.abStart || opts.gestartet) &&
      (!t.addons || t.addons.some((key) => opts.aktiveAddons.has(key))),
  )
}

// Where /arena lands: challenges first, bets second, home if neither is on.
export function arenaEntryPath(aktiveAddons: Set<string>): string {
  if (aktiveAddons.has('challenges')) return '/arena/challenges'
  if (aktiveAddons.has('sidebets')) return '/arena/wetten'
  return '/'
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/components/ui/tabs.test.ts`
Expected: 6 passed. (`Layout.tsx` still passes `isAdmin`; TypeScript tolerates the extra property only until Task 10, where Layout is rewritten. `npx tsc -b` is run at the end.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/tabs.ts frontend/src/components/ui/tabs.test.ts
git commit -m "feat(nav): four tabs with Arena and MyMeters, arenaEntryPath helper"
```

---

### Task 5: Achievement components folder

**Files:**
- Create: `frontend/src/components/achievements/constants.ts`
- Create: `frontend/src/components/achievements/ShowcaseToggle.tsx`
- Create: `frontend/src/components/achievements/AchievementBadge.tsx`
- Create: `frontend/src/components/achievements/TierCard.tsx`
- Create: `frontend/src/components/achievements/OneTimeCard.tsx`
- Create: `frontend/src/components/achievements/TimeAtTopCard.tsx`
- Create: `frontend/src/components/achievements/HiddenCard.tsx`
- Create: `frontend/src/components/achievements/AchievementsSection.tsx`
- Create: `frontend/src/components/achievements/AchievementsSection.test.tsx`
- Source: `frontend/src/pages/MeineAktivitaeten.tsx:183-462`

- [ ] **Step 1: Write the failing test**

Copy the `achievements` fixture array from `MeineAktivitaeten.test.tsx:16-61` into a `const FIXTURES: Achievement[]` and write:

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Achievement } from '../../api/client'
import AchievementsSection from './AchievementsSection'

const FIXTURES: Achievement[] = [ /* the 11 entries from MeineAktivitaeten.test.tsx */ ]

describe('AchievementsSection', () => {
  it('shows achieved and open achievements with progress', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Startschuss')).toBeInTheDocument()
    expect(screen.getByText('Ironman')).toBeInTheDocument()
    expect(screen.getByText(/Rad: 95\/190 km/)).toBeInTheDocument()
    expect(screen.queryByText(/Gesamt: 0\/0 km/)).not.toBeInTheDocument()
  })

  it('groups tiers into one card per discipline', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Rad')).toBeInTheDocument()
    expect(screen.getByText('Bronze')).toBeInTheDocument()
    expect(screen.getByText('Gold')).toBeInTheDocument()
    expect(screen.queryByText('Rad Silber')).not.toBeInTheDocument()
  })

  it('shows claimed one-time achievements with the owner name', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText(/vergeben an Lisa/)).toBeInTheDocument()
  })

  it('shows Frühstarter with warm-up progress instead of the race hint', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Frühstarter')).toBeInTheDocument()
    expect(screen.getByText(/50\/100 MM/)).toBeInTheDocument()
    expect(screen.queryByText(/bekommt nur die erste Person/)).not.toBeInTheDocument()
  })

  it('shows time at the top as a timer, in days from 24 h', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.getByText('Zeit an der Spitze')).toBeInTheDocument()
    expect(screen.getByText(/2,5 Tage/)).toBeInTheDocument()
  })

  it('never renders locked hidden achievements, only unlocked ones', () => {
    render(<AchievementsSection achievements={FIXTURES} onToggle={vi.fn()} />)
    expect(screen.queryByText('???')).not.toBeInTheDocument()
    expect(screen.queryByText(/Verstecktes Achievement/)).not.toBeInTheDocument()
    expect(screen.getByText('Hattrick')).toBeInTheDocument()
    expect(screen.getAllByText('🎩').length).toBeGreaterThan(0)
  })

  it('offers the showcase toggle only when onToggle is given', () => {
    const onToggle = vi.fn()
    const { unmount } = render(<AchievementsSection achievements={FIXTURES} onToggle={onToggle} />)
    fireEvent.click(screen.getByRole('button', { name: /wird getragen/ }))
    expect(onToggle).toHaveBeenCalledWith(expect.objectContaining({ key: 'hattrick' }))
    unmount()
    render(<AchievementsSection achievements={FIXTURES} />)
    expect(screen.queryByRole('button', { name: /wird getragen/ })).not.toBeInTheDocument()
  })

  it('says so when the list is empty', () => {
    render(<AchievementsSection achievements={[]} />)
    expect(screen.getByText(/Noch keine Achievements/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/achievements`
Expected: module not found.

- [ ] **Step 3: Create the files**

`constants.ts`:

```ts
export const TIER_ORDER = ['bronze', 'silber', 'gold'] as const
export const TIER_LABEL = { bronze: 'Bronze', silber: 'Silber', gold: 'Gold' } as const
// Personal specials without a race: the "only the first person" hint is wrong here.
export const NO_RACE_KEYS = new Set(['fruehstarter', 'early_bird'])
```

`ShowcaseToggle.tsx` — the old `EmojiToggle` (lines 247-263) with `onToggle` required, otherwise unchanged:

```tsx
import type { Achievement } from '../../api/client'

type Props = { a: Achievement; onToggle: (a: Achievement) => void }

// Wear the special emoji next to your name, or take it off.
export default function ShowcaseToggle({ a, onToggle }: Props) {
  if (!a.achieved || !a.emoji) return null
  const on = a.showcased ?? true
  return (
    <button
      type="button"
      onClick={() => onToggle(a)}
      className={`mt-2 flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
        on ? 'border-accent text-accent' : 'border-line text-ink-mute'
      }`}
      title="Emoji neben deinem Namen anzeigen"
    >
      <span className="text-sm">{a.emoji}</span>
      {on ? 'wird getragen' : 'abgelegt'}
    </button>
  )
}
```

`AchievementBadge.tsx`: move `AchievementBadge` (lines 421-462) verbatim, add `import Icon from '../ui/Icon'` and `import type { Achievement } from '../../api/client'`, `export default`.

`TierCard.tsx`: move `StufenKarte` (lines 265-313) renamed `TierCard` with prop `tiers: Achievement[]` (was `stufen`); imports `TIER_LABEL` from `./constants`, `Icon`, `Achievement`.

`OneTimeCard.tsx`: move `EinmalKarte` (lines 315-350) renamed `OneTimeCard`; props `{ a: Achievement; onToggle?: (a: Achievement) => void }`; last line becomes `{onToggle && <ShowcaseToggle a={a} onToggle={onToggle} />}`; `KEIN_WETTRENNEN` becomes `NO_RACE_KEYS` from `./constants`.

`TimeAtTopCard.tsx`: move `formatFuehrung` (renamed `formatLeadTime`) and `ZeitSpitzeKarte` (lines 352-390) renamed `TimeAtTopCard`.

`HiddenCard.tsx` — only the unlocked branch survives:

```tsx
import type { Achievement } from '../../api/client'
import ShowcaseToggle from './ShowcaseToggle'

type Props = { a: Achievement; onToggle?: (a: Achievement) => void }

// An unlocked hidden achievement. Locked ones are never rendered (spec chunk 1).
export default function HiddenCard({ a, onToggle }: Props) {
  return (
    <div className="rounded-xl border border-accent p-3 shadow-glow">
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className="text-sm font-bold text-accent">{a.title}</span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {a.unlocked_at && (
        <p className="mt-1 font-mono text-[10px] text-ink-mute">
          freigeschaltet am {new Date(a.unlocked_at).toLocaleDateString('de-DE')}
        </p>
      )}
      {onToggle && <ShowcaseToggle a={a} onToggle={onToggle} />}
    </div>
  )
}
```

`AchievementsSection.tsx`:

```tsx
import type { Achievement } from '../../api/client'
import AchievementBadge from './AchievementBadge'
import { TIER_ORDER } from './constants'
import HiddenCard from './HiddenCard'
import OneTimeCard from './OneTimeCard'
import TierCard from './TierCard'
import TimeAtTopCard from './TimeAtTopCard'

type Props = {
  achievements: Achievement[]
  // Present on the own profile only; without it no showcase toggles render.
  onToggle?: (a: Achievement) => void
}

export default function AchievementsSection({ achievements, onToggle }: Props) {
  if (achievements.length === 0)
    return <p className="text-sm text-ink-mute">Noch keine Achievements.</p>

  const tiers = achievements.filter((a) => a.tier !== null)
  const disciplines = [...new Set(tiers.map((a) => a.discipline))] as string[]
  const oneTime = achievements.filter((a) => a.emoji !== null && !a.hidden && a.tier === null)
  const hidden = achievements.filter((a) => a.hidden && a.achieved)
  const timeAtTop = achievements.find((a) => a.key === 'zeit_an_der_spitze')
  const classic = achievements.filter(
    (a) => a.tier === null && !a.hidden && a.emoji === null && a.key !== 'zeit_an_der_spitze',
  )

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {classic.map((a) => (
        <AchievementBadge key={a.key} a={a} />
      ))}
      {timeAtTop && <TimeAtTopCard a={timeAtTop} />}
      {disciplines.map((d) => (
        <TierCard
          key={d}
          tiers={TIER_ORDER.map((t) => tiers.find((s) => s.discipline === d && s.tier === t)).filter(
            (s): s is Achievement => Boolean(s),
          )}
        />
      ))}
      {oneTime.map((a) => (
        <OneTimeCard key={a.key} a={a} onToggle={onToggle} />
      ))}
      {hidden.map((a) => (
        <HiddenCard key={a.key} a={a} onToggle={onToggle} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/components/achievements`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/achievements
git commit -m "refactor(achievements): card components in their own folder, no locked hidden cards"
```

---

### Task 6: `ProfileAchievements` (queries + mutation)

**Files:**
- Create: `frontend/src/components/achievements/ProfileAchievements.tsx`

No separate unit test: it is covered through `Profil.test.tsx` in Task 8.

- [ ] **Step 1: Create the component**

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Achievement } from '../../api/client'
import AchievementsSection from './AchievementsSection'

type Props = { userId: number; own: boolean }

// Own profile: full list with progress and showcase toggles.
// Someone else's: only what they unlocked, read-only.
export default function ProfileAchievements({ userId, own }: Props) {
  const queryClient = useQueryClient()
  const { data: achievements = [], isLoading } = useQuery({
    queryKey: own ? ['achievements'] : ['user-achievements', userId],
    queryFn: () => (own ? api.achievements() : api.userAchievements(userId)),
  })
  const toggle = useMutation({
    mutationFn: ({ key, showcased }: { key: string; showcased: boolean }) =>
      api.patchAchievement(key, showcased),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['achievements'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
  })
  if (isLoading) return <p className="text-sm text-ink-mute">Lädt…</p>
  const onToggle = own
    ? (a: Achievement) => toggle.mutate({ key: a.key, showcased: !(a.showcased ?? true) })
    : undefined
  return <AchievementsSection achievements={achievements} onToggle={onToggle} />
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: no errors in the new file (errors elsewhere are addressed in later tasks; if any appear now, they must reference only Layout.tsx `isAdmin`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/achievements/ProfileAchievements.tsx
git commit -m "feat(achievements): profile achievements loader for own and other members"
```

---

### Task 7: MyMeters page replaces MeineAktivitaeten

**Files:**
- Create: `frontend/src/pages/MyMeters.tsx`
- Create: `frontend/src/pages/MyMeters.test.tsx`
- Delete: `frontend/src/pages/MeineAktivitaeten.tsx`, `frontend/src/pages/MeineAktivitaeten.test.tsx`

- [ ] **Step 1: Write the test**

`MyMeters.test.tsx`: copy `MeineAktivitaeten.test.tsx`, import `MyMeters from './MyMeters'`, drop the `achievements` mock entry and the whole `describe('Achievements')` block, keep the two list tests, and add:

```tsx
  it('has no achievements block any more', async () => {
    renderPage()
    await screen.findByText('Laufen')
    expect(screen.queryByText('Achievements')).not.toBeInTheDocument()
  })
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/MyMeters.test.tsx`
Expected: module not found.

- [ ] **Step 3: Create `MyMeters.tsx`**

Copy `MeineAktivitaeten.tsx` lines 1-181, then:
- line 3: `import { api, type Activity, type ActivityInput } from '../api/client'` (drop `Achievement`)
- line 11: `export default function MyMeters() {`
- delete line 168 `<Achievements />`
- keep `invalidate()` invalidating `['achievements']` (the profile reads them)
- add a doc comment above the component: `// MyMeters: quick entry plus the own entries of the season. Achievements live on the profile.`
Nothing after line 181 is copied.

- [ ] **Step 4: Delete the old page and test, run**

```bash
git rm frontend/src/pages/MeineAktivitaeten.tsx frontend/src/pages/MeineAktivitaeten.test.tsx
```
Run: `cd frontend && npx vitest run src/pages/MyMeters.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/MyMeters.tsx frontend/src/pages/MyMeters.test.tsx
git commit -m "feat(mymeters): activities page becomes MyMeters without the achievements block"
```

(App.tsx still imports the deleted page; it is rewritten in Task 9. Until then `tsc` fails on that import, which is expected.)

---

### Task 8: SettingsSection replaces ProfilModal

**Files:**
- Create: `frontend/src/components/profile/SettingsSection.tsx`
- Create: `frontend/src/components/profile/SettingsSection.test.tsx`
- Delete: `frontend/src/components/ui/ProfilModal.tsx`, `frontend/src/components/ui/ProfilModal.test.tsx`

- [ ] **Step 1: Write the test**

Copy `ProfilModal.test.tsx` to `SettingsSection.test.tsx` with these changes: import `SettingsSection from './SettingsSection'`; mock path `'../../api/client'` gains `logout: () => logout()` with `const logout = vi.fn()`; Toast mock path becomes `'../ui/Toast'`; `renderModal` becomes `renderSection` and wraps in `MemoryRouter`:

```tsx
function renderSection() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  qc.setQueryData(['me'], me)
  const utils = render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SettingsSection me={me} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { qc, ...utils }
}
```

Keep every existing Strava test (rename the describe blocks to `SettingsSection Strava section` / `SettingsSection Strava backfill`), and add:

```tsx
describe('SettingsSection footer', () => {
  it('links to the rules', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    renderSection()
    expect(await screen.findByRole('link', { name: 'Regeln' })).toHaveAttribute('href', '/regeln')
  })

  it('logout calls the API and clears the me query', async () => {
    stravaStatus.mockResolvedValue({ enabled: false, connected: false })
    logout.mockResolvedValue(undefined)
    const { qc } = renderSection()
    fireEvent.click(await screen.findByRole('button', { name: /Logout/ }))
    await waitFor(() => expect(logout).toHaveBeenCalled())
    await waitFor(() => expect(qc.getQueryData(['me'])).toBeNull())
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/profile/SettingsSection.test.tsx`
Expected: module not found.

- [ ] **Step 3: Create `SettingsSection.tsx`**

Start from `ProfilModal.tsx`. Changes:
- imports: drop `Modal`; add `import { Link } from 'react-router-dom'`, `import Card from '../ui/Card'`, `import SectionTitle from '../ui/SectionTitle'`, `import Icon from '../ui/Icon'`; other `./X` imports become `../ui/X`.
- signature: `export default function SettingsSection({ me }: { me: Me })`
- delete `trennenConfirm` reset-on-close logic and `close`; `save.onSuccess` no longer calls `close()`.
- add `const logout = useMutation({ mutationFn: () => api.logout(), onSuccess: () => queryClient.setQueryData(['me'], null) })`
- replace `<Modal open={open} onClose={close} title="Profil">` … `</Modal>` with `<Card>` `<SectionTitle>Einstellungen</SectionTitle>` … `</Card>`, and after the Speichern button add:

```tsx
        <div className="flex items-center justify-between border-t border-line/40 pt-3 text-xs">
          <Link to="/regeln" className="text-accent hover:underline">
            Regeln
          </Link>
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="flex items-center gap-1 text-ink-mute hover:text-danger"
          >
            <Icon name="logout" size={14} />
            Logout
          </button>
        </div>
```

- [ ] **Step 4: Delete the modal, run**

```bash
git rm frontend/src/components/ui/ProfilModal.tsx frontend/src/components/ui/ProfilModal.test.tsx
```
Run: `cd frontend && npx vitest run src/components/profile/SettingsSection.test.tsx`
Expected: all pass (7 Strava tests + 2 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/profile/SettingsSection.tsx frontend/src/components/profile/SettingsSection.test.tsx
git commit -m "feat(profile): settings section with logout replaces the profile modal"
```

---

### Task 9: Profile page gets achievements and settings

**Files:**
- Modify: `frontend/src/pages/Profil.tsx`
- Modify: `frontend/src/pages/Profil.test.tsx`

- [ ] **Step 1: Extend the test**

Add to the `api` mock: `achievements`, `userAchievements`, `patchAchievement`, `stravaStatus`, `patchMe`, `logout`:

```ts
    achievements: vi.fn().mockResolvedValue([
      { key: 'hattrick', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.', icon: 'blitz',
        achieved: true, progress: 1, parts: [], hidden: true, tier: null, discipline: null,
        unlocked_at: '2026-08-02T10:00:00Z', emoji: '🎩', showcased: true, claimed_by: null },
    ]),
    userAchievements: vi.fn().mockResolvedValue([
      { key: 'startschuss', title: 'Startschuss', description: 'Deine erste Aktivität ist im Kasten.',
        icon: 'fahne', achieved: true, progress: 1, parts: [{ label: 'Gesamt', current_km: 0.01, target_km: 0.01 }],
        hidden: false, tier: null, discipline: null, unlocked_at: null, emoji: null, showcased: null, claimed_by: null },
    ]),
    patchAchievement: vi.fn().mockResolvedValue({}),
    stravaStatus: vi.fn().mockResolvedValue({ enabled: false, connected: false }),
    patchMe: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
```
and `vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))`. Then add tests:

```tsx
  it("shows another member's unlocked achievements without toggles or settings", async () => {
    renderProfil()
    expect(await screen.findByText('Startschuss')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /wird getragen/ })).not.toBeInTheDocument()
    expect(screen.queryByText('Einstellungen')).not.toBeInTheDocument()
  })

  it('shows the own trophy room with toggles and the settings section', async () => {
    renderProfil('/profil/2?jahr=2026')
    expect(await screen.findByText('Hattrick')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /wird getragen/ })).toBeInTheDocument()
    expect(await screen.findByLabelText('Anzeigename')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Logout/ })).toBeInTheDocument()
  })
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/Profil.test.tsx`
Expected: the two new tests fail (texts missing).

- [ ] **Step 3: Modify `Profil.tsx`**

Imports: add `import ProfileAchievements from '../components/achievements/ProfileAchievements'` and `import SettingsSection from '../components/profile/SettingsSection'`. Between the Sportarten card and the Letzte Aktivitäten card insert:

```tsx
      <Card>
        <SectionTitle>Achievements</SectionTitle>
        <ProfileAchievements userId={user.user_id} own={me?.id === user.user_id} />
      </Card>
```

After the Letzte Aktivitäten card, as the last child of the outer `div`:

```tsx
      {me && me.id === user.user_id && <SettingsSection me={me} />}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/Profil.test.tsx`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Profil.tsx frontend/src/pages/Profil.test.tsx
git commit -m "feat(profile): trophy room and settings section on the profile page"
```

---

### Task 10: Arena page, routes, redirects, challenge links

**Files:**
- Create: `frontend/src/pages/Arena.tsx`, `frontend/src/pages/Arena.test.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/App.test.tsx`
- Modify: `frontend/src/components/challenges/ChallengeHeroCard.tsx:16`, `ChallengeRow.tsx:10`, `ChallengeDetail.tsx`

- [ ] **Step 1: Write the Arena test**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import Arena from './Arena'

const addons = vi.fn()
vi.mock('../api/client', () => ({ api: { addons: () => addons() } }))

function renderArena(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/arena" element={<Arena />}>
            <Route path="challenges" element={<p>Challenges-Inhalt</p>} />
            <Route path="challenges/:id" element={<p>Detail-Inhalt</p>} />
            <Route path="wetten" element={<p>Wetten-Inhalt</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Arena', () => {
  it('shows both pills when both add-ons are active and marks the current one', async () => {
    addons.mockResolvedValue([
      { key: 'challenges', label: 'Challenges', active: true },
      { key: 'sidebets', label: 'Wetten', active: true },
    ])
    renderArena('/arena/wetten')
    const wetten = await screen.findByRole('link', { name: /Wetten/ })
    expect(wetten).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: /Challenges/ })).toHaveAttribute('href', '/arena/challenges')
    expect(screen.getByText('Wetten-Inhalt')).toBeInTheDocument()
  })

  it('hides the pill row when only one add-on is active', async () => {
    addons.mockResolvedValue([{ key: 'challenges', label: 'Challenges', active: true }])
    renderArena('/arena/challenges')
    expect(await screen.findByText('Challenges-Inhalt')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Challenges/ })).not.toBeInTheDocument()
  })

  it('keeps the Challenges pill active on a detail page', async () => {
    addons.mockResolvedValue([
      { key: 'challenges', label: 'Challenges', active: true },
      { key: 'sidebets', label: 'Wetten', active: true },
    ])
    renderArena('/arena/challenges/5')
    expect(await screen.findByRole('link', { name: /Challenges/ })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByText('Detail-Inhalt')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Write the App routing test**

```tsx
// frontend/src/App.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const me = vi.fn()
vi.mock('./api/client', () => ({
  api: {
    me: () => me(),
    addons: vi.fn().mockResolvedValue([
      { key: 'challenges', label: 'Challenges', active: true },
      { key: 'sidebets', label: 'Wetten', active: true },
    ]),
    seasons: vi.fn().mockResolvedValue([]),
    feedUnseen: vi.fn().mockResolvedValue({ has_new: false }),
  },
  isUnauthorized: () => false,
}))
vi.mock('./pages/Vergleich', () => ({ default: () => <p>Vergleich-Seite</p> }))
vi.mock('./pages/Feed', () => ({ default: () => <p>Feed-Seite</p> }))
vi.mock('./pages/MyMeters', () => ({ default: () => <p>MyMeters-Seite</p> }))
vi.mock('./pages/Challenges', () => ({ default: () => <p>Challenges-Seite</p> }))
vi.mock('./pages/Wetten', () => ({ default: () => <p>Wetten-Seite</p> }))
vi.mock('./pages/Admin', () => ({ default: () => <p>Admin-Seite</p> }))
vi.mock('./pages/Regeln', () => ({ default: () => <p>Regeln-Seite</p> }))
vi.mock('./pages/Profil', () => ({ default: () => <p>Profil-Seite</p> }))
vi.mock('./pages/Datenschutz', () => ({ default: () => <p>Datenschutz-Seite</p> }))
vi.mock('./pages/Login', () => ({ default: () => <p>Login-Seite</p> }))
vi.mock('./pages/Einladung', () => ({ default: () => <p>Einladung-Seite</p> }))
vi.mock('./pages/PasswortReset', () => ({ default: () => <p>Reset-Seite</p> }))
vi.mock('./components/challenges/ChallengeDetail', () => ({ default: () => <p>Detail-Seite</p> }))

const member = { id: 2, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

function renderAt(path: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => me.mockResolvedValue(member))

describe('App routes', () => {
  it('redirects /aktivitaeten to MyMeters', async () => {
    renderAt('/aktivitaeten')
    expect(await screen.findByText('MyMeters-Seite')).toBeInTheDocument()
  })

  it('redirects /wetten into the Arena', async () => {
    renderAt('/wetten')
    expect(await screen.findByText('Wetten-Seite')).toBeInTheDocument()
  })

  it('redirects /challenges/:id into the Arena detail', async () => {
    renderAt('/challenges/7')
    expect(await screen.findByText('Detail-Seite')).toBeInTheDocument()
  })

  it('/arena lands on challenges', async () => {
    renderAt('/arena')
    expect(await screen.findByText('Challenges-Seite')).toBeInTheDocument()
  })

  it('sends non-admins from /admin home and lets admins in', async () => {
    renderAt('/admin')
    expect(await screen.findByText('Vergleich-Seite')).toBeInTheDocument()
    me.mockResolvedValue({ ...member, is_admin: true })
    renderAt('/admin')
    expect(await screen.findByText('Admin-Seite')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run both to verify failure**

Run: `cd frontend && npx vitest run src/pages/Arena.test.tsx src/App.test.tsx`
Expected: Arena module missing; App test fails on MyMeters import / routes.

- [ ] **Step 4: Create `Arena.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client'
import Icon from '../components/ui/Icon'

const VIEWS = [
  { to: '/arena/challenges', label: 'Challenges', icon: 'pokal', addon: 'challenges' },
  { to: '/arena/wetten', label: 'Wetten', icon: 'medaille', addon: 'sidebets' },
]

const pill = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 px-4 py-1 text-sm transition ${
    isActive ? 'font-bold text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute hover:text-ink'
  }`

// Arena: Challenges and Wetten under one tab. The pill row only appears when
// both add-ons are on; the sub-view is part of the URL so links and back work.
export default function Arena() {
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  const active = new Set(addons.filter((a) => a.active).map((a) => a.key))
  const views = VIEWS.filter((v) => active.has(v.addon))
  return (
    <div className="space-y-4">
      {views.length > 1 && (
        <div className="flex flex-wrap items-end gap-2">
          {views.map((v) => (
            <NavLink key={v.to} to={v.to} className={pill}>
              <Icon name={v.icon} size={14} />
              {v.label}
            </NavLink>
          ))}
        </div>
      )}
      <Outlet />
    </div>
  )
}
```

- [ ] **Step 5: Rewrite the logged-in routes in `App.tsx`**

Replace the `MeineAktivitaeten` import with `import MyMeters from './pages/MyMeters'`, add `import Arena from './pages/Arena'`, `import { arenaEntryPath } from './components/ui/tabs'`, and `useParams` to the react-router import. Replace `sidebetsAktiv` with:

```tsx
  const aktiveAddons = new Set((addons ?? []).filter((a) => a.active).map((a) => a.key))
  const sidebetsAktiv = aktiveAddons.has('sidebets')
```

Add above `App`:

```tsx
// Old deep link /challenges/:id → new home inside the Arena.
function RedirectChallenge() {
  const { id } = useParams()
  return <Navigate to={`/arena/challenges/${id}`} replace />
}
```

After the `if (!me)` block, wait for the add-ons so routes that depend on them never flash to `/`:

```tsx
  if (addons === undefined) return <p className="p-8 text-ink-mute">Lade…</p>
```

Logged-in routes:

```tsx
    <Routes>
      <Route element={<Layout me={me} />}>
        <Route path="/" element={<Vergleich />} />
        <Route path="/feed" element={<Feed />} />
        <Route path="/mymeters" element={<MyMeters />} />
        <Route path="/arena" element={<Arena />}>
          <Route index element={<Navigate to={arenaEntryPath(aktiveAddons)} replace />} />
          <Route path="challenges" element={<Challenges />} />
          <Route path="challenges/:id" element={<ChallengeDetail />} />
          {sidebetsAktiv && <Route path="wetten" element={<Wetten />} />}
        </Route>
        <Route path="/profil/:userId" element={<Profil />} />
        <Route path="/regeln" element={<Regeln />} />
        <Route path="/admin" element={me.is_admin ? <Admin /> : <Navigate to="/" replace />} />
        <Route path="/datenschutz" element={<Datenschutz />} />
        <Route path="/aktivitaeten" element={<Navigate to="/mymeters" replace />} />
        <Route path="/challenges" element={<Navigate to="/arena/challenges" replace />} />
        <Route path="/challenges/:id" element={<RedirectChallenge />} />
        <Route path="/wetten" element={<Navigate to="/arena/wetten" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
```

- [ ] **Step 6: Update challenge links**

`ChallengeHeroCard.tsx:16` and `ChallengeRow.tsx:10`: `` to={`/arena/challenges/${ch.id}`} ``. In `ChallengeDetail.tsx` add `Link` to the react-router import and render, as the first child of its top-level container:

```tsx
      <Link to="/arena/challenges" className="text-xs font-bold text-accent hover:underline">
        ← Arena
      </Link>
```

- [ ] **Step 7: Run the tests**

Run: `cd frontend && npx vitest run src/pages/Arena.test.tsx src/App.test.tsx src/pages/Challenges.test.tsx src/components/challenges`
Expected: all pass. If `App.test.tsx` fails because Layout renders something needing more API mocks, add that call to the mock rather than mocking Layout.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Arena.tsx frontend/src/pages/Arena.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/challenges
git commit -m "feat(nav): Arena with nested Challenges/Wetten routes, MyMeters route, legacy redirects"
```

---

### Task 11: Layout top bar and footer

**Files:**
- Modify: `frontend/src/components/ui/Layout.tsx`
- Create: `frontend/src/components/ui/Layout.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { Me } from '../../api/client'
import Layout from './Layout'

vi.mock('../../api/client', () => ({
  api: {
    seasons: vi.fn().mockResolvedValue([]),
    addons: vi.fn().mockResolvedValue([{ key: 'sidebets', label: 'Wetten', active: true }]),
    feedUnseen: vi.fn().mockResolvedValue({ has_new: false }),
  },
}))

const member: Me = { id: 2, username: 'erik', display_name: 'Erik', avatar: 'icon:laufen', is_admin: false }

function renderLayout(me: Me) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<Layout me={me} />}>
            <Route path="/" element={<p>Inhalt</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Layout', () => {
  it('links the avatar to the own profile and has no logout button', async () => {
    renderLayout(member)
    expect(await screen.findByRole('link', { name: /Mein Profil/ })).toHaveAttribute('href', '/profil/2')
    expect(screen.queryByRole('button', { name: /Logout/ })).not.toBeInTheDocument()
  })

  it('shows the gear only for admins', async () => {
    const { unmount } = renderLayout(member)
    await screen.findByText('Inhalt')
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument()
    unmount()
    renderLayout({ ...member, is_admin: true })
    expect(await screen.findByRole('link', { name: 'Admin' })).toHaveAttribute('href', '/admin')
  })

  it('renders the new tabs and the Regeln footer link', async () => {
    renderLayout(member)
    expect((await screen.findAllByText('MyMeters')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Arena')).length).toBeGreaterThan(0)
    expect(screen.queryByText('Aktivitäten')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Regeln' })).toHaveAttribute('href', '/regeln')
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/components/ui/Layout.test.tsx`
Expected: failures (avatar is a button, logout exists, tabs differ).

- [ ] **Step 3: Rewrite the bar and footer in `Layout.tsx`**

- Remove the `ProfilModal` import, the `profilOffen` state, the `logout` function, and `useQueryClient` if unused.
- `sichtbareTabs(TABS, { gestartet, aktiveAddons })`.
- Import `Link` from react-router-dom.
- Replace the three buttons after the desktop tab row with:

```tsx
        <div className="ml-auto flex items-center gap-3">
          {me.is_admin && (
            <NavLink to="/admin" aria-label="Admin" className="text-ink-mute hover:text-accent">
              <Icon name="zahnrad" size={18} />
            </NavLink>
          )}
          <button
            aria-label="Farbmodus wechseln"
            onClick={toggle}
            className="text-ink-mute hover:text-accent"
          >
            <Icon name={theme === 'dunkel' ? 'sonne' : 'mond'} size={18} />
          </button>
          <Link
            to={`/profil/${me.id}`}
            aria-label="Mein Profil"
            className="flex items-center gap-2 text-sm text-ink-soft hover:text-ink"
          >
            <Avatar value={me.avatar} size="sm" />
            <span className="hidden sm:inline">{me.display_name}</span>
          </Link>
        </div>
```

- Footer: before the Datenschutz link add `<NavLink to="/regeln" className="hover:text-accent">Regeln</NavLink><span className="mx-2">·</span>`.
- Remove `{profilOffen && <ProfilModal … />}`.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/components/ui/Layout.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Layout.tsx frontend/src/components/ui/Layout.test.tsx
git commit -m "feat(nav): avatar opens the profile, admin gear in the top bar, Regeln in the footer"
```

---

### Task 12: Admin panel section for hidden achievements

**Files:**
- Create: `frontend/src/components/admin/HiddenAchievementsAdmin.tsx`
- Modify: `frontend/src/pages/Admin.tsx:43-55`
- Modify: `frontend/src/pages/Admin.test.tsx`

- [ ] **Step 1: Extend the Admin test**

Add to the api mock:

```ts
    hiddenAchievementsAdmin: vi.fn().mockResolvedValue([
      { key: 'kletterkoenig', title: 'Kletterkönig', description: '1000 Höhenmeter an einem Tag.', emoji: '🏔️', unlocks: [] },
      { key: 'hattrick', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.', emoji: '🎩',
        unlocks: [{ user_id: 2, display_name: 'Lisa', avatar: 'icon:rad', unlocked_at: '2026-08-02T10:00:00Z' }] },
    ]),
```

and a new describe:

```tsx
describe('Admin hidden achievements', () => {
  it('lists every hidden achievement with its unlockers', async () => {
    renderAdmin()
    const section = (await screen.findByText('Kletterkönig')).closest('section')!
    const s = within(section)
    expect(s.getByText('noch niemand')).toBeInTheDocument()
    expect(s.getByText('Hattrick')).toBeInTheDocument()
    expect(s.getByText(/Lisa · 2\.8\.2026/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend && npx vitest run src/pages/Admin.test.tsx`
Expected: the new test fails (Kletterkönig not found).

- [ ] **Step 3: Create the section and mount it**

`HiddenAchievementsAdmin.tsx`:

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import Collapsible from '../ui/Collapsible'

// Read-only admin overview: the app never teases locked hidden achievements,
// so this is the one place to see what exists and who has it.
export default function HiddenAchievementsAdmin() {
  const { data: hidden = [] } = useQuery({
    queryKey: ['hidden-achievements-admin'],
    queryFn: api.hiddenAchievementsAdmin,
  })
  return (
    <Collapsible title="Versteckte Achievements">
      <ul className="space-y-2">
        {hidden.map((h) => (
          <li key={h.key} className="rounded-xl border border-line/40 p-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{h.emoji}</span>
              <span className="text-sm font-bold text-ink">{h.title}</span>
            </div>
            <p className="mt-1 text-xs text-ink-mute">{h.description}</p>
            <p className="mt-1 text-xs text-ink-soft">
              {h.unlocks.length === 0
                ? 'noch niemand'
                : h.unlocks
                    .map(
                      (u) =>
                        `${u.display_name} · ${new Date(u.unlocked_at).toLocaleDateString('de-DE')}`,
                    )
                    .join(', ')}
            </p>
          </li>
        ))}
      </ul>
    </Collapsible>
  )
}
```

In `Admin.tsx`: `import HiddenAchievementsAdmin from '../components/admin/HiddenAchievementsAdmin'` and add `<HiddenAchievementsAdmin />` after `<Einladungen />`.

- [ ] **Step 4: Run to verify pass**

Run: `cd frontend && npx vitest run src/pages/Admin.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/HiddenAchievementsAdmin.tsx frontend/src/pages/Admin.tsx frontend/src/pages/Admin.test.tsx
git commit -m "feat(admin): read-only list of hidden achievements and their unlockers"
```

---

### Task 13: Full verification and PR

- [ ] **Step 1: Frontend suite, lint, types**

```bash
cd frontend && npx vitest run && npx eslint . && npx tsc -b
```
Expected: vitest all green; eslint reports only the pre-existing errors in `Feed.tsx`/`ReactionBar.tsx` (compare against `git stash`-free baseline: run `git diff --stat main -- src/pages/Feed.tsx src/components/feed/ReactionBar.tsx` and confirm those files are untouched); tsc clean.

- [ ] **Step 2: Backend suite**

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q
```
Expected: all pass.

- [ ] **Step 3: Grep for leftovers**

```bash
grep -rn "MeineAktivitaeten\|ProfilModal\|adminOnly\|isAdmin" frontend/src
```
Expected: no matches.

- [ ] **Step 4: Production build**

```bash
cd frontend && npm run build
```
Expected: build succeeds.

- [ ] **Step 5: Push and open the PR**

```bash
git push -u origin feature/frontend-navigation
gh pr create --title "Frontend navigation restructure (redesign chunk 1)" --body-file <body>
```
Body: summary of the four tabs, Arena, MyMeters, profile trophy room + settings, hidden achievements policy, the two new endpoints, the redirects, and the test commands run; ends with the generated-with footer and session link.
