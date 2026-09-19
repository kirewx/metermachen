import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PeriodControl from './PeriodControl'

const years = [
  { year: 2025, label: '2025' },
  { year: 2026, label: '2026/27' },
]
const months = ['2026-07', '2026-08', '2026-09']
const today = new Date(2026, 8, 19)

function setup(props: Partial<Parameters<typeof PeriodControl>[0]> = {}) {
  const handlers = { onModeChange: vi.fn(), onYearChange: vi.fn(), onMonthChange: vi.fn() }
  render(
    <PeriodControl
      mode="year"
      showModeToggle
      years={years}
      year={2026}
      months={months}
      month={null}
      today={today}
      {...handlers}
      {...props}
    />,
  )
  return handlers
}

describe('PeriodControl', () => {
  it('switches the mode through the pill', () => {
    const h = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Monat' }))
    expect(h.onModeChange).toHaveBeenCalledWith('month')
  })

  it('steps through seasons in year mode and disables the last end', () => {
    const h = setup()
    expect(screen.getByText('2026/27')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nächste Saison' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Vorherige Saison' }))
    expect(h.onYearChange).toHaveBeenCalledWith(2025)
  })

  it('steps through months in month mode', () => {
    const h = setup({ mode: 'month', month: '2026-08' })
    expect(screen.getByText('Aug 2026')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    expect(h.onMonthChange).toHaveBeenCalledWith('2026-07')
    fireEvent.click(screen.getByRole('button', { name: 'Nächster Monat' }))
    expect(h.onMonthChange).toHaveBeenCalledWith('2026-09')
  })

  it('disables the arrows at the month ends', () => {
    setup({ mode: 'month', month: '2026-07' })
    expect(screen.getByRole('button', { name: 'Vorheriger Monat' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Nächster Monat' })).toBeEnabled()
  })

  it('tags finished months with Endstand, not the running one', () => {
    setup({ mode: 'month', month: '2026-08' })
    expect(screen.getByText('Endstand')).toBeInTheDocument()
  })

  it('shows no Endstand for the current month', () => {
    setup({ mode: 'month', month: '2026-09' })
    expect(screen.queryByText('Endstand')).toBeNull()
  })

  it('hides the pill and shows the season when the toggle is off', () => {
    setup({ mode: 'month', month: '2026-08', showModeToggle: false })
    expect(screen.queryByRole('button', { name: 'Monat' })).toBeNull()
    expect(screen.getByText('2026/27')).toBeInTheDocument()
  })

  it('disables the Monat pill without a month axis', () => {
    setup({ months: [] })
    expect(screen.getByRole('button', { name: 'Monat' })).toBeDisabled()
  })

  it('waits in month mode while the axis loads instead of stepping seasons', () => {
    const h = setup({ mode: 'month', months: [], loading: true })
    expect(screen.getByRole('button', { name: 'Monat' })).toBeEnabled()
    expect(screen.queryByText('2026/27')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Vorherige Saison' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Vorheriger Monat' }))
    expect(screen.getByRole('button', { name: 'Vorheriger Monat' })).toBeDisabled()
    expect(h.onYearChange).not.toHaveBeenCalled()
  })
})
