import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import AuszeichnungsBadges from './AuszeichnungsBadges'

const liste = [{ emoji: '🎩', title: 'Hattrick', description: 'Drei Aktivitäten an einem Tag.' }]

it('zeigt Popover mit Titel und Beschreibung beim Klick', () => {
  render(<AuszeichnungsBadges liste={liste} />)
  expect(screen.queryByText('Hattrick')).toBeNull()
  fireEvent.click(screen.getByText('🎩'))
  expect(screen.getByText('Hattrick')).toBeInTheDocument()
  expect(screen.getByText('Drei Aktivitäten an einem Tag.')).toBeInTheDocument()
  fireEvent.click(screen.getByText('🎩'))
  expect(screen.queryByText('Hattrick')).toBeNull()
})
