import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { Challenge } from '../../api/client'
import GluecksradDialog from './GluecksradDialog'

const stand = (user_id: number, display_name: string, geschafft: boolean) => ({
  user_id, display_name, avatar: '🦊', value: 0, rank: 1, geschafft, nicht_mehr_schaffbar: false,
})

const einzeln = {
  team_mode: false,
  groups: [],
  standings: [stand(1, 'Rick', true), stand(2, 'Mia', false), stand(3, 'Lea', true)],
} as unknown as Challenge

const team = {
  team_mode: true,
  standings: [],
  groups: [
    { id: 1, name: 'Gruppe A', geschafft: true, members: [stand(1, 'Rick', true), stand(2, 'Mia', false)] },
    { id: 2, name: 'Gruppe B', geschafft: false, members: [stand(3, 'Lea', false)] },
  ],
} as unknown as Challenge

/** Fixed random values: first the slice index, then the spot inside it. */
function folge(...werte: number[]) {
  return () => werte.shift() ?? 0
}

function renderRad(ch: Challenge, zufall: () => number) {
  const onSieger = vi.fn()
  render(
    <GluecksradDialog
      ch={ch} open onClose={() => {}} onSieger={onSieger} speichert={false}
      dauerMs={0} zufall={zufall}
    />,
  )
  return onSieger
}

const box = (name: string) => screen.getByRole('checkbox', { name: new RegExp(name) })

describe('GluecksradDialog', () => {
  it('waehlt wer es geschafft hat vor, laesst aber alle zu', async () => {
    // Mia dazu → Rad: Rick, Mia, Lea; Index 1 = Mia
    const onSieger = renderRad(einzeln, folge(1, 500))
    expect(box('Rick')).toBeChecked()
    expect(box('Mia')).not.toBeChecked()
    expect(box('Lea')).toBeChecked()
    fireEvent.click(box('Mia'))
    fireEvent.click(screen.getByRole('button', { name: 'Drehen' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Mia')
    fireEvent.click(screen.getByRole('button', { name: 'Als Sieger eintragen' }))
    expect(onSieger).toHaveBeenCalledWith({ user_id: 2 })
  })

  it('zieht nur aus der Auswahl', async () => {
    // Rick abgewählt → Rad: Lea allein
    renderRad(einzeln, folge(0, 0))
    fireEvent.click(box('Rick'))
    fireEvent.click(screen.getByRole('button', { name: 'Drehen' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Lea')
  })

  it('sperrt das Drehen ohne Auswahl', () => {
    renderRad(einzeln, folge())
    fireEvent.click(box('Rick'))
    fireEvent.click(box('Lea'))
    expect(screen.getByRole('button', { name: 'Drehen' })).toBeDisabled()
  })

  it('lost bei Gruppen erst die Gruppe, dann die Person aus', async () => {
    // Runde 1: Gruppe B dazu → Index 0 = Gruppe A; Runde 2: Index 1 = Mia
    const onSieger = renderRad(team, folge(0, 0, 1, 0))
    expect(box('Gruppe A')).toBeChecked()
    expect(box('Gruppe B')).not.toBeChecked()
    fireEvent.click(box('Gruppe B'))
    fireEvent.click(screen.getByRole('button', { name: 'Drehen' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Gruppe A')

    fireEvent.click(screen.getByRole('button', { name: 'Weiter: Person auslosen' }))
    expect(screen.getByText('Runde 2: Wer aus Gruppe A gewinnt?')).toBeInTheDocument()
    expect(box('Rick')).toBeChecked()
    expect(box('Mia')).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Drehen' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Mia')
    fireEvent.click(screen.getByRole('button', { name: 'Als Sieger eintragen' }))
    expect(onSieger).toHaveBeenCalledWith({ user_id: 2 })
  })

  it('kann auch die ganze Gruppe als Sieger eintragen', async () => {
    const onSieger = renderRad(team, folge(0, 0))
    fireEvent.click(screen.getByRole('button', { name: 'Drehen' }))
    await screen.findByRole('status')
    fireEvent.click(screen.getByRole('button', { name: 'Gruppe als Sieger eintragen' }))
    expect(onSieger).toHaveBeenCalledWith({ group_id: 1 })
  })
})
