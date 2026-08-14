import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import Input from '../components/ui/Input'

export default function PasswortReset() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [password, setPassword] = useState('')
  const [wiederholung, setWiederholung] = useState('')
  const [error, setError] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const me = await api.resetPassword(token, password)
      queryClient.setQueryData(['me'], me)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Zurücksetzen fehlgeschlagen')
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
          <form onSubmit={submit} className="space-y-4">
            <p className="text-center text-xs text-ink-mute">
              Leg ein neues Passwort für dein Konto fest.
            </p>
            <Input
              label="Neues Passwort (min. 4 Zeichen)"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Input
              label="Passwort wiederholen"
              type="password"
              value={wiederholung}
              onChange={(e) => setWiederholung(e.target.value)}
            />
            {error && <p className="text-sm text-danger">{error}</p>}
            <Button
              type="submit"
              className="w-full"
              disabled={password.length < 4 || password !== wiederholung}
            >
              Passwort setzen
            </Button>
          </form>
        </Card>
      </div>
    </div>
  )
}
