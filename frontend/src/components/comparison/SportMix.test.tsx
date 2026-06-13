import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Comparison } from '../../api/client'
import SportMix from './SportMix'

const data: Comparison = {
  year: 2026,
  goal_km: 1000,
  milestones: [],
  users: [
    {
      user_id: 1,
      display_name: 'Erik',
      avatar: 'icon:laufen',
      rank: 1,
      total_scaled_km: 300,
      by_category: [
        { category_id: 1, name: 'Laufen', color: '#f00', icon: 'laufen', scaled_km: 200 },
        { category_id: 2, name: 'Radfahren', color: '#00f', icon: 'rad', scaled_km: 100 },
      ],
      segments: [],
      cumulative: [],
    },
  ],
}

describe('SportMix', () => {
  it('zeigt Person, gewertete Gesamtsumme und Kategorie-Legende', () => {
    render(<SportMix data={data} />)
    expect(screen.getByText('Erik')).toBeInTheDocument()
    expect(screen.getByText('300')).toBeInTheDocument()
    expect(screen.getByText('Laufen')).toBeInTheDocument()
    expect(screen.getByText('Radfahren')).toBeInTheDocument()
  })
})
