import { useQuery } from '@tanstack/react-query'
import { Navigate, Route, Routes } from 'react-router-dom'
import { api, isUnauthorized } from './api/client'
import Layout from './components/ui/Layout'
import Admin from './pages/Admin'
import Archiv from './pages/Archiv'
import Datenschutz from './pages/Datenschutz'
import Einladung from './pages/Einladung'
import Login from './pages/Login'
import MeineAktivitaeten from './pages/MeineAktivitaeten'
import Regeln from './pages/Regeln'
import Vergleich from './pages/Vergleich'
import Wetten from './pages/Wetten'

export default function App() {
  const {
    data: me,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['me'],
    // 401 = nicht eingeloggt → null (zeigt Login). Netz-/Serverfehler werfen
    // durch, damit react-query retryt und wir eine Fehleransicht zeigen statt
    // den User faelschlich auszuloggen.
    queryFn: () => api.me().catch((e) => {
      if (isUnauthorized(e)) return null
      throw e
    }),
  })
  const { data: addons } = useQuery({
    queryKey: ['addons'],
    queryFn: () => api.addons().catch(() => []),
    enabled: !!me,
  })
  const sidebetsAktiv = (addons ?? []).some((a) => a.key === 'sidebets' && a.active)
  if (isLoading) return <p className="p-8 text-ink-mute">Lade…</p>
  if (isError)
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center text-ink-mute">
        <p>Verbindung zum Server fehlgeschlagen.</p>
        <button
          onClick={() => refetch()}
          className="rounded-full border border-accent px-4 py-1 text-sm font-bold text-accent"
        >
          Erneut versuchen
        </button>
      </div>
    )
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
        <Route path="/regeln" element={<Regeln />} />
        {sidebetsAktiv && <Route path="/wetten" element={<Wetten />} />}
        <Route path="/admin" element={<Admin />} />
        <Route path="/datenschutz" element={<Datenschutz />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
