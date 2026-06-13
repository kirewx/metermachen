# Fast-Add-Absicherung Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Versehentliches und mehrfaches Anlegen von Aktivitäten verhindern — durch einen Pre-Layer auf der Schnellwahl-Leiste und einen Doppelklick-Schutz auf der Eingabe-Card.

**Architecture:** Reine Frontend-Änderung. (1) `SchnellwahlCard` bekommt einen lokalen `gesperrt`-State, der den „Eintragen"-Button während des Speicherns und kurz danach `disabled` schaltet. (2) `SchnellwahlLeiste` startet in einem sicheren Ruhezustand (nur ein „Eintrag hinzufügen"-Button) und zeigt die Card erst nach Klick; nach erfolgreichem Speichern oder „Abbrechen" klappt sie wieder zu. Der bisherige `offen/zu`-localStorage-Toggle entfällt.

**Tech Stack:** React 19, TypeScript, Vitest + Testing Library, @tanstack/react-query. Arbeitsverzeichnis für alle Kommandos: `frontend/`.

---

## File Structure

- `frontend/src/components/activities/SchnellwahlCard.tsx` — Eingabe-Card; bekommt `gesperrt`-State + `disabled`-Button (betrifft Hero- und Kompakt-Variante).
- `frontend/src/components/activities/SchnellwahlCard.test.tsx` — neuer Test für den Doppelklick-Schutz.
- `frontend/src/components/activities/SchnellwahlLeiste.tsx` — Pre-Layer-Logik; `offen/zu`-Toggle entfällt.
- `frontend/src/components/activities/SchnellwahlLeiste.test.tsx` — komplett neu (alte Toggle-Tests entfallen).

Keine Backend-Änderung. Keine Caller-Anpassung nötig (Props von `SchnellwahlLeiste` und `SchnellwahlCard` bleiben unverändert).

---

## Task 1: Doppelklick-Schutz in SchnellwahlCard

**Files:**
- Modify: `frontend/src/components/activities/SchnellwahlCard.tsx`
- Test: `frontend/src/components/activities/SchnellwahlCard.test.tsx`

- [ ] **Step 1: Failing test für den gesperrten Button schreiben**

In `frontend/src/components/activities/SchnellwahlCard.test.tsx` diesen Test innerhalb des `describe('SchnellwahlCard', ...)`-Blocks (z.B. am Ende, vor der schließenden `})`) ergänzen:

```tsx
  it('sperrt den Eintragen-Button während des Speicherns gegen Doppelklick', async () => {
    let freigeben: () => void = () => {}
    const onSubmit = vi.fn(
      () => new Promise<void>((resolve) => { freigeben = resolve }),
    )
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    const btn = screen.getByRole('button', { name: /Eintragen/ })
    await userEvent.click(btn)
    expect(btn).toBeDisabled()
    await userEvent.click(btn)
    expect(onSubmit).toHaveBeenCalledTimes(1)
    freigeben()
  })
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `npm test -- src/components/activities/SchnellwahlCard.test.tsx`
Expected: FAIL — der Button ist nicht `disabled`, `onSubmit` wird zweimal aufgerufen.

- [ ] **Step 3: `gesperrt`-State implementieren**

In `frontend/src/components/activities/SchnellwahlCard.tsx` nach der Zeile
`const [pulsiert, setPulsiert] = useState(false)` ergänzen:

```tsx
  const [gesperrt, setGesperrt] = useState(false)
```

Die `submit`-Funktion komplett ersetzen durch:

```tsx
  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (gesperrt) return
    if (!categoryId || !Number.isFinite(km) || km <= 0 || !date) return
    setGesperrt(true)
    Promise.resolve(
      onSubmit({
        category_id: categoryId,
        date,
        distance_km: km,
        duration_min: duration ? parseInt(duration, 10) : null,
        note: note || null,
      }),
    )
      .then(() => {
        setPulsiert(true)
        window.setTimeout(() => {
          setPulsiert(false)
          setGesperrt(false)
        }, 700)
        if (!initial) {
          setKmText(String(kategorie?.default_km ?? 10))
          setDetails(false)
          setDate(heute())
          setDuration('')
          setNote('')
        }
      })
      .catch(() => {
        // Fehler-Toast zeigt der Aufrufer; Eingaben bleiben erhalten, Button wieder frei
        setGesperrt(false)
      })
  }
```

Den „Eintragen"-Button um `disabled={gesperrt}` ergänzen:

```tsx
          <Button type="submit" disabled={gesperrt} className={variant === 'hero' ? 'w-full' : ''}>
```

- [ ] **Step 4: Test ausführen, Erfolg bestätigen**

Run: `npm test -- src/components/activities/SchnellwahlCard.test.tsx`
Expected: PASS — alle bestehenden Tests **und** der neue Doppelklick-Test sind grün. (Die Tests „nach Erfolg" und „bei Fehler" müssen unverändert grün bleiben; bei Fehler wird `gesperrt` sofort zurückgesetzt.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/activities/SchnellwahlCard.tsx frontend/src/components/activities/SchnellwahlCard.test.tsx
git commit -m "fix: doppelklick-schutz fuer schnellwahl-eintragen-button"
```

---

## Task 2: Pre-Layer in SchnellwahlLeiste

**Files:**
- Modify: `frontend/src/components/activities/SchnellwahlLeiste.tsx`
- Test: `frontend/src/components/activities/SchnellwahlLeiste.test.tsx` (Inhalt komplett ersetzen)

- [ ] **Step 1: Testdatei komplett neu schreiben**

`frontend/src/components/activities/SchnellwahlLeiste.test.tsx` vollständig durch diesen Inhalt ersetzen (die alten Toggle-Tests entfallen, da das `offen/zu`-Verhalten wegfällt):

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SchnellwahlLeiste from './SchnellwahlLeiste'

vi.mock('../../api/client', () => ({
  api: {
    categories: vi.fn().mockResolvedValue([
      {
        id: 1, name: 'Joggen', factor: 4, color: '#fff',
        icon: 'laufen', default_km: 5, is_active: true,
      },
    ]),
    createActivity: vi.fn().mockResolvedValue({}),
  },
}))

function renderLeiste() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SchnellwahlLeiste />
    </QueryClientProvider>,
  )
}

describe('SchnellwahlLeiste', () => {
  beforeEach(() => localStorage.clear())

  it('startet im sicheren Zustand mit nur einem Hinzufügen-Button', () => {
    renderLeiste()
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
  })

  it('Klick auf Hinzufügen öffnet die Schnellwahl-Karte', async () => {
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    expect(await screen.findByTestId('km-wert')).toBeInTheDocument()
  })

  it('Abbrechen klappt ohne Speichern zurück in den sicheren Zustand', async () => {
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    await screen.findByTestId('km-wert')
    await userEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
  })

  it('nach erfolgreichem Eintragen klappt die Leiste automatisch zurück', async () => {
    renderLeiste()
    await userEvent.click(screen.getByRole('button', { name: /Eintrag hinzufügen/ }))
    await screen.findByTestId('km-wert')
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    await waitFor(() => expect(screen.queryByTestId('km-wert')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Eintrag hinzufügen/ })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Tests ausführen, Fehlschlag bestätigen**

Run: `npm test -- src/components/activities/SchnellwahlLeiste.test.tsx`
Expected: FAIL — es gibt noch keinen „Eintrag hinzufügen"-Button; die Leiste rendert die Card sofort.

- [ ] **Step 3: SchnellwahlLeiste mit Pre-Layer implementieren**

`frontend/src/components/activities/SchnellwahlLeiste.tsx` vollständig durch diesen Inhalt ersetzen:

```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import Icon from '../ui/Icon'
import { useToast } from '../ui/Toast'
import SchnellwahlCard from './SchnellwahlCard'

export default function SchnellwahlLeiste() {
  const [aktiv, setAktiv] = useState(false)
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const save = useMutation({
    mutationFn: api.createActivity,
    onSuccess: () => {
      setAktiv(false)
      queryClient.invalidateQueries({ queryKey: ['activities'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
    onError: (e) => toast(e.message),
  })

  if (!aktiv) {
    return (
      <button
        type="button"
        onClick={() => setAktiv(true)}
        className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute hover:text-accent"
      >
        <Icon name="blitz" size={12} />
        Eintrag hinzufügen
      </button>
    )
  }

  return (
    <div>
      <div className="mb-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
        <Icon name="blitz" size={12} />
        Schnellwahl
      </div>
      {categories.length > 0 && (
        <SchnellwahlCard
          variant="kompakt"
          categories={categories}
          onSubmit={(input) => save.mutateAsync(input)}
          onCancel={() => setAktiv(false)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 4: Tests ausführen, Erfolg bestätigen**

Run: `npm test -- src/components/activities/SchnellwahlLeiste.test.tsx`
Expected: PASS — alle vier Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/activities/SchnellwahlLeiste.tsx frontend/src/components/activities/SchnellwahlLeiste.test.tsx
git commit -m "fix: pre-layer fuer schnellwahl-leiste gegen versehentliches adden"
```

---

## Task 3: Gesamtverifikation (Tests, Lint, Build)

**Files:** keine — nur Verifikation.

- [ ] **Step 1: Komplette Test-Suite ausführen**

Run: `npm test`
Expected: PASS — alle Tests grün, keine Regression.

- [ ] **Step 2: Lint**

Run: `npm run lint`
Expected: keine Fehler. (Häufige Stolperfalle: ungenutzte Imports nach dem Umbau von `SchnellwahlLeiste` — die obige Vorlage importiert nur noch `useMutation`, `useQuery`, `useQueryClient`, `useState`, `api`, `Icon`, `useToast`, `SchnellwahlCard`.)

- [ ] **Step 3: Build (TypeScript + Vite)**

Run: `npm run build`
Expected: erfolgreich, keine Typfehler.

- [ ] **Step 4: Abschluss-Commit (nur falls Lint/Build kleine Korrekturen nötig machten)**

```bash
git add -A
git commit -m "chore: lint/build-fixes fast-add-absicherung"
```

---

## Self-Review-Notiz

- **Spec-Abdeckung:** Pre-Layer nur auf der Leiste (Task 2) ✓; Doppelklick-Schutz auf beiden Card-Varianten via `SchnellwahlCard` (Task 1) ✓; Hero-Card bleibt unverändert direkt nutzbar ✓; `offen/zu`-Toggle entfällt (Task 2) ✓.
- **Konsistenz:** Trigger-Button „Eintrag hinzufügen" vs. Submit-Button „Eintragen" sind per Regex eindeutig unterscheidbar (`/Eintrag hinzufügen/` matcht nicht „Eintragen" und umgekehrt).
- **Kein Backend-Change**, keine API-/Typ-Änderung.
