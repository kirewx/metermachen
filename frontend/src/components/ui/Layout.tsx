import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api, type Me } from '../../api/client'
import ProfilModal from './ProfilModal'
import Avatar from './Avatar'
import Icon from './Icon'
import { useTheme } from './useTheme'

const TABS = [
  { to: '/', label: 'Vergleich', icon: 'fahne', end: true, adminOnly: false },
  { to: '/aktivitaeten', label: 'Aktivitäten', icon: 'blitz', end: false, adminOnly: false },
  { to: '/admin', label: 'Admin', icon: 'zahnrad', end: false, adminOnly: true },
]

const pill = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition ${
    isActive
      ? 'border border-accent font-bold text-accent shadow-glow'
      : 'text-ink-mute hover:text-ink'
  }`

export default function Layout({ me }: { me: Me }) {
  const queryClient = useQueryClient()
  const { theme, toggle } = useTheme()
  const [profilOffen, setProfilOffen] = useState(false)
  const tabs = TABS.filter((t) => !t.adminOnly || me.is_admin)

  async function logout() {
    await api.logout()
    queryClient.setQueryData(['me'], null)
  }

  return (
    <div className="min-h-screen pb-20 sm:pb-0">
      <nav className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-card/80 px-4 py-2 backdrop-blur">
        <span className="mr-2 flex items-center gap-1 font-black tracking-wide text-ink">
          <Icon name="blitz" size={16} className="text-accent" />
          METER<span className="text-accent [text-shadow:var(--t-glow)]">MACHEN</span>
        </span>
        <div className="hidden gap-1 sm:flex">
          {tabs.map((t) => (
            <NavLink key={t.to} to={t.to} end={t.end} className={pill}>
              <Icon name={t.icon} size={14} />
              {t.label}
            </NavLink>
          ))}
        </div>
        <button
          aria-label="Farbmodus wechseln"
          onClick={toggle}
          className="ml-auto text-ink-mute hover:text-accent"
        >
          <Icon name={theme === 'dunkel' ? 'sonne' : 'mond'} size={18} />
        </button>
        <button
          onClick={() => setProfilOffen(true)}
          className="flex items-center gap-2 text-sm text-ink-soft hover:text-ink"
        >
          <Avatar value={me.avatar} size="sm" />
          <span className="hidden sm:inline">{me.display_name}</span>
        </button>
        <button aria-label="Logout" onClick={logout} className="text-ink-mute hover:text-danger">
          <Icon name="logout" size={18} />
        </button>
      </nav>
      <main className="mx-auto max-w-5xl p-4">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-line bg-card/95 py-2 backdrop-blur sm:hidden">
        {tabs.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            end={t.end}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 text-[10px] font-bold ${
                isActive ? 'text-accent [text-shadow:var(--t-glow)]' : 'text-ink-mute'
              }`
            }
          >
            <Icon name={t.icon} size={20} />
            {t.label}
          </NavLink>
        ))}
      </nav>
      <ProfilModal me={me} open={profilOffen} onClose={() => setProfilOffen(false)} />
    </div>
  )
}
