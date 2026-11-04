import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PartnerCard from './PartnerCard'

const togetherPartners = vi.fn()
vi.mock('../../api/client', () => ({
  api: {
    addons: vi.fn().mockResolvedValue([{ key: 'together', active: true }]),
    togetherPartners: (id: number) => togetherPartners(id),
  },
}))

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <PartnerCard userId={1} />
    </QueryClientProvider>,
  )
}

beforeEach(() => togetherPartners.mockReset())

describe('PartnerCard', () => {
  it('highlights the most frequent partner and lists all', async () => {
    togetherPartners.mockResolvedValue([
      { user_id: 2, display_name: 'Anna', avatar: 'icon:laufen', sessions: 7, km_together: 54 },
      { user_id: 3, display_name: 'Tom', avatar: 'icon:rad', sessions: 4, km_together: 38.25 },
    ])
    renderCard()
    expect(await screen.findByText('Häufigster Partner')).toBeInTheDocument()
    expect(screen.getByText('7×', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText(/38,3 km/)).toBeInTheDocument()
    expect(togetherPartners).toHaveBeenCalledWith(1)
  })

  it('renders nothing without partners', async () => {
    togetherPartners.mockResolvedValue([])
    const { container } = renderCard()
    await waitFor(() => expect(togetherPartners).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
