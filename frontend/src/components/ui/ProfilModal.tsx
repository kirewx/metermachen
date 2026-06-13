import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Me } from '../../api/client'
import AvatarWahl from './AvatarWahl'
import Button from './Button'
import Input from './Input'
import Modal from './Modal'
import { useToast } from './Toast'

type Props = { me: Me; open: boolean; onClose: () => void }

export default function ProfilModal({ me, open, onClose }: Props) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState(me.display_name)
  const [avatar, setAvatar] = useState(me.avatar)
  const [passwort, setPasswort] = useState('')

  const { data: strava } = useQuery({ queryKey: ['strava-status'], queryFn: api.stravaStatus })
  const trennen = useMutation({
    mutationFn: () => api.disconnectStrava(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strava-status'] })
      toast('Strava getrennt', 'ok')
    },
    onError: (e) => toast(e.message),
  })

  const save = useMutation({
    mutationFn: () =>
      api.patchMe({
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
          <div className="rounded-xl border border-line p-3">
            <div className="mb-2 text-xs font-semibold text-ink-mute">Strava</div>
            {strava.connected ? (
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => trennen.mutate()}
                disabled={trennen.isPending}
              >
                Strava trennen
              </Button>
            ) : (
              <Button
                variant="ghost"
                className="w-full"
                onClick={() => {
                  window.location.href = '/api/strava/connect'
                }}
              >
                Mit Strava verbinden
              </Button>
            )}
          </div>
        )}
        <Button
          className="w-full"
          disabled={!name || (passwort.length > 0 && passwort.length < 4)}
          onClick={() => save.mutate()}
        >
          Speichern
        </Button>
      </div>
    </Modal>
  )
}
