import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ToastProvider, useToast } from './Toast'

function Probe() {
  const toast = useToast()
  return <button onClick={() => toast('Kaputt', 'fehler')}>zeig</button>
}

describe('Toast', () => {
  it('zeigt gemeldete Fehler an', async () => {
    render(
      <ToastProvider>
        <Probe />
      </ToastProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'zeig' }))
    expect(screen.getByText('Kaputt')).toBeInTheDocument()
  })
})
