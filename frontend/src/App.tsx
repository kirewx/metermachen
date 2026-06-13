import { useQuery } from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import Layout from './components/ui/Layout'
import Admin from './pages/Admin'
import Login from './pages/Login'
import MeineAktivitaeten from './pages/MeineAktivitaeten'
import Vergleich from './pages/Vergleich'

export default function App() {
  const { data: me, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.me().catch(() => null),
  })
  if (isLoading) return <p className="p-8 text-ink-mute">Lade…</p>
  if (!me) return <Login />
  return (
    <Routes>
      <Route element={<Layout me={me} />}>
        <Route path="/" element={<Vergleich />} />
        <Route path="/aktivitaeten" element={<MeineAktivitaeten />} />
        <Route path="/admin" element={<Admin />} />
      </Route>
    </Routes>
  )
}
