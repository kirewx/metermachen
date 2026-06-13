import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import Icon from '../ui/Icon'
import { useToast } from '../ui/Toast'
import SchnellwahlCard from './SchnellwahlCard'

export default function SchnellwahlLeiste() {
  const [aktiv, setAktiv] = useState(false)
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const save = useMutation({
    mutationFn: api.createActivity,
    onSuccess: () => {
      setAktiv(false)
      queryClient.invalidateQueries({ queryKey: ['activities'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
    onError: (e) => toast(e.message),
  })

  // Solange keine Kategorien geladen sind, bleibt nur der Trigger sichtbar —
  // sonst gäbe es im offenen Zustand keine Karte und damit kein "Abbrechen".
  if (!aktiv || categories.length === 0) {
    return (
      <button
        type="button"
        onClick={() => setAktiv(true)}
        className="inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute hover:text-accent"
      >
        <Icon name="blitz" size={12} />
        Eintrag hinzufügen
      </button>
    )
  }

  return (
    <div>
      <div className="mb-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
        <Icon name="blitz" size={12} />
        Schnellwahl
      </div>
      <SchnellwahlCard
        variant="kompakt"
        categories={categories}
        onSubmit={(input) => save.mutateAsync(input)}
        onCancel={() => setAktiv(false)}
      />
    </div>
  )
}
