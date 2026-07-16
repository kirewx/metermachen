export type Tab = {
  to: string
  label: string
  icon: string
  end: boolean
  adminOnly: boolean
  abStart: boolean
  addon?: string
}

export const TABS: Tab[] = [
  { to: '/', label: 'Vergleich', icon: 'fahne', end: true, adminOnly: false, abStart: false },
  { to: '/aktivitaeten', label: 'Aktivitäten', icon: 'blitz', end: false, adminOnly: false, abStart: false },
  { to: '/wetten', label: 'Wetten', icon: 'medaille', end: false, adminOnly: false, abStart: false, addon: 'sidebets' },
  { to: '/regeln', label: 'Regeln', icon: 'notiz', end: false, adminOnly: false, abStart: false },
  { to: '/archiv', label: 'Archiv', icon: 'pokal', end: false, adminOnly: false, abStart: true },
  { to: '/admin', label: 'Admin', icon: 'zahnrad', end: false, adminOnly: true, abStart: false },
]

export function sichtbareTabs(
  tabs: Tab[],
  opts: { isAdmin: boolean; gestartet: boolean; aktiveAddons: Set<string> },
): Tab[] {
  return tabs.filter(
    (t) =>
      (!t.adminOnly || opts.isAdmin) &&
      (!t.abStart || opts.gestartet) &&
      (!t.addon || opts.aktiveAddons.has(t.addon)),
  )
}
