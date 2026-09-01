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
