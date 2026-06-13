import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Avatar from './Avatar'
import Icon from './Icon'

describe('Icon', () => {
  it('referenziert das Sprite-Symbol', () => {
    const { container } = render(<Icon name="rad" />)
    expect(container.querySelector('use')?.getAttribute('href')).toBe('/icons.svg#rad')
  })
})

describe('Avatar', () => {
  it('rendert Emojis als Text', () => {
    render(<Avatar value="🦊" />)
    expect(screen.getByText('🦊')).toBeInTheDocument()
  })

  it('rendert icon:-Werte als Piktogramm', () => {
    const { container } = render(<Avatar value="icon:berg" />)
    expect(container.querySelector('use')?.getAttribute('href')).toBe('/icons.svg#berg')
  })
})
