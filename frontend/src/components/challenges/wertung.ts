import type { Challenge, ChallengeGroup } from '../../api/client'

export type KategorieName = { id: number; name: string }

export function einheit(metric: Challenge['metric']): string {
  if (metric === 'streak') return 'Tage'
  if (metric === 'anzahl') return 'Aktivitäten'
  return 'MM'
}

function kategorienText(ch: Challenge, kategorien: KategorieName[]): string {
  if (ch.category_ids.length === 0) return 'allen Sportarten'
  const namen = ch.category_ids
    .map((id) => kategorien.find((k) => k.id === id)?.name)
    .filter((n): n is string => !!n)
  return namen.length > 0 ? namen.join(' und ') : 'ausgewählten Sportarten'
}

/** Menschenlesbare Beschreibung der Wertung, z.B. "Ziel: 300 MM aus allen Sportarten". */
export function wertungText(ch: Challenge, kategorien: KategorieName[]): string {
  const aus = `aus ${kategorienText(ch, kategorien)}`
  // A streak counts days in a row, so it is never divided by the group size.
  const proKopf = ch.team_mode && ch.metric !== 'streak' ? ' pro Kopf' : ''
  const gruppen =
    ch.team_mode && typeof ch.group_count === 'number' ? ` · ${ch.group_count} Gruppen` : ''
  if (ch.mode === 'rangliste') {
    const was =
      ch.metric === 'streak'
        ? 'längste Serie'
        : ch.metric === 'anzahl'
          ? 'meiste Aktivitäten'
          : 'meiste MM'
    return `Rangliste: ${was}${proKopf} ${aus}, Top ${ch.top_n}${gruppen}`
  }
  if (ch.metric === 'streak') {
    return `Ziel: ${ch.target} Tage am Stück mit mindestens ${ch.streak_min_mm} MM ${aus}${gruppen}`
  }
  return `Ziel: ${ch.target} ${einheit(ch.metric)}${proKopf} ${aus}${gruppen}`
}

/** The group the current user is in, or null (not a group challenge, not drawn, not placed). */
export function meineGruppe(ch: Challenge): ChallengeGroup | null {
  if (!ch.team_mode || ch.meine_gruppe_id === null || ch.meine_gruppe_id === undefined) return null
  return ch.groups.find((g) => g.id === ch.meine_gruppe_id) ?? null
}

/** The group a person belongs to, by the members list. */
export function gruppeVon(ch: Challenge, userId: number): ChallengeGroup | undefined {
  return ch.groups.find((g) => g.members.some((m) => m.user_id === userId))
}

/** "Gruppe A", "Mia (Gruppe A)" or "Mia"; null while no winner is entered. */
export function siegerText(ch: Challenge): string | null {
  if (ch.sieger_group_id != null) {
    return ch.groups.find((g) => g.id === ch.sieger_group_id)?.name ?? 'unbekannt'
  }
  if (ch.sieger_id == null) return null
  const name = ch.standings.find((s) => s.user_id === ch.sieger_id)?.display_name ?? 'unbekannt'
  const gruppe = ch.team_mode ? gruppeVon(ch, ch.sieger_id) : undefined
  return gruppe ? `${name} (${gruppe.name})` : name
}

/** 0..1 für den Fortschrittsbalken. Ranglisten haben keine Schwelle → 0. */
export function fortschritt(ch: Challenge, wert: number): number {
  if (ch.mode !== 'ziel' || !ch.target) return 0
  return Math.min(wert / ch.target, 1)
}
