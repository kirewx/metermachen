import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import AvatarWahl from '../components/ui/AvatarWahl'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import Input from '../components/ui/Input'

export default function Einladung() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: invite, isLoading } = useQuery({
    queryKey: ['invite', token],
    queryFn: () => api.getInvite(token),
  })

  const [username, setUsername] = useState('')
  // null = noch nicht bearbeitet → Vorbelegung aus der Einladung anzeigen.
  // Sobald getippt (auch leer), gewinnt die Eingabe — kein Effekt nötig.
  const [displayNameEdit, setDisplayNameEdit] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [avatar, setAvatar] = useState('icon:laufen')
  const [error, setError] = useState('')

  const displayName = displayNameEdit ?? (invite?.valid ? (invite.display_name ?? '') : '')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const me = await api.acceptInvite(token, { username, password, display_name: displayName, avatar })
      queryClient.setQueryData(['me'], me)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registrierung fehlgeschlagen')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-xs">
        <Card glow className="space-y-4 p-7">
          <h1 className="flex items-center justify-center gap-1 text-2xl font-black tracking-wide text-ink">
            <Icon name="blitz" size={20} className="text-accent" />
            METER<span className="text-accent [text-shadow:var(--t-glow)]">MACHEN</span>
          </h1>
          {isLoading ? (
            <p className="text-center text-sm text-ink-mute">Lade…</p>
          ) : invite?.valid ? (
            <form onSubmit={submit} className="space-y-4">
              <p className="text-center text-xs text-ink-mute">Willkommen! Leg dein Konto an.</p>
              <Input label="Benutzername" value={username} onChange={(e) => setUsername(e.target.value)} />
              <Input
                label="Anzeigename"
                value={displayName}
                onChange={(e) => setDisplayNameEdit(e.target.value)}
              />
              <Input
                label="Passwort (min. 4 Zeichen)"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <div>
                <div className="mb-1 text-xs font-semibold text-ink-mute">Avatar</div>
                <AvatarWahl value={avatar} onChange={setAvatar} />
              </div>
              {error && <p className="text-sm text-danger">{error}</p>}
              <Button
                type="submit"
                className="w-full"
                disabled={!username || !displayName || password.length < 4}
              >
                Konto anlegen
              </Button>
            </form>
          ) : (
            <p className="text-center text-sm text-danger">
              Diese Einladung ist ungültig, abgelaufen oder bereits eingelöst.
            </p>
          )}
        </Card>
      </div>
    </div>
  )
}
