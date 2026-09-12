import { describe, expect, it } from 'vitest'
import type { Challenge, ChallengeStanding } from '../../api/client'
import { einheit, fortschritt, gruppeVon, meineGruppe, siegerText, wertungText } from './wertung'

const basis: Challenge = {
  id: 1, title: 'T', description: '', prize: null, creator_id: 1,
  mode: 'ziel', target: 300, top_n: 1, metric: 'mm', category_ids: [],
  streak_min_mm: 5, join_mode: 'auto',
  period_start: '2026-08-04', period_end: '2026-08-31',
  status: 'laufend', vorlaeufig: false, bin_dabei: true, kann_beitreten: false,
  standings: [], mein_stand: null, gewinner_ids: [],
  sieger_id: null, kann_sieger_setzen: false,
  created_at: '2026-08-01T10:00:00Z', resolved_at: null,
}

describe('wertung', () => {
  it('benennt die Einheit je Metrik', () => {
    expect(einheit('mm')).toBe('MM')
    expect(einheit('streak')).toBe('Tage')
    expect(einheit('anzahl')).toBe('Aktivitäten')
  })

  it('beschreibt eine Ziel-Challenge im Klartext', () => {
    expect(wertungText(basis, [])).toBe('Ziel: 300 MM aus allen Sportarten')
  })

  it('nennt die gefilterten Kategorien', () => {
    const ch = { ...basis, category_ids: [2] }
    expect(wertungText(ch, [{ id: 2, name: 'Joggen' }])).toBe('Ziel: 300 MM aus Joggen')
  })

  it('beschreibt eine Streak-Challenge mit Tagesminimum', () => {
    const ch: Challenge = { ...basis, metric: 'streak', target: 10, streak_min_mm: 6 }
    expect(wertungText(ch, [])).toBe(
      'Ziel: 10 Tage am Stück mit mindestens 6 MM aus allen Sportarten',
    )
  })

  it('beschreibt eine Rangliste', () => {
    const ch: Challenge = { ...basis, mode: 'rangliste', target: null, top_n: 3 }
    expect(wertungText(ch, [])).toBe('Rangliste: meiste MM aus allen Sportarten, Top 3')
  })

  it('rechnet den Fortschritt und deckelt bei 1', () => {
    expect(fortschritt(basis, 150)).toBeCloseTo(0.5)
    expect(fortschritt(basis, 600)).toBe(1)
    expect(fortschritt({ ...basis, mode: 'rangliste', target: null }, 42)).toBe(0)
  })
})

const teamBase: Challenge = {
  ...basis,
  team_mode: true,
  group_count: 3,
  seeding_days: 30,
  groups_drawn: true,
  groups: [
    { id: 1, name: 'Gruppe A', size: 2, sum: 400, value: 200, rank: 2, geschafft: false, members: [] },
    { id: 2, name: 'Gruppe B', size: 2, sum: 620, value: 310, rank: 1, geschafft: true, members: [] },
  ],
  unassigned: [],
  meine_gruppe_id: 2,
  sieger_group_id: null,
  kann_gruppen_bearbeiten: false,
}

describe('wertungText for group challenges', () => {
  it('names the per-head target and the group count', () => {
    expect(wertungText({ ...teamBase, mode: 'ziel', target: 300, metric: 'mm' }, [])).toBe(
      'Ziel: 300 MM pro Kopf aus allen Sportarten · 3 Gruppen',
    )
  })
  it('describes the ranking per head', () => {
    expect(wertungText({ ...teamBase, mode: 'rangliste', top_n: 1, metric: 'anzahl' }, [])).toBe(
      'Rangliste: meiste Aktivitäten pro Kopf aus allen Sportarten, Top 1 · 3 Gruppen',
    )
  })
  it('names the group count on a streak target too', () => {
    expect(wertungText({ ...teamBase, metric: 'streak', target: 10, streak_min_mm: 6 }, [])).toBe(
      'Ziel: 10 Tage am Stück mit mindestens 6 MM aus allen Sportarten · 3 Gruppen',
    )
  })
  it('leaves the group count out while it is unknown', () => {
    expect(wertungText({ ...teamBase, group_count: null }, [])).toBe(
      'Ziel: 300 MM pro Kopf aus allen Sportarten',
    )
  })
})

describe('meineGruppe', () => {
  it('returns the own group or null', () => {
    expect(meineGruppe(teamBase)?.name).toBe('Gruppe B')
    expect(meineGruppe({ ...teamBase, meine_gruppe_id: null })).toBeNull()
    expect(meineGruppe({ ...teamBase, meine_gruppe_id: 99 })).toBeNull()
    expect(meineGruppe(basis)).toBeNull()
  })
})

function mitglied(user_id: number, display_name: string): ChallengeStanding {
  return {
    user_id, display_name, avatar: '🦊', value: 100, rank: user_id,
    geschafft: false, nicht_mehr_schaffbar: false,
  }
}

const teamMitMitgliedern: Challenge = {
  ...teamBase,
  standings: [mitglied(1, 'Rick'), mitglied(2, 'Mia')],
  groups: [
    { ...teamBase.groups[0], members: [mitglied(1, 'Rick')] },
    { ...teamBase.groups[1], members: [mitglied(2, 'Mia')] },
  ],
}

describe('gruppeVon', () => {
  it('finds the group by its members, else null', () => {
    expect(gruppeVon(teamMitMitgliedern, 1)?.name).toBe('Gruppe A')
    expect(gruppeVon(teamMitMitgliedern, 2)?.name).toBe('Gruppe B')
    expect(gruppeVon(teamMitMitgliedern, 99)).toBeNull()
  })
})

describe('siegerText', () => {
  it('is null while nobody is entered', () => {
    expect(siegerText(teamMitMitgliedern)).toBeNull()
    expect(siegerText(basis)).toBeNull()
  })

  it('names the winning group', () => {
    expect(siegerText({ ...teamMitMitgliedern, sieger_group_id: 1 })).toBe('Gruppe A')
  })

  it('names a winning person together with their group', () => {
    expect(siegerText({ ...teamMitMitgliedern, sieger_id: 2 })).toBe('Mia (Gruppe B)')
  })

  it('names a winner without a group plainly', () => {
    expect(siegerText({ ...basis, standings: [mitglied(1, 'Rick')], sieger_id: 1 })).toBe('Rick')
  })

  it('falls back to the group member when the standings do not list them', () => {
    expect(siegerText({ ...teamMitMitgliedern, standings: [], sieger_id: 2 })).toBe(
      'Mia (Gruppe B)',
    )
  })

  it('says unbekannt for an id nobody carries', () => {
    expect(siegerText({ ...teamMitMitgliedern, sieger_group_id: 99 })).toBe('unbekannt')
    expect(siegerText({ ...teamMitMitgliedern, sieger_id: 99 })).toBe('unbekannt')
  })
})
