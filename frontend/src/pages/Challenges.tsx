import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Challenge } from '../api/client'
import ChallengeHeroCard from '../components/challenges/ChallengeHeroCard'
import ChallengeInvite from '../components/challenges/ChallengeInvite'
import ChallengeRow from '../components/challenges/ChallengeRow'

function Abschnitt({ titel, children }: { titel: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="px-1 text-[11px] font-bold uppercase tracking-wider text-ink-mute">
        {titel}
      </h2>
      {children}
    </section>
  )
}

export default function Challenges() {
  const queryClient = useQueryClient()
  const { data: alle = [], error } = useQuery({
    queryKey: ['challenges'],
    queryFn: api.challenges,
  })
  const join = useMutation({
    mutationFn: (id: number) => api.joinChallenge(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['challenges'] }),
  })

  const nachEnde = (a: Challenge, b: Challenge) =>
    a.period_end.localeCompare(b.period_end)
  const dabei = alle.filter((c) => c.status === 'laufend' && c.bin_dabei).sort(nachEnde)
  const offen = alle.filter((c) => c.kann_beitreten && c.status === 'laufend')
  const geplant = alle.filter((c) => c.status === 'geplant').sort(nachEnde)
  const beendet = alle
    .filter((c) => c.status === 'beendet')
    .sort((a, b) => b.period_end.localeCompare(a.period_end))

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (alle.length === 0)
    return (
      <p className="p-8 text-center text-sm text-ink-mute">
        Noch keine Challenges — der Admin legt die erste an.
      </p>
    )

  return (
    <div className="mx-auto max-w-xl space-y-5">
      {dabei.length > 0 && (
        <Abschnitt titel="Du bist dabei">
          <div className="flex snap-x snap-mandatory gap-2 overflow-x-auto pb-1">
            {dabei.map((ch) => (
              <ChallengeHeroCard key={ch.id} ch={ch} />
            ))}
          </div>
        </Abschnitt>
      )}
      {offen.length > 0 && (
        <Abschnitt titel="Mitmachen?">
          {offen.map((ch) => (
            <ChallengeInvite
              key={ch.id}
              ch={ch}
              busy={join.isPending}
              onJoin={() => join.mutate(ch.id)}
            />
          ))}
        </Abschnitt>
      )}
      {geplant.length > 0 && (
        <Abschnitt titel="Geplant">
          <div className="rounded-2xl border border-line bg-card">
            {geplant.map((ch) => (
              <ChallengeRow key={ch.id} ch={ch} />
            ))}
          </div>
        </Abschnitt>
      )}
      {beendet.length > 0 && (
        <Abschnitt titel="Beendet">
          <div className="rounded-2xl border border-line bg-card opacity-70">
            {beendet.map((ch) => (
              <ChallengeRow key={ch.id} ch={ch} />
            ))}
          </div>
        </Abschnitt>
      )}
    </div>
  )
}
