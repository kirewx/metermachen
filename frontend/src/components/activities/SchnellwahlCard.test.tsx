import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Category } from '../../api/client'
import SchnellwahlCard from './SchnellwahlCard'

const categories: Category[] = [
  { id: 1, name: 'Joggen', factor: 4, color: '#e74c3c', icon: 'laufen', default_km: 5, is_active: true },
  { id: 2, name: 'Radfahren', factor: 1, color: '#3498db', icon: 'rad', default_km: 20, is_active: true },
  { id: 3, name: 'Alt', factor: 2, color: '#000000', icon: 'medaille', default_km: 10, is_active: false },
]

const heute = () => new Date().toISOString().slice(0, 10)

describe('SchnellwahlCard', () => {
  beforeEach(() => localStorage.clear())

  it('zeigt nur aktive Kategorien', () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByRole('option', { name: /Joggen/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Alt/ })).not.toBeInTheDocument()
  })

  it('startet beim Standard-km der ersten Kategorie', () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByTestId('km-wert')).toHaveTextContent('5')
  })

  it('Kategoriewechsel setzt auf deren Standard und merkt die Wahl', async () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    await userEvent.selectOptions(screen.getByLabelText('Kategorie'), '2')
    expect(screen.getByTestId('km-wert')).toHaveTextContent('20')
    expect(localStorage.getItem('schnellwahl-kategorie')).toBe('2')
  })

  it('plus/minus in 1-km-Schritten, nicht unter 1', async () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    expect(screen.getByTestId('km-wert')).toHaveTextContent('6')
    for (let i = 0; i < 7; i++) {
      await userEvent.click(screen.getByRole('button', { name: '1 km weniger' }))
    }
    expect(screen.getByTestId('km-wert')).toHaveTextContent('1')
  })

  it('zeigt die gewertete Distanz', () => {
    render(<SchnellwahlCard categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByText(/= 20\.0 km gewertet/)).toBeInTheDocument()
  })

  it('Submit ohne Details nutzt heute als Datum', async () => {
    const onSubmit = vi.fn()
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: heute(),
      distance_km: 5,
      duration_min: null,
      note: null,
    })
  })

  it('Details: Datum, Dauer, Notiz und freie km werden übernommen', async () => {
    const onSubmit = vi.fn()
    render(<SchnellwahlCard categories={categories} onSubmit={onSubmit} />)
    await userEvent.click(screen.getByRole('button', { name: 'Details' }))
    const datum = screen.getByLabelText('Datum')
    await userEvent.clear(datum)
    await userEvent.type(datum, '2026-03-01')
    await userEvent.type(screen.getByLabelText('Dauer (min)'), '42')
    await userEvent.type(screen.getByLabelText('Notiz'), 'Runde am Fluss')
    const frei = screen.getByLabelText('km (frei)')
    await userEvent.clear(frei)
    await userEvent.type(frei, '7.5')
    await userEvent.click(screen.getByRole('button', { name: /Eintragen/ }))
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: '2026-03-01',
      distance_km: 7.5,
      duration_min: 42,
      note: 'Runde am Fluss',
    })
  })

  it('füllt beim Bearbeiten die Eintragswerte vor', () => {
    render(
      <SchnellwahlCard
        categories={categories}
        initial={{
          id: 9, category_id: 2, date: '2026-02-02', distance_km: 33,
          duration_min: 90, note: 'Tour', scaled_km: 33, edited: false,
        }}
        onSubmit={vi.fn()}
      />,
    )
    expect(screen.getByTestId('km-wert')).toHaveTextContent('33')
    expect(screen.getByLabelText('Datum')).toHaveValue('2026-02-02')
    expect(screen.getByLabelText('Notiz')).toHaveValue('Tour')
  })
})
