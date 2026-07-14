import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { api, type Me } from '../../api/client'
import AvatarWahl from './AvatarWahl'
import Button from './Button'
import Input from './Input'
import Modal from './Modal'
import StravaConnectButton from './StravaConnectButton'
import { useToast } from './Toast'

type Props = { me: Me; open: boolean; onClose: () => void }

export default function ProfilModal({ me, open, onClose }: Props) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [username, setUsername] = useState(me.username)
  const [name, setName] = useState(me.display_name)
  const [avatar, setAvatar] = useState(me.avatar)
  const [passwort, setPasswort] = useState('')

  const { data: strava } = useQuery({
    queryKey: ['strava-status'],
    queryFn: api.stravaStatus,
    refetchInterval: (query) =>
      query.state.data?.backfill?.state === 'running' ? 1500 : false,
  })

  const prevBackfill = useRef<string | undefined>(undefined)
  useEffect(() => {
    const state = strava?.backfill?.state
    if (prevBackfill.current === 'running' && state === 'done') {
      const total = strava?.backfill?.total ?? 0
      if (total > 0) toast(`${total} Aktivitäten importiert`, 'ok')
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
      queryClient.invalidateQueries({ queryKey: ['activities'] })
    }
    prevBackfill.current = state
  }, [strava?.backfill?.state, strava?.backfill?.total, queryClient, toast])

  const trennen = useMutation({
    mutationFn: () => api.disconnectStrava(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strava-status'] })
      toast('Strava getrennt', 'ok')
    },
    onError: (e) => toast(e.message),
  })

  const zustimmen = useMutation({
    mutationFn: () => api.consentStrava(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strava-status'] }),
    onError: (e) => toast(e.message),
  })

  const save = useMutation({
    mutationFn: () =>
      api.patchMe({
        ...(username !== me.username ? { username } : {}),
        display_name: name,
        avatar,
        ...(passwort ? { password: passwort } : {}),
      }),
    onSuccess: (neu) => {
      queryClient.setQueryData(['me'], neu)
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
      setPasswort('')
      toast('Profil gespeichert', 'ok')
      onClose()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <Modal open={open} onClose={onClose} title="Profil">
      <div className="space-y-4">
        <Input
          label="Benutzername (Login)"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <Input label="Anzeigename" value={name} onChange={(e) => setName(e.target.value)} />
        <div>
          <div className="mb-1 text-xs font-semibold text-ink-mute">Avatar</div>
          <AvatarWahl value={avatar} onChange={setAvatar} />
        </div>
        <Input
          label="Neues Passwort (leer = unverändert)"
          type="password"
          value={passwort}
          onChange={(e) => setPasswort(e.target.value)}
        />
        {strava?.enabled && (
          <div className="space-y-3 border-t border-line/40 pt-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-mono text-xs uppercase tracking-wider text-ink-tech">
                Strava
                {strava.connected && strava.backfill?.state !== 'running' && (
                  <span className="text-accent">✓ Verbunden</span>
                )}
              </span>
              {strava.connected ? (
                strava.backfill?.state === 'running' ? (
                  <span className="flex items-center gap-2 text-sm text-ink-mute">
                    <span className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent" />
                    Importiere… {strava.backfill.done} von {strava.backfill.total}
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => trennen.mutate()}
                    disabled={trennen.isPending}
                    className="text-sm text-ink-mute hover:text-danger"
                  >
                    Strava trennen
                  </button>
                )
              ) : (
                strava.consent && <StravaConnectButton />
              )}
            </div>
            {!strava.connected && !strava.consent && (
              <label className="flex items-start gap-2 text-xs text-ink-soft">
                <input
                  type="checkbox"
                  className="mt-0.5 shrink-0"
                  checked={false}
                  disabled={zustimmen.isPending}
                  onChange={() => zustimmen.mutate()}
                />
                <span>
                  Ich bin einverstanden, dass meine – auch via Strava importierten –
                  Aktivitäten für die anderen Mitglieder meiner Gruppe im Ranking sichtbar
                  sind. Danach kann ich Strava verbinden.
                </span>
              </label>
            )}
          </div>
        )}
        {strava?.enabled && (
          <p className="text-[11px] text-ink-mute">
            Mit dem Verbinden holen wir deine Strava-Aktivitäten fürs Ranking.{' '}
            <a href="/datenschutz" target="_blank" className="text-accent hover:underline">
              Datenschutz
            </a>
          </p>
        )}
        <Button
          className="w-full"
          disabled={!name || !username || (passwort.length > 0 && passwort.length < 4)}
          onClick={() => save.mutate()}
        >
          Speichern
        </Button>
      </div>
    </Modal>
  )
}
