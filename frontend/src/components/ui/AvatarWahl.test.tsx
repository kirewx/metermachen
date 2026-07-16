import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import AvatarWahl from './AvatarWahl'

describe('AvatarWahl', () => {
  it('liefert Emojis direkt', async () => {
    const onChange = vi.fn()
    render(<AvatarWahl value="🦊" onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: '🐸' }))
    expect(onChange).toHaveBeenCalledWith('🐸')
  })

  it('liefert Piktogramme mit icon:-Präfix', async () => {
    const onChange = vi.fn()
    render(<AvatarWahl value="🦊" onChange={onChange} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Piktogramme' }))
    await userEvent.click(screen.getByRole('button', { name: 'berg' }))
    expect(onChange).toHaveBeenCalledWith('icon:berg')
  })

  it('zeigt Reiter Erspielt nur mit erspielten Emojis und wählt daraus', async () => {
    const onChange = vi.fn()
    render(<AvatarWahl value="🦊" onChange={onChange} erspielt={['👑']} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Erspielt' }))
    await userEvent.click(screen.getByRole('button', { name: '👑' }))
    expect(onChange).toHaveBeenCalledWith('👑')
  })

  it('versteckt Reiter Erspielt ohne erspielte Emojis', () => {
    render(<AvatarWahl value="🦊" onChange={vi.fn()} />)
    expect(screen.queryByRole('tab', { name: 'Erspielt' })).not.toBeInTheDocument()
  })
})
