import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../../api/client'
import Icon from '../ui/Icon'
import { useToast } from '../ui/Toast'
import SchnellwahlCard from './SchnellwahlCard'

const KEY = 'schnellwahl-leiste-offen'

export default function SchnellwahlLeiste() {
  const [offen, setOffen] = useState(localStorage.getItem(KEY) !== 'zu')
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const save = useMutation({
    mutationFn: api.createActivity,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activities'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
    onError: (e) => toast(e.message),
  })

  function toggle() {
    const neu = !offen
    setOffen(neu)
    localStorage.setItem(KEY, neu ? 'offen' : 'zu')
  }

  return (
    <div>
      <button
        type="button"
        onClick={toggle}
        className="mb-2 inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute hover:text-accent"
      >
        <Icon name="blitz" size={12} />
        Schnellwahl
        <Icon name="chevron" size={12} className={offen ? 'rotate-180' : ''} />
      </button>
      {offen && categories.length > 0 && (
        <SchnellwahlCard
          variant="kompakt"
          categories={categories}
          onSubmit={(input) => save.mutateAsync(input)}
        />
      )}
    </div>
  )
}
