import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { FeedEvent } from '../../api/client'
import FeedItem from './FeedItem'

vi.mock('./ReactionBar', () => ({ default: () => null }))

function ev(over: Partial<FeedEvent>): FeedEvent {
  return {
    id: 1, type: 'challenge_end', user_id: null, display_name: null,
    avatar: null, created_at: '2026-09-01T06:00:00Z', payload: {}, reactions: [],
    ...over,
  } as unknown as FeedEvent
}

// getByText matches an element's own text nodes, so the regex targets the
// sentence fragment in the wrapping <span>; toHaveTextContent then checks the
// whole sentence including the <b> children.
describe('FeedItem group challenge texts', () => {
  it('qualified group', () => {
    render(<FeedItem ev={ev({ type: 'challenge_qualified', payload: { title: 'Teams', group_name: 'Gruppe A' } })} />)
    expect(screen.getByText(/hat das Ziel geknackt/)).toHaveTextContent('Gruppe A hat das Ziel geknackt')
  })
  it('winning groups at the end', () => {
    render(<FeedItem ev={ev({ payload: { title: 'Teams', prize: 'Kuchen', gewinner_namen: ['Rick', 'Mia'], gewinner_gruppen: ['Gruppe A'] } })} />)
    expect(screen.getByText(/ist vorbei/)).toHaveTextContent('Gruppe A gewinnt: Kuchen')
  })
  it('group as prize winner', () => {
    render(<FeedItem ev={ev({ type: 'challenge_sieger', payload: { title: 'Teams', gruppe: 'Gruppe A' } })} />)
    expect(screen.getByText(/gewinnt/)).toHaveTextContent('Gruppe A gewinnt Teams')
  })
  it('person from a group as prize winner', () => {
    render(<FeedItem ev={ev({ type: 'challenge_sieger', display_name: 'Mia', payload: { title: 'Teams', gruppe: 'Gruppe A' } })} />)
    expect(screen.getByText(/gewinnt/)).toHaveTextContent('Mia (Gruppe A) gewinnt Teams')
  })
})
