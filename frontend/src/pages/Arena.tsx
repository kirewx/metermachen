import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api/client'
import Icon from '../components/ui/Icon'

const VIEWS = [
  { to: '/arena/challenges', label: 'Challenges', icon: 'pokal', addon: 'challenges' },
  { to: '/arena/wetten', label: 'Wetten', icon: 'medaille', addon: 'sidebets' },
]

const pill = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 px-4 py-1 text-sm transition ${
    isActive ? 'font-bold text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute hover:text-ink'
  }`

// Arena: Challenges and Wetten under one tab. The pill row only appears when
// both add-ons are on; the sub-view is part of the URL so links and back work.
export default function Arena() {
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  const active = new Set(addons.filter((a) => a.active).map((a) => a.key))
  const views = VIEWS.filter((v) => active.has(v.addon))
  return (
    <div className="space-y-4">
      {views.length > 1 && (
        <div className="flex flex-wrap items-end gap-2">
          {views.map((v) => (
            <NavLink key={v.to} to={v.to} className={pill}>
              <Icon name={v.icon} size={14} />
              {v.label}
            </NavLink>
          ))}
        </div>
      )}
      <Outlet />
    </div>
  )
}
