import { describe, expect, it } from 'vitest'
import { sichtbareTabs, TABS as ECHTE_TABS, type Tab } from './tabs'

const TABS: Tab[] = [
  { to: '/', label: 'Vergleich', icon: 'fahne', end: true, adminOnly: false, abStart: false },
  // synthetischer abStart-Tab (der echte Archiv-Tab wurde entfernt, Spec 2026-07-25 A1)
  { to: '/spaeter', label: 'Später', icon: 'pokal', end: false, adminOnly: false, abStart: true },
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
    expect(l).not.toContain('Später')
  })

  it('zeigt abStart-Tab ab Challenge-Start', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set() })
    expect(l).toContain('Später')
  })

  it('versteckt Add-on-Tab, wenn das Add-on nicht aktiv ist', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set() })
    expect(l).not.toContain('Wetten')
  })

  it('zeigt Add-on-Tab, wenn das Add-on aktiv ist', () => {
    const l = labels({ isAdmin: false, gestartet: true, aktiveAddons: new Set(['sidebets']) })
    expect(l).toContain('Wetten')
  })

  it('zeigt den Feed-Tab nur ab Challenge-Start', () => {
    const vorher = sichtbareTabs(ECHTE_TABS, {
      isAdmin: false,
      gestartet: false,
      aktiveAddons: new Set(),
    }).map((t) => t.to)
    expect(vorher).not.toContain('/feed')
    const nachher = sichtbareTabs(ECHTE_TABS, {
      isAdmin: false,
      gestartet: true,
      aktiveAddons: new Set(),
    }).map((t) => t.to)
    expect(nachher).toContain('/feed')
  })

  it('zeigt den Challenges-Tab nur bei aktivem Add-on', () => {
    const ohne = sichtbareTabs(ECHTE_TABS, {
      isAdmin: false, gestartet: true, aktiveAddons: new Set<string>(),
    })
    expect(ohne.find((t) => t.to === '/challenges')).toBeUndefined()
    const mit = sichtbareTabs(ECHTE_TABS, {
      isAdmin: false, gestartet: true, aktiveAddons: new Set(['challenges']),
    })
    expect(mit.find((t) => t.to === '/challenges')?.label).toBe('Challenges')
  })
})
