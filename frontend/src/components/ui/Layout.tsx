import { useQueryClient } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'
import { api, type Me } from '../../api/client'

const link = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-1 ${isActive ? 'bg-emerald-600 text-white' : 'hover:bg-emerald-100'}`

export default function Layout({ me }: { me: Me }) {
  const queryClient = useQueryClient()
  async function logout() {
    await api.logout()
    queryClient.setQueryData(['me'], null)
  }
  return (
    <div className="min-h-screen bg-emerald-50">
      <nav className="flex items-center gap-2 bg-white px-4 py-2 shadow">
        <span className="mr-2 font-bold">MeterMachen</span>
        <NavLink to="/" end className={link}>Vergleich</NavLink>
        <NavLink to="/aktivitaeten" className={link}>Meine Aktivitäten</NavLink>
        {me.is_admin && <NavLink to="/admin" className={link}>Admin</NavLink>}
        <span className="ml-auto text-sm">{me.avatar_emoji} {me.display_name}</span>
        <button onClick={logout} className="text-sm text-gray-500 hover:underline">
          Logout
        </button>
      </nav>
      <main className="mx-auto max-w-5xl p-4">
        <Outlet />
      </main>
    </div>
  )
}
