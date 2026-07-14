import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import Layout from './components/ui/Layout'
import Admin from './pages/Admin'
import Archiv from './pages/Archiv'
import Datenschutz from './pages/Datenschutz'
import Einladung from './pages/Einladung'
import Login from './pages/Login'
import MeineAktivitaeten from './pages/MeineAktivitaeten'
import Vergleich from './pages/Vergleich'
import Wetten from './pages/Wetten'

export default function App() {
  const { data: me, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.me().catch(() => null),
  })
  const { data: addons } = useQuery({
    queryKey: ['addons'],
    queryFn: () => api.addons().catch(() => []),
    enabled: !!me,
  })
  const sidebetsAktiv = (addons ?? []).some((a) => a.key === 'sidebets' && a.active)
  if (isLoading) return <p className="p-8 text-ink-mute">Lade…</p>
  if (!me)
    return (
      <Routes>
        <Route path="/einladung/:token" element={<Einladung />} />
        <Route path="/datenschutz" element={<Datenschutz />} />
        <Route path="*" element={<Login />} />
      </Routes>
    )
  return (
    <Routes>
      <Route element={<Layout me={me} />}>
        <Route path="/" element={<Vergleich />} />
        <Route path="/aktivitaeten" element={<MeineAktivitaeten />} />
        <Route path="/archiv" element={<Archiv />} />
        {sidebetsAktiv && <Route path="/wetten" element={<Wetten />} />}
        <Route path="/admin" element={<Admin />} />
        <Route path="/datenschutz" element={<Datenschutz />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
