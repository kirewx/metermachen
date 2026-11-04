import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { TogetherInfo } from '../../api/client'
import { TogetherPanel, TogetherStapel } from './TogetherBadge'
import { hatBadge } from './together'

const togetherConfirm = vi.fn()
const togetherDecline = vi.fn()
vi.mock('../../api/client', () => ({
  api: {
    togetherConfirm: (id: number) => togetherConfirm(id),
    togetherDecline: (id: number) => togetherDecline(id),
  },
}))
vi.mock('../ui/Toast', () => ({ useToast: () => vi.fn() }))

const anna = { user_id: 2, display_name: 'Anna', avatar: 'icon:laufen' }
const tom = { user_id: 3, display_name: 'Tom', avatar: 'icon:rad' }
const info = (over: Partial<TogetherInfo>): TogetherInfo => ({
  session_id: 1,
  participant_id: 10,
  status: 'confirmed',
  partners: [anna],
  pending: [],
  km_together: 8.24,
  ...over,
})

function renderPanel(together: TogetherInfo, own: boolean) {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <TogetherPanel together={together} own={own} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  togetherConfirm.mockReset()
  togetherConfirm.mockResolvedValue(undefined)
  togetherDecline.mockReset()
  togetherDecline.mockResolvedValue(undefined)
})

describe('TogetherStapel', () => {
  it('names partners and pending people and toggles', () => {
    const onToggle = vi.fn()
    render(
      <TogetherStapel together={info({ pending: [tom] })} own offen={false} onToggle={onToggle} />,
    )
    const button = screen.getByRole('button', { name: 'Zusammen mit Anna und Tom' })
    expect(button).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(button)
    expect(onToggle).toHaveBeenCalled()
  })

  it('labels a declined session', () => {
    render(<TogetherStapel together={info({ status: 'declined' })} own offen onToggle={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Nicht dabei: Anna' })).toBeInTheDocument()
  })

  it('hides pending people on foreign profiles', () => {
    expect(hatBadge(info({ partners: [], pending: [tom] }), false)).toBe(false)
    expect(hatBadge(info({ partners: [], pending: [tom] }), true)).toBe(true)
    expect(hatBadge(null, true)).toBe(false)
  })
})

describe('TogetherPanel', () => {
  it('shows km and declines a confirmed session', async () => {
    renderPanel(info({}), true)
    expect(screen.getByText('8,2 km gemeinsam')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Bestätigen' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'War ich nicht dabei' }))
    await waitFor(() => expect(togetherDecline).toHaveBeenCalledWith(10))
  })

  it('confirms a suggestion', async () => {
    renderPanel(info({ status: 'suggested', partners: [], pending: [anna] }), true)
    expect(screen.getByText('offen')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Bestätigen' }))
    await waitFor(() => expect(togetherConfirm).toHaveBeenCalledWith(10))
  })

  it('offers „Doch dabei“ after declining', async () => {
    renderPanel(info({ status: 'declined' }), true)
    expect(screen.queryByRole('button', { name: 'War ich nicht dabei' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Doch dabei' }))
    await waitFor(() => expect(togetherConfirm).toHaveBeenCalledWith(10))
  })

  it('has no actions on foreign profiles', () => {
    renderPanel(info({}), false)
    expect(screen.getByText('Anna')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
