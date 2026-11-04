import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import PartnerPicker from './PartnerPicker'

const members = [
  { user_id: 2, display_name: 'Anna', avatar: 'icon:laufen' },
  { user_id: 3, display_name: 'Jonas', avatar: 'icon:rad' },
  { user_id: 4, display_name: 'Johanna', avatar: 'icon:rad' },
]

function Wrapper({ onChange, start = [] }: { onChange: (ids: number[]) => void; start?: number[] }) {
  const [value, setValue] = useState(start)
  return (
    <PartnerPicker
      value={value}
      members={members}
      onChange={(ids) => {
        setValue(ids)
        onChange(ids)
      }}
    />
  )
}

describe('PartnerPicker', () => {
  it('filters by name and adds the picked member', () => {
    const onChange = vi.fn()
    render(<Wrapper onChange={onChange} />)
    const input = screen.getByLabelText('Mit wem? (optional)')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'jo' } })
    expect(screen.queryByRole('button', { name: /Anna/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Johanna/ }))
    expect(onChange).toHaveBeenLastCalledWith([4])
    expect(input).toHaveValue('')
  })

  it('selects the first hit with Enter and hides chosen ones', () => {
    const onChange = vi.fn()
    render(<Wrapper onChange={onChange} start={[2]} />)
    const input = screen.getByLabelText('Mit wem? (optional)')
    fireEvent.focus(input)
    expect(screen.queryByRole('button', { name: /^Anna$/ })).not.toBeInTheDocument()
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(onChange).toHaveBeenLastCalledWith([2, 3])
  })

  it('removes a chip', () => {
    const onChange = vi.fn()
    render(<Wrapper onChange={onChange} start={[2, 3]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Anna entfernen' }))
    expect(onChange).toHaveBeenLastCalledWith([3])
  })
})
