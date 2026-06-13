# UI-Cleanup, Sport-Mix & Einladungs-Flow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Frontend auf einen flachen „Race-Telemetry/HUD"-Look umstellen, die Vergleichsseite neu ordnen (Sport-Mix statt Karte), Aktivitäten gruppieren, das Admin-Strava-Mapping als Zuordnungstabelle bauen und Mitglieder über einen einmaligen Einladungslink (mit QR) selbst registrieren lassen.

**Architecture:** Reines Frontend für Punkte 1–6 (React 19 + Tailwind v4, CSS-Variablen-Theme). Punkt 7 ergänzt ein `Invite`-Modell + Router im FastAPI-Backend und eine öffentliche `/einladung/:token`-Route im Frontend. Auth-Mechanismus (Argon2 + signiertes Session-Cookie) bleibt unverändert.

**Tech Stack:** FastAPI, SQLModel, SQLite, pytest · React 19, react-router-dom 7, @tanstack/react-query, Tailwind v4, recharts, vitest + Testing Library. Neue Frontend-Abhängigkeit: `qrcode.react`.

**Spec:** `docs/superpowers/specs/2026-06-13-ui-cleanup-und-invites-design.md`

---

## File Structure

**Backend**
- Modify `backend/app/models.py` — neues `Invite`-Modell
- Create `backend/app/routers/invites.py` — Einladungs-Endpoints
- Modify `backend/app/main.py` — Router registrieren
- Create `backend/tests/test_invites.py` — Tests

**Frontend**
- Modify `frontend/src/index.css` — Fonts, Tokens, HUD-Textur, Animationen
- Create `frontend/src/components/ui/SectionTitle.tsx` — mono Versal-Sektionskopf (ersetzt lokale `H`)
- Modify `frontend/src/api/client.ts` — Invite-Typen + Methoden
- Modify `frontend/src/components/ui/ProfilModal.tsx` — schlanke Strava-Zeile
- Create `frontend/src/components/comparison/SportMix.tsx` (+ Test) — gestapelte Balken
- Modify `frontend/src/pages/Vergleich.tsx` — Reihenfolge + Sport-Mix, Karte raus
- Delete `frontend/src/components/comparison/WanderKarte.tsx`
- Modify `frontend/src/pages/MeineAktivitaeten.tsx` (+ Test) — Kategorie-Gruppen
- Modify `frontend/src/pages/Admin.tsx` — Mapping-Tabelle, flach, Einladungen statt direkter User-Anlage, Kartenupload raus
- Create `frontend/src/pages/Einladung.tsx` (+ Test) — öffentliche Registrierung
- Modify `frontend/src/App.tsx` — öffentliche Invite-Route

Build-Reihenfolge: erst Backend-Invites (in sich testbar), dann visuelle Grundlage (Task 4), dann die Screens.

---

## Task 1: `Invite`-Modell

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: Modell ergänzen**

In `backend/app/models.py` ans Dateiende anfügen (nutzt die vorhandene `utcnow`-Funktion und `datetime`-Imports oben):

```python
class Invite(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    created_by: int = Field(foreign_key="user.id")
    display_name: str | None = None
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    used_at: datetime | None = None
    used_by_user_id: int | None = Field(default=None, foreign_key="user.id")
```

- [ ] **Step 2: Import-Smoke-Test**

Run: `cd backend && uv run python -c "from app.models import Invite; print(Invite.__tablename__)"`
Expected: gibt `invite` aus, kein Fehler.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models.py
git commit -m "feat(invites): Invite-Modell"
```

---

## Task 2: Einladungs-Router (TDD)

**Files:**
- Create: `backend/app/routers/invites.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_invites.py`

- [ ] **Step 1: Failing tests schreiben**

Create `backend/tests/test_invites.py`:

```python
from datetime import datetime, timedelta, timezone

from app.models import Invite
from tests.conftest import login, make_user


def _create_invite(client):
    return client.post("/api/invites", json={"display_name": "Lisa"})


def test_create_invite_admin_only(client, session):
    make_user(session)  # kein Admin
    login(client)
    assert _create_invite(client).status_code == 403


def test_admin_creates_invite_returns_token_and_url(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    r = _create_invite(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["token"]
    assert body["url"].endswith("/einladung/" + body["token"])
    assert body["used_at"] is None


def test_public_can_check_valid_token(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    client.post("/api/auth/logout")
    r = client.get(f"/api/invites/{token}")
    assert r.status_code == 200
    assert r.json() == {"valid": True, "display_name": "Lisa", "expired": False, "used": False}


def test_unknown_token_is_invalid(client):
    r = client.get("/api/invites/does-not-exist")
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_accept_creates_user_and_logs_in(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    client.post("/api/auth/logout")
    r = client.post(
        f"/api/invites/{token}/accept",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "lisa"
    assert r.json()["is_admin"] is False
    # Cookie gesetzt → /me funktioniert ohne erneuten Login
    assert client.get("/api/auth/me").json()["username"] == "lisa"


def test_accept_is_single_use(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    body = {"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"}
    assert client.post(f"/api/invites/{token}/accept", json=body).status_code == 200
    body2 = {**body, "username": "tom"}
    assert client.post(f"/api/invites/{token}/accept", json=body2).status_code == 409


def test_accept_rejects_expired(client, session):
    admin = make_user(session, username="chef", is_admin=True)
    invite = Invite(
        token="abgelaufen",
        created_by=admin.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(invite)
    session.commit()
    r = client.post(
        "/api/invites/abgelaufen/accept",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"},
    )
    assert r.status_code == 410


def test_accept_rejects_duplicate_username(client, session):
    make_user(session, username="lisa")  # existiert schon
    admin = make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    token = _create_invite(client).json()["token"]
    client.post("/api/auth/logout")
    r = client.post(
        f"/api/invites/{token}/accept",
        json={"username": "lisa", "password": "pw456", "display_name": "Lisa", "avatar": "icon:rad"},
    )
    assert r.status_code == 409


def test_admin_can_list_and_delete(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")
    invite_id = _create_invite(client).json()["id"]
    assert len(client.get("/api/invites").json()) == 1
    assert client.delete(f"/api/invites/{invite_id}").status_code == 204
    assert client.get("/api/invites").json() == []
```

- [ ] **Step 2: Tests laufen lassen (rot)**

Run: `cd backend && uv run pytest tests/test_invites.py -v`
Expected: FAIL/ERROR — `/api/invites` existiert noch nicht (404/Import-Fehler).

- [ ] **Step 3: Router implementieren**

Create `backend/app/routers/invites.py`:

```python
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import auth, config
from ..deps import get_session, require_admin
from ..models import Invite, User, utcnow
from .auth_router import MeOut

router = APIRouter(prefix="/api/invites", tags=["invites"])

INVITE_TTL = timedelta(days=7)


def _invite_url(token: str) -> str:
    base = config.PUBLIC_BASE_URL or ""
    return f"{base}/einladung/{token}"


def _is_expired(invite: Invite) -> bool:
    exp = invite.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < datetime.now(timezone.utc)


class InviteCreate(BaseModel):
    display_name: str | None = None
    is_admin: bool = False


class InviteOut(BaseModel):
    id: int
    token: str
    url: str
    display_name: str | None
    is_admin: bool
    expires_at: datetime
    used_at: datetime | None


class InvitePublic(BaseModel):
    valid: bool
    display_name: str | None = None
    expired: bool = False
    used: bool = False


class InviteAccept(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=4)
    display_name: str = Field(min_length=1)
    avatar: str = "icon:laufen"


def _to_out(invite: Invite) -> InviteOut:
    return InviteOut(
        id=invite.id,
        token=invite.token,
        url=_invite_url(invite.token),
        display_name=invite.display_name,
        is_admin=invite.is_admin,
        expires_at=invite.expires_at,
        used_at=invite.used_at,
    )


@router.post("", response_model=InviteOut, status_code=201)
def create_invite(
    data: InviteCreate,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
):
    invite = Invite(
        token=secrets.token_urlsafe(16),
        created_by=admin.id,
        display_name=data.display_name,
        is_admin=data.is_admin,
        expires_at=utcnow() + INVITE_TTL,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return _to_out(invite)


@router.get("", response_model=list[InviteOut], dependencies=[Depends(require_admin)])
def list_invites(session: Session = Depends(get_session)):
    invites = session.exec(select(Invite).order_by(Invite.created_at.desc())).all()
    return [_to_out(i) for i in invites]


@router.delete("/{invite_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_invite(invite_id: int, session: Session = Depends(get_session)):
    invite = session.get(Invite, invite_id)
    if invite is not None:
        session.delete(invite)
        session.commit()


@router.get("/{token}", response_model=InvitePublic)
def check_invite(token: str, session: Session = Depends(get_session)):
    invite = session.exec(select(Invite).where(Invite.token == token)).first()
    if invite is None:
        return InvitePublic(valid=False)
    used = invite.used_at is not None
    expired = _is_expired(invite)
    return InvitePublic(
        valid=not used and not expired,
        display_name=invite.display_name,
        expired=expired,
        used=used,
    )


@router.post("/{token}/accept", response_model=MeOut)
def accept_invite(
    token: str,
    data: InviteAccept,
    response: Response,
    session: Session = Depends(get_session),
):
    invite = session.exec(select(Invite).where(Invite.token == token)).first()
    if invite is None:
        raise HTTPException(status_code=404, detail="Einladung ungültig")
    if invite.used_at is not None:
        raise HTTPException(status_code=409, detail="Einladung bereits eingelöst")
    if _is_expired(invite):
        raise HTTPException(status_code=410, detail="Einladung abgelaufen")
    if session.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(status_code=409, detail="Benutzername vergeben")
    user = User(
        username=data.username,
        password_hash=auth.hash_password(data.password),
        display_name=data.display_name,
        avatar=data.avatar,
        is_admin=invite.is_admin,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    invite.used_at = utcnow()
    invite.used_by_user_id = user.id
    session.add(invite)
    session.commit()
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user.id),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return user
```

- [ ] **Step 4: Router registrieren**

In `backend/app/main.py` die Import-Zeile der Router um `invites` ergänzen und den Router einhängen:

```python
from .routers import (
    activities,
    auth_router,
    categories,
    comparison,
    invites,
    seasons,
    strava_router,
    users,
)
```

und nach `app.include_router(comparison.router)`:

```python
app.include_router(invites.router)
```

- [ ] **Step 5: Tests laufen lassen (grün)**

Run: `cd backend && uv run pytest tests/test_invites.py -v`
Expected: PASS (alle 9 Tests).

- [ ] **Step 6: Volle Suite + Commit**

Run: `cd backend && uv run pytest`
Expected: PASS.

```bash
git add backend/app/routers/invites.py backend/app/main.py backend/tests/test_invites.py
git commit -m "feat(invites): einladungs-router mit selbstregistrierung"
```

---

## Task 3: API-Client um Invites erweitern

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Typen ergänzen**

In `frontend/src/api/client.ts` nach dem `StravaStatus`-Typ einfügen:

```typescript
export type Invite = {
  id: number
  token: string
  url: string
  display_name: string | null
  is_admin: boolean
  expires_at: string
  used_at: string | null
}
export type InvitePublic = {
  valid: boolean
  display_name?: string | null
  expired?: boolean
  used?: boolean
}
```

- [ ] **Step 2: Methoden ergänzen**

Im `api`-Objekt (nach `disconnectStrava`) ergänzen:

```typescript
  createInvite: (b: { display_name?: string | null; is_admin?: boolean }) =>
    request<Invite>('/api/invites', post(b)),
  listInvites: () => request<Invite[]>('/api/invites'),
  deleteInvite: (id: number) => request<void>(`/api/invites/${id}`, { method: 'DELETE' }),
  getInvite: (token: string) => request<InvitePublic>(`/api/invites/${token}`),
  acceptInvite: (
    token: string,
    b: { username: string; password: string; display_name: string; avatar: string },
  ) => request<Me>(`/api/invites/${token}/accept`, post(b)),
```

- [ ] **Step 3: Typecheck + Commit**

Run: `cd frontend && npx tsc -b`
Expected: kein Fehler.

```bash
git add frontend/src/api/client.ts
git commit -m "feat(invites): api-client methoden & typen"
```

---

## Task 4: Visuelle Grundlage — Fonts, Tokens, HUD-Textur

**Files:**
- Modify: `frontend/src/index.css`
- Create: `frontend/src/components/ui/SectionTitle.tsx`

- [ ] **Step 1: Fonts + Tokens in `index.css`**

Ganz oben in `frontend/src/index.css` **vor** `@import 'tailwindcss';` die Google-Fonts importieren:

```css
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Spline+Sans+Mono:wght@400;500;700&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
@import 'tailwindcss';
```

Im `:root`-Block (heller Modus) `--t-ink-tech` ergänzen:

```css
  --t-ink-tech: #5a7e8a;
```

Im `.dark`-Block ergänzen:

```css
  --t-ink-tech: #3d6470;
```

Im `@theme inline`-Block die Font- und Farb-Tokens ergänzen:

```css
  --color-ink-tech: var(--t-ink-tech);
  --font-display: 'Rajdhani', system-ui, sans-serif;
  --font-mono: 'Spline Sans Mono', ui-monospace, monospace;
  --font-body: 'Hanken Grotesk', system-ui, sans-serif;
```

Den `body`-Block auf die Body-Font setzen:

```css
body {
  @apply bg-surface text-ink;
  font-family: var(--font-body);
}
```

Am Dateiende die HUD-Textur und die gestaffelte Reihen-Animation ergänzen:

```css
/* Dezentes HUD-Grid als Flächen-Textur */
.hud-grid {
  background-image:
    linear-gradient(var(--t-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--t-line) 1px, transparent 1px);
  background-size: 44px 44px;
  background-position: center;
  opacity: 0.06;
}

@keyframes reihe-rein {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
}
.reihe-rein {
  animation: reihe-rein 0.45s ease-out both;
}
```

- [ ] **Step 2: `SectionTitle`-Komponente**

Create `frontend/src/components/ui/SectionTitle.tsx`:

```tsx
export default function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 border-b border-line/40 pb-1.5 font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-ink-tech">
      <span className="text-accent">// </span>
      {children}
    </h2>
  )
}
```

- [ ] **Step 3: Build prüfen**

Run: `cd frontend && npm run build`
Expected: Build erfolgreich (Fonts/Tokens valide, `font-display`/`font-mono`/`text-ink-tech` als Utilities verfügbar).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/index.css frontend/src/components/ui/SectionTitle.tsx
git commit -m "feat(ui): HUD-grundlage – fonts, tokens, textur, section-title"
```

---

## Task 5: Strava-Zeile im Profil verschlanken

**Files:**
- Modify: `frontend/src/components/ui/ProfilModal.tsx`
- Test: `frontend/src/components/ui/ProfilModal.test.tsx`

Hinweis: Die bestehenden Tests prüfen die Button-Namen „Mit Strava verbinden" / „Strava trennen". Wir behalten diese Namen bei, ändern nur das Layout — so bleiben die Tests gültig.

- [ ] **Step 1: Strava-Block ersetzen**

In `frontend/src/components/ui/ProfilModal.tsx` den gesamten `{strava?.enabled && ( ... )}`-Block (die umrahmte Box) durch eine schlanke Zeile ersetzen:

```tsx
        {strava?.enabled && (
          <div className="flex items-center justify-between border-t border-line/40 pt-3">
            <span className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-ink-tech">
              Strava
              {strava.connected && strava.backfill?.state !== 'running' && (
                <span className="text-accent">✓ Verbunden</span>
              )}
            </span>
            {strava.connected ? (
              strava.backfill?.state === 'running' ? (
                <span className="flex items-center gap-2 text-sm text-ink-mute">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                  Importiere… {strava.backfill.done} von {strava.backfill.total}
                </span>
              ) : (
                <button
                  type="button"
                  onClick={() => trennen.mutate()}
                  disabled={trennen.isPending}
                  className="text-sm text-ink-mute hover:text-danger"
                >
                  Strava trennen
                </button>
              )
            ) : (
              <button
                type="button"
                onClick={() => {
                  window.location.href = '/api/strava/connect'
                }}
                className="text-sm text-accent hover:underline"
              >
                Mit Strava verbinden
              </button>
            )}
          </div>
        )}
```

`Button`-Import bleibt für den Speichern-Button erhalten.

- [ ] **Step 2: Tests laufen lassen**

Run: `cd frontend && npx vitest run src/components/ui/ProfilModal.test.tsx`
Expected: PASS (alle Strava-Tests, da Button-Namen unverändert).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/ProfilModal.tsx
git commit -m "feat(ui): strava als schlanke profil-zeile statt button-box"
```

---

## Task 6: Sport-Mix-Ansicht (TDD) + Vergleich neu ordnen

**Files:**
- Create: `frontend/src/components/comparison/SportMix.tsx`
- Test: `frontend/src/components/comparison/SportMix.test.tsx`
- Modify: `frontend/src/pages/Vergleich.tsx`
- Delete: `frontend/src/components/comparison/WanderKarte.tsx`

- [ ] **Step 1: Failing test**

Create `frontend/src/components/comparison/SportMix.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Comparison } from '../../api/client'
import SportMix from './SportMix'

const data: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  map_image: null,
  users: [
    {
      user_id: 1,
      display_name: 'Erik',
      avatar: 'icon:laufen',
      rank: 1,
      total_scaled_km: 300,
      by_category: [
        { category_id: 1, name: 'Laufen', color: '#f00', icon: 'laufen', scaled_km: 200 },
        { category_id: 2, name: 'Radfahren', color: '#00f', icon: 'rad', scaled_km: 100 },
      ],
      segments: [],
      cumulative: [],
    },
  ],
}

describe('SportMix', () => {
  it('zeigt Person, gewertete Gesamtsumme und Kategorie-Legende', () => {
    render(<SportMix data={data} />)
    expect(screen.getByText('Erik')).toBeInTheDocument()
    expect(screen.getByText('300')).toBeInTheDocument()
    // Legende listet beide Kategorien
    expect(screen.getByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText('Radfahren')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Test rot**

Run: `cd frontend && npx vitest run src/components/comparison/SportMix.test.tsx`
Expected: FAIL — `SportMix` existiert nicht.

- [ ] **Step 3: Komponente implementieren**

Create `frontend/src/components/comparison/SportMix.tsx`:

```tsx
import type { Comparison } from '../../api/client'
import Avatar from '../ui/Avatar'

export default function SportMix({ data }: { data: Comparison }) {
  // Alle vorkommenden Kategorien für die Legende sammeln (Reihenfolge stabil).
  const legende = new Map<number, { name: string; color: string }>()
  for (const u of data.users)
    for (const c of u.by_category) legende.set(c.category_id, { name: c.name, color: c.color })

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        {data.users.map((u, i) => {
          const gesamt = u.by_category.reduce((s, c) => s + c.scaled_km, 0)
          return (
            <div
              key={u.user_id}
              className="reihe-rein flex items-center gap-3"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <span className="w-7 font-mono text-sm font-bold tabular-nums text-ink-tech">
                P{u.rank}
              </span>
              <Avatar value={u.avatar} size="sm" />
              <span className="w-24 truncate text-sm font-bold text-ink">{u.display_name}</span>
              <div className="flex h-4 flex-1 overflow-hidden rounded-full bg-surface">
                {u.by_category.map((c) => (
                  <span
                    key={c.category_id}
                    title={`${c.name}: ${Math.round(c.scaled_km)} km`}
                    className="balken-wachsen h-full"
                    style={{
                      width: gesamt ? `${(c.scaled_km / gesamt) * 100}%` : 0,
                      background: c.color,
                    }}
                  />
                ))}
              </div>
              <span className="w-16 text-right font-mono text-sm font-bold tabular-nums text-ink">
                {Math.round(gesamt)}
              </span>
            </div>
          )
        })}
      </div>
      <ul className="flex flex-wrap gap-3 text-xs text-ink-soft">
        {[...legende.entries()].map(([id, c]) => (
          <li key={id} className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-full" style={{ background: c.color }} />
            {c.name}
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: Test grün**

Run: `cd frontend && npx vitest run src/components/comparison/SportMix.test.tsx`
Expected: PASS.

- [ ] **Step 5: Vergleich neu ordnen + Karte entfernen**

In `frontend/src/pages/Vergleich.tsx`:

1. Import `WanderKarte` entfernen, `SportMix` importieren:

```tsx
import SportMix from '../components/comparison/SportMix'
```

2. `ANSICHTEN`/`Ansicht` und Default-State ersetzen:

```tsx
const ANSICHTEN = [
  { key: 'rennen', label: 'Rennen', icon: 'fahne' },
  { key: 'verlauf', label: 'Verlauf', icon: 'chart' },
  { key: 'sportmix', label: 'Sport-Mix', icon: 'medaille' },
] as const
type Ansicht = (typeof ANSICHTEN)[number]['key']
```

```tsx
  const [ansicht, setAnsicht] = useState<Ansicht>('rennen')
```

3. Die Render-Zeilen ganz unten ersetzen:

```tsx
      {data && ansicht === 'rennen' && <RaceBahnen data={data} />}
      {data && ansicht === 'verlauf' && <JahresVerlauf data={data} />}
      {data && ansicht === 'sportmix' && <SportMix data={data} />}
```

Hinweis: Falls `medaille` kein vorhandenes Icon ist, ein vorhandenes aus `frontend/src/components/ui/icons.ts` wählen (prüfen mit Grep). `medaille` wird im Code bereits genutzt (Default-Kategorie-Icon), ist also vorhanden.

- [ ] **Step 6: `WanderKarte.tsx` löschen**

```bash
git rm frontend/src/components/comparison/WanderKarte.tsx
```

- [ ] **Step 7: Voller Frontend-Check**

Run: `cd frontend && npx tsc -b && npx vitest run && npm run build`
Expected: PASS, kein ungenutzter Import, Build grün. (Falls `pathMath.ts`/`spreadBadges`/`progressFraction` jetzt nirgends mehr importiert werden, ist das ok — Module bleiben bestehen; optionaler Cleanup später.)

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(vergleich): sport-mix statt karte, reihenfolge rennen→verlauf→sport-mix"
```

---

## Task 7: Aktivitäten als ausklappbare Kategorie-Gruppen

**Files:**
- Modify: `frontend/src/pages/MeineAktivitaeten.tsx`
- Test: `frontend/src/pages/MeineAktivitaeten.test.tsx`

- [ ] **Step 1: Test erweitern**

In `frontend/src/pages/MeineAktivitaeten.test.tsx` einen Test ergänzen, der die Gruppierung prüft. Beide Mock-Aktivitäten liegen in Kategorie 1 (Laufen), gewertet 20 + 12 = 32 km, default eingeklappt → Einträge nicht sichtbar, Gruppenkopf mit Summe sichtbar:

```tsx
import { fireEvent } from '@testing-library/react'

// ... innerhalb describe('MeineAktivitaeten', ...):

  it('gruppiert nach Kategorie, default eingeklappt, klappt auf Klick auf', async () => {
    renderPage()
    // Gruppenkopf zeigt Anzahl und gewertete Summe
    expect(await screen.findByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText(/2 Einträge/)).toBeInTheDocument()
    expect(screen.getByText('32 km')).toBeInTheDocument()
    // Eingeklappt: kein Strava-Badge sichtbar
    expect(screen.queryByText('Strava')).not.toBeInTheDocument()
    // Aufklappen
    fireEvent.click(screen.getByText('Laufen'))
    expect(await screen.findByText('Strava')).toBeInTheDocument()
  })
```

Den bestehenden Test „zeigt genau ein Strava-Badge" anpassen: er muss zuerst die Gruppe aufklappen, da default eingeklappt:

```tsx
  it('zeigt genau ein Strava-Badge (nur für die Strava-Aktivität)', async () => {
    renderPage()
    fireEvent.click(await screen.findByText('Laufen'))
    const badges = screen.getAllByText('Strava')
    expect(badges).toHaveLength(1)
  })
```

(`fireEvent` aus `@testing-library/react` importieren.)

- [ ] **Step 2: Test rot**

Run: `cd frontend && npx vitest run src/pages/MeineAktivitaeten.test.tsx`
Expected: FAIL (noch keine Gruppierung).

- [ ] **Step 3: Liste auf Gruppen umstellen**

In `frontend/src/pages/MeineAktivitaeten.tsx`:

1. `useState` für aufgeklappte Gruppen ergänzen (nach den bestehenden `useState`-Zeilen):

```tsx
  const [offen, setOffen] = useState<Set<number>>(new Set())
  const toggle = (catId: number) =>
    setOffen((s) => {
      const next = new Set(s)
      next.has(catId) ? next.delete(catId) : next.add(catId)
      return next
    })
```

2. Vor dem `return` die Gruppierung berechnen (nach `const gesamt = ...`):

```tsx
  const gruppen = [...catById.values()]
    .map((cat) => {
      const eintraege = activities.filter((a) => a.category_id === cat.id)
      const summe = eintraege.reduce((s, a) => s + a.scaled_km, 0)
      return { cat, eintraege, summe }
    })
    .filter((g) => g.eintraege.length > 0)
    .sort((a, b) => b.summe - a.summe)
```

3. Die bestehende `<ul className="space-y-2"> ... </ul>` (die flache Aktivitätsliste) durch die gruppierte Darstellung ersetzen:

```tsx
      <div className="space-y-1">
        {gruppen.map(({ cat, eintraege, summe }) => {
          const auf = offen.has(cat.id)
          return (
            <div key={cat.id} className="border-b border-line/30 last:border-0">
              <button
                type="button"
                onClick={() => toggle(cat.id)}
                className="flex w-full items-center gap-3 py-2.5 text-left"
              >
                <Icon
                  name="chevron"
                  size={14}
                  className={`text-ink-mute transition ${auf ? 'rotate-180' : ''}`}
                />
                <Icon name={cat.icon} size={20} className="shrink-0 text-accent" />
                <span className="flex-1 text-sm font-bold text-ink">{cat.name}</span>
                <span className="text-xs text-ink-mute">{eintraege.length} Einträge</span>
                <span className="w-20 text-right font-mono text-sm font-bold tabular-nums text-accent">
                  {Math.round(summe)} km
                </span>
              </button>
              {auf && (
                <ul className="space-y-1 pb-2 pl-8">
                  {eintraege.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-3 border-t border-line/20 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-ink">
                          <span className="font-mono tabular-nums">{a.distance_km}</span> km
                          <span className="text-accent"> → {a.scaled_km} km</span>
                          {a.edited && (
                            <span className="ml-2 text-xs text-ink-mute">(bearbeitet)</span>
                          )}
                          {a.source === 'strava' && (
                            <span className="ml-2 rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
                              Strava
                            </span>
                          )}
                        </p>
                        <p className="truncate text-xs text-ink-mute">
                          {a.date}
                          {a.duration_min ? ` · ${a.duration_min} min` : ''}
                          {a.note ? ` · ${a.note}` : ''}
                        </p>
                      </div>
                      <button
                        aria-label="Bearbeiten"
                        className="text-ink-mute hover:text-accent"
                        onClick={() => setEditing(a)}
                      >
                        <Icon name="stift" size={16} />
                      </button>
                      <button
                        aria-label="Löschen"
                        className="text-ink-mute hover:text-danger"
                        onClick={() => setLoeschId(a.id)}
                      >
                        <Icon name="papierkorb" size={16} />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
        {activities.length === 0 && <p className="text-sm text-ink-mute">Noch keine Einträge.</p>}
      </div>
```

Die Überschriften-Zeile darüber (`Meine Einträge {year}` + Gesamtsumme) auf `SectionTitle`-Stil bzw. mono-Zahlen anpassen ist optional; funktional bleibt sie.

- [ ] **Step 4: Tests grün**

Run: `cd frontend && npx vitest run src/pages/MeineAktivitaeten.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/MeineAktivitaeten.tsx frontend/src/pages/MeineAktivitaeten.test.tsx
git commit -m "feat(aktivitaeten): ausklappbare kategorie-gruppen mit gewerteter summe"
```

---

## Task 8: Admin — Strava-Zuordnungstabelle, flach, Kartenupload raus

**Files:**
- Modify: `frontend/src/pages/Admin.tsx`
- Test: `frontend/src/pages/Admin.test.tsx` (neu)

Diese Aufgabe baut die `Kategorien`- und `Jahr`-Abschnitte flach um, entfernt die Pills aus jeder Kategoriezeile, entfernt den Kartenbild-Upload und ergänzt eine neue `StravaMapping`-Sektion. Die `NeuerUser`-Sektion bleibt in dieser Aufgabe unverändert (Task 9 ersetzt sie).

- [ ] **Step 1: Failing test für die Zuordnungslogik**

Create `frontend/src/pages/Admin.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Admin from './Admin'

const patchCategory = vi.fn().mockResolvedValue({})

vi.mock('../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Laufen', factor: 4, color: '#f00', icon: 'laufen', default_km: 5, is_active: true, strava_sport_types: ['Run'] },
      { id: 2, name: 'Radfahren', factor: 1, color: '#00f', icon: 'rad', default_km: 20, is_active: true, strava_sport_types: [] },
    ]),
    patchCategory: (...a: unknown[]) => patchCategory(...a),
    seasons: vi.fn().mockResolvedValue([]),
    listInvites: vi.fn().mockResolvedValue([]),
  },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAdmin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <Admin />
    </QueryClientProvider>,
  )
}

beforeEach(() => patchCategory.mockClear())

describe('Admin Strava-Zuordnung', () => {
  it('weist einen Typ neu zu und entfernt ihn aus der alten Kategorie', async () => {
    renderAdmin()
    // Zeile für "Run" finden; aktuell Kategorie 1 (Laufen). Auf Radfahren umstellen.
    const select = await screen.findByLabelText('Zuordnung Run')
    fireEvent.change(select, { target: { value: '2' } })
    await waitFor(() => {
      // Run aus Laufen (id 1) entfernt:
      expect(patchCategory).toHaveBeenCalledWith(1, { strava_sport_types: [] })
      // Run zu Radfahren (id 2) hinzugefügt:
      expect(patchCategory).toHaveBeenCalledWith(2, { strava_sport_types: ['Run'] })
    })
  })
})
```

- [ ] **Step 2: Test rot**

Run: `cd frontend && npx vitest run src/pages/Admin.test.tsx`
Expected: FAIL — Label „Zuordnung Run" existiert nicht.

- [ ] **Step 3: Admin umbauen**

In `frontend/src/pages/Admin.tsx`:

1. Die lokale `H`-Komponente entfernen und `SectionTitle` importieren; `SectionTitle` überall statt `<H>` verwenden. Imports ergänzen:

```tsx
import SectionTitle from '../components/ui/SectionTitle'
import Select from '../components/ui/Select'
```

(`Card`-Import kann bleiben; wir nutzen Cards nun flacher bzw. ersetzen sie durch Sektions-Container — siehe unten.)

2. Die `Admin`-Wurzel um die neue Sektion ergänzen:

```tsx
export default function Admin() {
  return (
    <div className="space-y-8">
      <Kategorien />
      <StravaMapping />
      <Jahr />
      <NeuerUser />
    </div>
  )
}
```

3. In `Kategorien`: den `<Card>`-Wrapper durch ein flaches `<section>` ersetzen, `<H>` → `<SectionTitle>`, und **den gesamten `Strava-Sportarten`-Block (`<div className="w-full">…</div>`) aus jeder Kategoriezeile entfernen**. Die Kategoriezeile wird flach (kein eigener Rahmen je Zeile, Trennung per `border-b`):

```tsx
  return (
    <section>
      <SectionTitle>Kategorien &amp; Faktoren</SectionTitle>
      <div>
        {categories.map((c) => (
          <div
            key={c.id}
            className={`flex flex-wrap items-center gap-3 border-b border-line/30 py-2 ${
              c.is_active ? '' : 'opacity-40'
            }`}
          >
            <Icon name={c.icon} size={20} className="text-accent" />
            <span className="min-w-24 flex-1 text-sm font-bold text-ink">{c.name}</span>
            <Input
              label="Faktor"
              type="number"
              step="0.5"
              defaultValue={c.factor}
              className="w-20"
              onBlur={(e) => {
                const factor = parseFloat(e.target.value)
                if (factor > 0 && factor !== c.factor) patch.mutate({ id: c.id, factor })
              }}
            />
            <Input
              label="Standard-km"
              type="number"
              step="1"
              min="1"
              defaultValue={c.default_km}
              className="w-24"
              onBlur={(e) => {
                const default_km = parseFloat(e.target.value)
                if (default_km > 0 && default_km !== c.default_km)
                  patch.mutate({ id: c.id, default_km })
              }}
            />
            <Button
              variant="ghost"
              onClick={() => patch.mutate({ id: c.id, is_active: !c.is_active })}
            >
              {c.is_active ? 'Deaktivieren' : 'Aktivieren'}
            </Button>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-3 border-t border-dashed border-line pt-3">
        <div className="flex flex-wrap gap-2">
          <Input label="Name" value={neu.name} onChange={(e) => setNeu({ ...neu, name: e.target.value })} />
          <Input
            label="Faktor"
            type="number"
            step="0.5"
            className="w-20"
            value={neu.factor}
            onChange={(e) => setNeu({ ...neu, factor: e.target.value })}
          />
          <Input
            label="Standard-km"
            type="number"
            className="w-24"
            value={neu.default_km}
            onChange={(e) => setNeu({ ...neu, default_km: e.target.value })}
          />
          <label className="flex flex-col gap-1 text-xs font-semibold text-ink-mute">
            Farbe
            <input
              type="color"
              className="h-9 w-12 rounded-xl border border-line bg-surface"
              value={neu.color}
              onChange={(e) => setNeu({ ...neu, color: e.target.value })}
            />
          </label>
        </div>
        <IconPicker auswahl={SPORT_ICONS} value={neu.icon} onChange={(icon) => setNeu({ ...neu, icon })} />
        <Button
          disabled={!neu.name || !(parseFloat(neu.factor) > 0) || !(parseFloat(neu.default_km) > 0)}
          onClick={() => create.mutate()}
        >
          Kategorie anlegen
        </Button>
      </div>
    </section>
  )
```

4. Neue Komponente `StravaMapping` ergänzen (vor `function Jahr()`):

```tsx
function StravaMapping() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const patch = useMutation({
    mutationFn: ({ id, types }: { id: number; types: string[] }) =>
      api.patchCategory(id, { strava_sport_types: types }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['categories'] }),
    onError: (e) => toast(e.message),
  })

  // Aktuelle Zuordnung: Sportart -> Kategorie-id (höchstens eine).
  const aktuelleKat = (sport: string) =>
    categories.find((c) => c.strava_sport_types.includes(sport))?.id ?? 0

  function zuweisen(sport: string, zielId: number) {
    const alt = categories.find((c) => c.strava_sport_types.includes(sport))
    if (alt && alt.id !== zielId) {
      patch.mutate({ id: alt.id, types: alt.strava_sport_types.filter((s) => s !== sport) })
    }
    if (zielId) {
      const ziel = categories.find((c) => c.id === zielId)
      if (ziel && !ziel.strava_sport_types.includes(sport)) {
        patch.mutate({ id: ziel.id, types: [...ziel.strava_sport_types, sport] })
      }
    }
  }

  return (
    <section>
      <SectionTitle>Strava-Zuordnung</SectionTitle>
      <p className="mb-3 text-xs text-ink-mute">
        Jede Strava-Sportart zählt zu höchstens einer Kategorie.
      </p>
      <div>
        {STRAVA_SPORT_TYPES.map((sport) => (
          <div key={sport} className="flex items-center justify-between border-b border-line/30 py-2">
            <span className="font-mono text-sm text-ink">{sport}</span>
            <Select
              label=""
              aria-label={`Zuordnung ${sport}`}
              value={aktuelleKat(sport)}
              onChange={(e) => zuweisen(sport, Number(e.target.value))}
              className="w-44"
            >
              <option value={0}>— ignorieren</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
        ))}
      </div>
    </section>
  )
}
```

5. In `Jahr`: `<Card>` → `<section>`, `<H>` → `<SectionTitle>`, und **den Kartenbild-Block entfernen** (die `<h3>Kartenbild (Aquarell)</h3>`, das `<input type="file">` und die `{season.map_image && …}`-Zeile). `uploadMapImage` wird damit nicht mehr verwendet.

- [ ] **Step 4: Test grün**

Run: `cd frontend && npx vitest run src/pages/Admin.test.tsx`
Expected: PASS.

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc -b`
Expected: kein Fehler. Falls `Select`/`uploadMapImage`-Warnungen wegen ungenutzter Importe: ungenutzte Importe entfernen.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Admin.tsx frontend/src/pages/Admin.test.tsx
git commit -m "feat(admin): strava-zuordnungstabelle, flache sektionen, kartenupload entfernt"
```

---

## Task 9: Admin — Einladungen statt direkter Mitglied-Anlage

**Files:**
- Modify: `frontend/src/pages/Admin.tsx`
- Add dependency: `qrcode.react`

- [ ] **Step 1: QR-Lib installieren**

Run: `cd frontend && npm install qrcode.react`
Expected: `qrcode.react` in `package.json`.

- [ ] **Step 2: `NeuerUser` durch `Einladungen` ersetzen**

In `frontend/src/pages/Admin.tsx` die `NeuerUser`-Funktion **vollständig ersetzen** durch eine `Einladungen`-Komponente und in der `Admin`-Wurzel `<NeuerUser />` → `<Einladungen />`. Imports ergänzen:

```tsx
import { QRCodeSVG } from 'qrcode.react'
import { type Invite } from '../api/client'
```

`AvatarWahl`-Import wird nicht mehr gebraucht (entfernen, falls ungenutzt).

```tsx
function Einladungen() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [displayName, setDisplayName] = useState('')
  const [istAdmin, setIstAdmin] = useState(false)
  const [neu, setNeu] = useState<Invite | null>(null)
  const { data: invites = [] } = useQuery({ queryKey: ['invites'], queryFn: api.listInvites })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['invites'] })

  // Vollständige URL: das Backend liefert ggf. nur einen relativen Pfad,
  // wenn PUBLIC_BASE_URL nicht gesetzt ist.
  const volleUrl = (invite: Invite) =>
    invite.url.startsWith('http') ? invite.url : window.location.origin + invite.url

  const erstellen = useMutation({
    mutationFn: () =>
      api.createInvite({ display_name: displayName || null, is_admin: istAdmin }),
    onSuccess: (invite) => {
      setNeu(invite)
      setDisplayName('')
      setIstAdmin(false)
      refresh()
    },
    onError: (e) => toast(e.message),
  })
  const widerrufen = useMutation({
    mutationFn: (id: number) => api.deleteInvite(id),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })

  return (
    <section>
      <SectionTitle>Mitglied einladen</SectionTitle>
      <div className="flex flex-wrap items-end gap-2">
        <Input
          label="Anzeigename (optional)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <label className="flex items-center gap-2 pb-2 text-xs font-semibold text-ink-mute">
          <input
            type="checkbox"
            checked={istAdmin}
            onChange={(e) => setIstAdmin(e.target.checked)}
          />
          Admin
        </label>
        <Button onClick={() => erstellen.mutate()} disabled={erstellen.isPending}>
          Einladung erstellen
        </Button>
      </div>

      {neu && (
        <div className="mt-4 flex flex-col items-center gap-3 border border-line p-4 sm:flex-row sm:items-start">
          <div className="rounded-lg bg-white p-2">
            <QRCodeSVG value={volleUrl(neu)} size={120} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="mb-1 font-mono text-xs uppercase tracking-wider text-ink-tech">
              Einladungslink
            </p>
            <p className="break-all text-sm text-ink">{volleUrl(neu)}</p>
            <Button
              variant="ghost"
              className="mt-2"
              onClick={() => {
                navigator.clipboard.writeText(volleUrl(neu))
                toast('Link kopiert', 'ok')
              }}
            >
              Link kopieren
            </Button>
          </div>
        </div>
      )}

      {invites.length > 0 && (
        <ul className="mt-4">
          {invites.map((i) => {
            const status = i.used_at
              ? 'genutzt'
              : new Date(i.expires_at) < new Date()
                ? 'abgelaufen'
                : 'offen'
            return (
              <li
                key={i.id}
                className="flex items-center gap-3 border-b border-line/30 py-2 text-sm"
              >
                <span className="flex-1 text-ink">{i.display_name || '—'}</span>
                <span className="font-mono text-xs uppercase tracking-wider text-ink-tech">
                  {status}
                </span>
                <button
                  aria-label="Einladung widerrufen"
                  className="text-ink-mute hover:text-danger"
                  onClick={() => widerrufen.mutate(i.id)}
                >
                  <Icon name="papierkorb" size={16} />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
```

`createUser` im API-Client wird nicht mehr aus der UI verwendet (Methode kann bleiben).

- [ ] **Step 3: Admin-Test um `listInvites`-Mock prüfen**

Der Mock in `Admin.test.tsx` (Task 8) enthält bereits `listInvites: vi.fn().mockResolvedValue([])`. Falls `createInvite`/`deleteInvite` in Tests gebraucht werden, ergänzen. Hier genügt der vorhandene Mock.

Run: `cd frontend && npx vitest run src/pages/Admin.test.tsx`
Expected: PASS.

- [ ] **Step 4: Typecheck + Build**

Run: `cd frontend && npx tsc -b && npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Admin.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(admin): mitglieder per einladungslink + QR statt direkter anlage"
```

---

## Task 10: Öffentliche Einladungs-Seite + Routing (TDD)

**Files:**
- Create: `frontend/src/pages/Einladung.tsx`
- Test: `frontend/src/pages/Einladung.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Failing test**

Create `frontend/src/pages/Einladung.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Einladung from './Einladung'

const getInvite = vi.fn()
vi.mock('../api/client', () => ({
  api: { getInvite: () => getInvite(), acceptInvite: vi.fn() },
}))
vi.mock('../components/ui/Toast', () => ({ useToast: () => vi.fn() }))

function renderAt(token: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/einladung/${token}`]}>
        <Routes>
          <Route path="/einladung/:token" element={<Einladung />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => getInvite.mockReset())

describe('Einladung', () => {
  it('zeigt das Registrierungsformular bei gültigem Token', async () => {
    getInvite.mockResolvedValue({ valid: true, display_name: 'Lisa' })
    renderAt('abc')
    expect(await screen.findByLabelText('Benutzername')).toBeInTheDocument()
  })

  it('zeigt eine Fehlermeldung bei ungültigem Token', async () => {
    getInvite.mockResolvedValue({ valid: false })
    renderAt('weg')
    expect(await screen.findByText(/ungültig|abgelaufen|eingelöst/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Test rot**

Run: `cd frontend && npx vitest run src/pages/Einladung.test.tsx`
Expected: FAIL — `Einladung` existiert nicht.

- [ ] **Step 3: Seite implementieren**

Create `frontend/src/pages/Einladung.tsx`:

```tsx
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import AvatarWahl from '../components/ui/AvatarWahl'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import Input from '../components/ui/Input'

export default function Einladung() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: invite, isLoading } = useQuery({
    queryKey: ['invite', token],
    queryFn: () => api.getInvite(token),
  })

  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [avatar, setAvatar] = useState('icon:laufen')
  const [error, setError] = useState('')

  // Anzeigename aus Einladung vorbelegen, sobald geladen.
  if (invite?.valid && invite.display_name && !displayName) setDisplayName(invite.display_name)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const me = await api.acceptInvite(token, { username, password, display_name: displayName, avatar })
      queryClient.setQueryData(['me'], me)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registrierung fehlgeschlagen')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-xs">
        <Card glow className="space-y-4 p-7">
          <h1 className="flex items-center justify-center gap-1 text-2xl font-black tracking-wide text-ink">
            <Icon name="blitz" size={20} className="text-accent" />
            METER<span className="text-accent [text-shadow:var(--t-glow)]">MACHEN</span>
          </h1>
          {isLoading ? (
            <p className="text-center text-sm text-ink-mute">Lade…</p>
          ) : invite?.valid ? (
            <form onSubmit={submit} className="space-y-4">
              <p className="text-center text-xs text-ink-mute">Willkommen! Leg dein Konto an.</p>
              <Input label="Benutzername" value={username} onChange={(e) => setUsername(e.target.value)} />
              <Input
                label="Anzeigename"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
              <Input
                label="Passwort (min. 4 Zeichen)"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <div>
                <div className="mb-1 text-xs font-semibold text-ink-mute">Avatar</div>
                <AvatarWahl value={avatar} onChange={setAvatar} />
              </div>
              {error && <p className="text-sm text-danger">{error}</p>}
              <Button
                type="submit"
                className="w-full"
                disabled={!username || !displayName || password.length < 4}
              >
                Konto anlegen
              </Button>
            </form>
          ) : (
            <p className="text-center text-sm text-danger">
              Diese Einladung ist ungültig, abgelaufen oder bereits eingelöst.
            </p>
          )}
        </Card>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Test grün**

Run: `cd frontend && npx vitest run src/pages/Einladung.test.tsx`
Expected: PASS.

- [ ] **Step 5: Routing in `App.tsx`**

In `frontend/src/App.tsx`:

```tsx
import { Navigate, Route, Routes } from 'react-router-dom'
import Einladung from './pages/Einladung'
```

Den Logged-out-Fall und den Catch-all anpassen:

```tsx
  if (isLoading) return <p className="p-8 text-ink-mute">Lade…</p>
  if (!me)
    return (
      <Routes>
        <Route path="/einladung/:token" element={<Einladung />} />
        <Route path="*" element={<Login />} />
      </Routes>
    )
  return (
    <Routes>
      <Route element={<Layout me={me} />}>
        <Route path="/" element={<Vergleich />} />
        <Route path="/aktivitaeten" element={<MeineAktivitaeten />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
```

- [ ] **Step 6: Voller Frontend-Check**

Run: `cd frontend && npx tsc -b && npx vitest run && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/Einladung.tsx frontend/src/pages/Einladung.test.tsx frontend/src/App.tsx
git commit -m "feat(invites): öffentliche /einladung/:token registrierung + routing"
```

---

## Task 11: README aktualisieren + Gesamtabnahme

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README anpassen**

Im Abschnitt mit dem Admin-Login bzw. Mitglieder-Hinweis ergänzen, dass neue Mitglieder über einen Einladungslink (Admin → „Mitglied einladen") selbst ein Konto anlegen; der Link ist 7 Tage gültig und einmalig nutzbar. Falls die alte „Kartenbild (Aquarell)"-Funktion irgendwo im README erwähnt ist, entfernen.

- [ ] **Step 2: Gesamte Suiten**

Run: `cd backend && uv run pytest`
Expected: PASS.

Run: `cd frontend && npx tsc -b && npx vitest run && npm run build`
Expected: PASS.

- [ ] **Step 3: Pre-commit/Lint**

Run: `cd frontend && npm run lint`
Expected: keine Fehler (ungenutzte Importe wie `uploadMapImage`, `createUser`, `AvatarWahl` in `Admin.tsx` ggf. entfernen).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: einladungs-flow im README, kartenbild-hinweis entfernt"
```

---

## Self-Review-Ergebnis (gegen die Spec geprüft)

- **Punkt 1 (flacher):** Task 4 (Tokens/SectionTitle) + flache Sektionen in Tasks 7/8. ✓
- **Punkt 2 (Strava-Zeile):** Task 5. ✓
- **Punkt 3 (Reihenfolge + Sport-Mix):** Task 6. ✓
- **Punkt 4 (Hinzufügen cleaner):** bewusst minimal — `SchnellwahlCard` bleibt als hervorgehobene Card; Feinschliff über die HUD-Tokens (Task 4) ohne strukturelle Änderung. Kein eigener Task nötig.
- **Punkt 5 (Aktivitäten-Gruppen):** Task 7. ✓
- **Punkt 6 (Admin-Mapping):** Task 8. ✓
- **Punkt 7 (Einladungen):** Tasks 1–3, 9, 10. ✓
- **Visuelle Richtung (HUD):** Task 4 als Grundlage, in allen Screen-Tasks angewandt. ✓

Offene, bewusst verschobene Punkte (in Spec als optional markiert): Backend-`map_image`/Upload-Endpoint und ggf. ungenutztes `pathMath.ts` bleiben bestehen; reiner Cleanup, kein Funktionsbezug.
```
