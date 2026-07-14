import { describe, expect, it } from 'vitest'
import { sichtbareTabs, type Tab } from './tabs'

const TABS: Tab[] = [
  { to: '/', label: 'Vergleich', icon: 'fahne', end: true, adminOnly: false, abStart: false },
  { to: '/archiv', label: 'Archiv', icon: 'pokal', end: false, adminOnly: false, abStart: true },
  { to: '/admin', label: 'Admin', icon: 'zahnrad', end: false, adminOnly: true, abStart: false },
  { to: '/wetten', label: 'Wetten', icon: 'medaille', end: false, adminOnly: false, abStart: false, addon: 'sidebets' },
]

const labels = (opts: Parameters<typeof sichtbareTabs>[1]) =>
  sichtbareTabs(TABS, opts).map((t) => t.label)

describe('sichtbareTabs', () => {
  it('blendet Admin-Tab für Nicht-Admins aus', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set(['sidebets']) })
    expect(l).not.toContain('Admin')
  })

  it('zeigt Admin-Tab für Admins', () => {
    const l = labels({ isAdmin: true, gestartet: true, aktiveAddons: new Set() })
    expect(l).toContain('Admin')
  })

  it('blendet abStart-Tab vor Challenge-Start aus', () => {
    const l = labels({ isAdmin: false, gestartet: false, aktiveAddons: new Set() })
    expect(l).not.toContain('Archiv')
  })

  it('zeigt abStart-Tab ab Challenge-Start', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set() })
    expect(l).toContain('Archiv')
  })

  it('versteckt Add-on-Tab, wenn das Add-on nicht aktiv ist', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set() })
    expect(l).not.toContain('Wetten')
  })

  it('zeigt Add-on-Tab, wenn das Add-on aktiv ist', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set(['sidebets']) })
    expect(l).toContain('Wetten')
  })
})
