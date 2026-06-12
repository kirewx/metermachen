import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
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
})
