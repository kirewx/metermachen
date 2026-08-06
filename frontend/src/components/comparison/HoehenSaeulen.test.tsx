import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ComparisonUser } from '../../api/client'
import HoehenSaeulen from './HoehenSaeulen'

const MONATE = ['2026-07', '2026-08', '2026-09']

function user(
  id: number,
  name: string,
  monate: { month: string; meters: number }[],
): ComparisonUser {
  return {
    user_id: id,
    display_name: name,
    avatar: 'icon:laufen',
    rank: id,
    total_scaled_km: 0,
    total_real_km: 0,
    total_elevation_m: monate.reduce((s, m) => s + m.meters, 0),
    km_factor: 1,
    by_category: [],
    segments: [],
    cumulative: [],
    elevation_by_month: monate,
  }
}

const erik = user(1, 'Erik', [
  { month: '2026-07', meters: 500 },
  { month: '2026-09', meters: 450 },
])
const lisa = user(2, 'Lisa', [{ month: '2026-07', meters: 2000 }])
const tom = user(3, 'Tom', [])

function renderSaeulen(users: ComparisonUser[], meId: number | null = 1, onSelect = vi.fn()) {
  render(
    <HoehenSaeulen users={users} months={MONATE} meId={meId} onSelect={onSelect} />,
  )
  return onSelect
}

describe('HoehenSaeulen', () => {
  it('sortiert absteigend nach Höhenmetern', () => {
    renderSaeulen([erik, lisa, tom])
    const namen = screen
      .getAllByRole('button')
      .map((b) => b.getAttribute('aria-label'))
    expect(namen).toEqual(['Details zu Lisa', 'Details zu Erik', 'Details zu Tom'])
  })

  it('öffnet über eine Säule die Detailansicht', () => {
    const onSelect = renderSaeulen([erik, lisa])
    fireEvent.click(screen.getByLabelText('Details zu Erik'))
    expect(onSelect).toHaveBeenCalledWith(erik)
  })

  it('zeigt bei wenigen Personen Namen und Zahlen', () => {
    renderSaeulen([erik, lisa])
    expect(screen.getByText('Erik')).toBeInTheDocument()
    expect(screen.getByText('2.000')).toBeInTheDocument()
    expect(screen.getByText('950')).toBeInTheDocument()
  })

  it('ersetzt bei vielen Personen die Namen durch die eigene Platzierung', () => {
    const viele = Array.from({ length: 12 }, (_, i) =>
      user(i + 1, `P${i + 1}`, [{ month: '2026-07', meters: (i + 1) * 100 }]),
    )
    renderSaeulen(viele, 1)
    expect(screen.queryByText('P1')).not.toBeInTheDocument()
    // P1 hat die wenigsten Höhenmeter und landet damit auf dem letzten Platz
    expect(screen.getByText(/Platz 12 von 12/)).toBeInTheDocument()
  })

  it('blendet nur Bergreferenzen unterhalb des Höchstwerts ein', () => {
    renderSaeulen([erik, lisa]) // Höchstwert 2.000
    expect(screen.getByText('Brocken 1.141')).toBeInTheDocument()
    expect(screen.queryByText('Zugspitze 2.962')).not.toBeInTheDocument()
  })

  it('zeigt in der Legende nur Monate mit Daten', () => {
    renderSaeulen([erik, lisa])
    expect(screen.getByText('Jul 26')).toBeInTheDocument()
    expect(screen.getByText('Sep 26')).toBeInTheDocument()
    expect(screen.queryByText('Aug 26')).not.toBeInTheDocument()
  })

  it('lässt Personen ohne Höhenmeter im Feld stehen', () => {
    renderSaeulen([erik, tom])
    expect(screen.getByLabelText('Details zu Tom')).toBeInTheDocument()
  })
})
