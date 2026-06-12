import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Category } from '../../api/client'
import ActivityForm from './ActivityForm'

const categories: Category[] = [
  { id: 1, name: 'Joggen', factor: 4, color: '#e74c3c', icon_emoji: '🏃', is_active: true },
  { id: 2, name: 'Alt', factor: 2, color: '#000000', icon_emoji: '🦖', is_active: false },
]

describe('ActivityForm', () => {
  it('zeigt nur aktive Kategorien an', () => {
    render(<ActivityForm categories={categories} onSubmit={vi.fn()} />)
    expect(screen.getByRole('option', { name: /Joggen/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Alt/ })).not.toBeInTheDocument()
  })

  it('liefert die Eingaben beim Absenden', async () => {
    const onSubmit = vi.fn()
    render(<ActivityForm categories={categories} onSubmit={onSubmit} />)
    await userEvent.type(screen.getByLabelText('Datum'), '2026-03-01')
    await userEvent.type(screen.getByLabelText('Distanz (km)'), '5.5')
    await userEvent.type(screen.getByLabelText('Notiz'), 'Runde am Fluss')
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(onSubmit).toHaveBeenCalledWith({
      category_id: 1,
      date: '2026-03-01',
      distance_km: 5.5,
      duration_min: null,
      note: 'Runde am Fluss',
    })
  })

  it('blockiert Absenden ohne Distanz', async () => {
    const onSubmit = vi.fn()
    render(<ActivityForm categories={categories} onSubmit={onSubmit} />)
    await userEvent.type(screen.getByLabelText('Datum'), '2026-03-01')
    await userEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
