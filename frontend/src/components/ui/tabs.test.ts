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
