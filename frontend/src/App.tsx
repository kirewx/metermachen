import { useQuery } from '@tanstack/react-query'
import { Link, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { api, isUnauthorized } from './api/client'
import ChallengeDetail from './components/challenges/ChallengeDetail'
import GroupEditor from './components/challenges/GroupEditor'
import Layout from './components/ui/Layout'
import { arenaEntryPath } from './components/ui/tabs'
import Admin from './pages/Admin'
import Arena from './pages/Arena'
import Challenges from './pages/Challenges'
import Datenschutz from './pages/Datenschutz'
import Einladung from './pages/Einladung'
import Feed from './pages/Feed'
import Login from './pages/Login'
import MyMeters from './pages/MyMeters'
import PasswortReset from './pages/PasswortReset'
import Profil from './pages/Profil'
import Regeln from './pages/Regeln'
import Vergleich from './pages/Vergleich'
import Wetten from './pages/Wetten'

// Regeln ohne Login: Die Seite selbst bringt kein Padding mit (das liefert
// sonst das Layout), daher hier Wrapper + Link zurück zur Anmeldung.
function RegelnOeffentlich() {
  return (
    <div className="p-4">
      <Regeln />
      <p className="mx-auto mt-6 max-w-2xl text-xs">
        <Link to="/" className="text-accent hover:underline">
          ← Zur Anmeldung
        </Link>
      </p>
    </div>
  )
}

// Old deep link /challenges/:id → new home inside the Arena.
function RedirectChallenge() {
  const { id } = useParams()
  return <Navigate to={`/arena/challenges/${id}`} replace />
}

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
  const aktiveAddons = new Set((addons ?? []).filter((a) => a.active).map((a) => a.key))
  const sidebetsAktiv = aktiveAddons.has('sidebets')
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
        <Route path="/passwort-reset/:token" element={<PasswortReset />} />
        <Route path="/datenschutz" element={<Datenschutz />} />
        <Route path="/regeln" element={<RegelnOeffentlich />} />
        <Route path="*" element={<Login />} />
      </Routes>
    )
  // Routes depend on the add-ons; wait for them so a refresh on /arena/wetten
  // never bounces to the home page while they load.
  if (addons === undefined) return <p className="p-8 text-ink-mute">Lade…</p>
  return (
    <Routes>
      <Route element={<Layout me={me} />}>
        <Route path="/" element={<Vergleich />} />
        <Route path="/feed" element={<Feed />} />
        <Route path="/mymeters" element={<MyMeters />} />
        <Route path="/arena" element={<Arena />}>
          <Route index element={<Navigate to={arenaEntryPath(aktiveAddons)} replace />} />
          <Route path="challenges" element={<Challenges />} />
          <Route path="challenges/:id" element={<ChallengeDetail />} />
          <Route path="challenges/:id/gruppen" element={<GroupEditor />} />
          {sidebetsAktiv && <Route path="wetten" element={<Wetten />} />}
        </Route>
        <Route path="/profil/:userId" element={<Profil />} />
        <Route path="/regeln" element={<Regeln />} />
        <Route path="/admin" element={me.is_admin ? <Admin /> : <Navigate to="/" replace />} />
        <Route path="/datenschutz" element={<Datenschutz />} />
        <Route path="/aktivitaeten" element={<Navigate to="/mymeters" replace />} />
        <Route path="/challenges" element={<Navigate to="/arena/challenges" replace />} />
        <Route path="/challenges/:id" element={<RedirectChallenge />} />
        <Route path="/wetten" element={<Navigate to="/arena/wetten" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
