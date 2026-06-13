import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Stepper from './Stepper'

describe('Stepper', () => {
  it('erhöht und verringert um step', async () => {
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    expect(onChange).toHaveBeenCalledWith(11)
    await userEvent.click(screen.getByRole('button', { name: '1 km weniger' }))
    expect(onChange).toHaveBeenCalledWith(9)
  })

  it('geht nicht unter das Minimum', async () => {
    const onChange = vi.fn()
    render(<Stepper value={1} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '1 km weniger' }))
    expect(onChange).toHaveBeenCalledWith(1)
  })

  afterEach(() => vi.useRealTimers())

  it('gedrückt halten wiederholt nach kurzer Verzögerung', () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    const plus = screen.getByRole('button', { name: '1 km mehr' })
    fireEvent.pointerDown(plus)
    expect(onChange).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(400 + 3 * 120)
    expect(onChange).toHaveBeenCalledTimes(4)
    fireEvent.pointerUp(plus)
    vi.advanceTimersByTime(500)
    expect(onChange).toHaveBeenCalledTimes(4)
  })

  it('zweiter pointerdown stoppt den laufenden Hold (kein Timer-Leak)', () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    fireEvent.pointerDown(screen.getByRole('button', { name: '1 km mehr' }))
    fireEvent.pointerDown(screen.getByRole('button', { name: '1 km weniger' }))
    expect(onChange).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(400 + 2 * 120)
    // nur der zweite Hold tickt weiter: 2 Sofort-Schritte + 2 Wiederholungen
    expect(onChange).toHaveBeenCalledTimes(4)
    expect(onChange).toHaveBeenLastCalledWith(9)
    fireEvent.pointerUp(screen.getByRole('button', { name: '1 km weniger' }))
    vi.advanceTimersByTime(500)
    expect(onChange).toHaveBeenCalledTimes(4)
  })

  it('reagiert auf Tastatur-Klicks (click mit detail 0)', () => {
    const onChange = vi.fn()
    render(<Stepper value={10} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: '1 km mehr' }))
    expect(onChange).toHaveBeenCalledWith(11)
  })
})
