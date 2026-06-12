import { useQuery } from '@tanstack/react-query'
import { Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import Layout from './components/ui/Layout'
import Login from './pages/Login'
import MeineAktivitaeten from './pages/MeineAktivitaeten'

const Vergleich = () => <p>Vergleich 🚧</p>
const Admin = () => <p>Admin 🚧</p>

export default function App() {
  const { data: me, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.me().catch(() => null),
  })
  if (isLoading) return <p className="p-8">Lade…</p>
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
