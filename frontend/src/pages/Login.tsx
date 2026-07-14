import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import Input from '../components/ui/Input'

export default function Login() {
  const queryClient = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      const me = await api.login(username, password)
      queryClient.setQueryData(['me'], me)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login fehlgeschlagen')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-xs">
        <Card glow className="space-y-4 p-7 text-center">
          <h1 className="flex items-center justify-center gap-1 text-2xl font-black tracking-wide text-ink">
            <Icon name="blitz" size={20} className="text-accent" />
            METER<span className="text-accent [text-shadow:var(--t-glow)]">MACHEN</span>
          </h1>
          <p className="text-xs text-ink-mute">Wer macht die Meter?</p>
          <Input
            label="Benutzername"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="text-left"
          />
          <Input
            label="Passwort"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="text-left"
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" className="w-full">
            Los geht's
          </Button>
        </Card>
        <p className="mt-4 text-center text-[11px] text-ink-mute">
          <Link to="/datenschutz" className="hover:text-accent">
            Datenschutz
          </Link>
        </p>
      </form>
    </div>
  )
}
