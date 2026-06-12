import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'

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
    <div className="flex min-h-screen items-center justify-center bg-emerald-50">
      <form onSubmit={submit} className="w-80 space-y-4 rounded-2xl bg-white p-8 shadow">
        <h1 className="text-center text-2xl font-bold">MeterMachen 🏃</h1>
        <input
          className="w-full rounded border p-2"
          placeholder="Benutzername"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="w-full rounded border p-2"
          type="password"
          placeholder="Passwort"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-emerald-600 p-2 font-semibold text-white">
          Einloggen
        </button>
      </form>
    </div>
  )
}
