import { useQuery, type QueryClient } from '@tanstack/react-query'
import { api, type TogetherInfo } from '../../api/client'

/** True, wenn das Add-on `together` gerade aktiv ist. */
export function useTogetherAktiv(): boolean {
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  return addons.some((a) => a.key === 'together' && a.active)
}

/** Nach Bestätigen/Ablehnen: alles neu laden, was Together-Daten zeigt. */
export function invalidateTogether(qc: QueryClient) {
  for (const key of [
    'together-suggestions',
    'activities',
    'user-activities',
    'together-partners',
    'feed',
    'achievements',
  ]) {
    qc.invalidateQueries({ queryKey: [key] })
  }
}

/** Badge-Daten, die etwas zu zeigen haben (fremde Profile: nur mit Partnern). */
export function hatBadge(together: TogetherInfo | null | undefined, own: boolean): boolean {
  return !!together && together.partners.length + (own ? (together.pending?.length ?? 0) : 0) > 0
}

/** 8.24 → "8,2" */
export function km(value: number): string {
  return value.toLocaleString('de-DE', { maximumFractionDigits: 1 })
}

/** '2026-11-03' → "Mo., 03.11." */
export function tagKurz(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('de-DE', {
    weekday: 'short',
    day: '2-digit',
    month: '2-digit',
  })
}
