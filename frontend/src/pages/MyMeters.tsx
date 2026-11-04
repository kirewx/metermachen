import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, type Activity, type ActivityInput } from '../api/client'
import SchnellwahlCard from '../components/activities/SchnellwahlCard'
import { TogetherPanel, TogetherStapel } from '../components/together/TogetherBadge'
import { hatBadge, invalidateTogether, useTogetherAktiv } from '../components/together/together'
import Button from '../components/ui/Button'
import Icon from '../components/ui/Icon'
import Modal from '../components/ui/Modal'
import { aktiveSeason, saisonLabel } from '../components/ui/season'
import { useToast } from '../components/ui/Toast'

// MyMeters: quick entry plus the own entries of the season. Achievements live on the profile.
export default function MyMeters() {
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season = aktiveSeason(seasons)
  const year = season?.year ?? new Date().getFullYear()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<Activity | null>(null)
  const [loeschId, setLoeschId] = useState<number | null>(null)
  const [badgeOffen, setBadgeOffen] = useState<number | null>(null)
  const together = useTogetherAktiv()
  const { data: members } = useQuery({
    queryKey: ['together-members'],
    queryFn: api.togetherMembers,
    enabled: together,
  })
  // „Neu anlegen“ aus einem Tag: Formular mit den Werten des Partners, danach verknüpfen
  const [params, setParams] = useSearchParams()
  const verknuepfId = Number(params.get('verknuepfen')) || null
  const { data: vorschlaege = [] } = useQuery({
    queryKey: ['together-suggestions'],
    queryFn: api.togetherSuggestions,
    enabled: together && verknuepfId != null,
  })
  const tag = vorschlaege.find((v) => v.participant_id === verknuepfId)
  const vorlage = !editing && tag?.partner_activity ? tag.partner_activity : undefined
  function verknuepfenBeenden() {
    params.delete('verknuepfen')
    setParams(params, { replace: true })
  }

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const { data: activities = [] } = useQuery({
    queryKey: ['activities', year],
    queryFn: () => api.activities(year),
  })
  const catById = new Map(categories.map((c) => [c.id, c]))
  const gesamt = activities.reduce((s, a) => s + a.scaled_km, 0)
  const [offen, setOffen] = useState<Set<number>>(new Set())
  const toggle = (catId: number) =>
    setOffen((s) => {
      const next = new Set(s)
      if (next.has(catId)) next.delete(catId)
      else next.add(catId)
      return next
    })
  const gruppen = [...catById.values()]
    .map((cat) => {
      const eintraege = activities.filter((a) => a.category_id === cat.id)
      const summe = eintraege.reduce((s, a) => s + a.scaled_km, 0)
      return { cat, eintraege, summe }
    })
    .filter((g) => g.eintraege.length > 0)
    .sort((a, b) => b.summe - a.summe)

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ['activities'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
    queryClient.invalidateQueries({ queryKey: ['achievements'] })
  }
  const save = useMutation({
    mutationFn: async (input: ActivityInput) => {
      if (editing) return api.patchActivity(editing.id, input)
      const neu = await api.createActivity(input)
      if (vorlage && tag) await api.togetherConfirm(tag.participant_id, neu.id)
      return neu
    },
    onSuccess: () => {
      if (editing) toast('Eintrag aktualisiert', 'ok')
      if (vorlage) {
        toast('Eingetragen und verknüpft', 'ok')
        verknuepfenBeenden()
      }
      setEditing(null)
      invalidate()
      if (together) invalidateTogether(queryClient)
    },
    onError: (e) => toast(e.message),
  })
  const remove = useMutation({
    mutationFn: api.deleteActivity,
    onSuccess: () => {
      setLoeschId(null)
      invalidate()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <div className="space-y-6">
      {vorlage && tag && (
        <p className="text-sm text-ink-soft">
          Neue Aktivität für die gemeinsame Einheit mit{' '}
          <b className="text-ink">{tag.partners.map((p) => p.display_name).join(', ')}</b> — wird
          nach dem Eintragen verknüpft.
        </p>
      )}
      <SchnellwahlCard
        key={editing?.id ?? (vorlage ? `verknuepfen-${verknuepfId}` : 'neu')}
        categories={categories}
        initial={editing ?? undefined}
        vorlage={vorlage}
        members={together ? (members ?? []) : undefined}
        onSubmit={(input) => save.mutateAsync(input)}
        onCancel={editing ? () => setEditing(null) : vorlage ? verknuepfenBeenden : undefined}
      />
      <div className="flex items-baseline justify-between">
        <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
          Meine Einträge {saisonLabel(season)}
        </h2>
        <span className="text-sm font-black tabular-nums text-accent [text-shadow:var(--t-glow)]">
          {Math.round(gesamt)} MM gewertet
        </span>
      </div>
      <div className="space-y-1">
        {gruppen.map(({ cat, eintraege, summe }) => {
          const auf = offen.has(cat.id)
          return (
            <div key={cat.id} className="border-b border-line/30 last:border-0">
              <button
                type="button"
                onClick={() => toggle(cat.id)}
                className="flex w-full items-center gap-3 py-2.5 text-left"
              >
                <Icon
                  name="chevron"
                  size={14}
                  className={`text-ink-mute transition ${auf ? 'rotate-180' : ''}`}
                />
                <Icon name={cat.icon} size={20} className="shrink-0 text-accent" />
                <span className="flex-1 text-sm font-bold text-ink">{cat.name}</span>
                <span className="text-xs text-ink-mute">{eintraege.length} Einträge</span>
                <span className="w-20 text-right font-mono text-sm font-bold tabular-nums text-accent">
                  {Math.round(summe)} MM
                </span>
              </button>
              {auf && (
                <ul className="space-y-1 pb-2 pl-8">
                  {eintraege.map((a) => (
                    <li key={a.id} className="border-t border-line/20">
                      <div className="flex items-center gap-3 py-2">
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm text-ink">
                            <span className="font-mono tabular-nums">{a.distance_km}</span> km
                            <span className="text-accent"> → {a.scaled_km} MM</span>
                            {a.edited && (
                              <span className="ml-2 text-xs text-ink-mute">(bearbeitet)</span>
                            )}
                            {a.source === 'strava' &&
                              (a.strava_url ? (
                                <a
                                  href={a.strava_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="ml-2 rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent hover:bg-accent/10"
                                >
                                  View on Strava
                                </a>
                              ) : (
                                <span className="ml-2 rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
                                  Strava
                                </span>
                              ))}
                          </p>
                          <p className="break-words text-xs text-ink-mute">
                            {a.date}
                            {a.start_time ? ` · ${a.start_time.slice(0, 5)} Uhr` : ''}
                            {a.duration_min ? ` · ${a.duration_min} min` : ''}
                            {a.elevation_m ? ` · ${Math.round(a.elevation_m)} hm` : ''}
                            {a.note ? ` · ${a.note}` : ''}
                          </p>
                        </div>
                        {together && a.together && hatBadge(a.together, true) && (
                          <TogetherStapel
                            together={a.together}
                            own
                            offen={badgeOffen === a.id}
                            onToggle={() => setBadgeOffen(badgeOffen === a.id ? null : a.id)}
                          />
                        )}
                        <button
                          aria-label="Bearbeiten"
                          className="text-ink-mute hover:text-accent"
                          onClick={() => setEditing(a)}
                        >
                          <Icon name="stift" size={16} />
                        </button>
                        <button
                          aria-label="Löschen"
                          className="text-ink-mute hover:text-danger"
                          onClick={() => setLoeschId(a.id)}
                        >
                          <Icon name="papierkorb" size={16} />
                        </button>
                      </div>
                      {together && a.together && badgeOffen === a.id && (
                        <TogetherPanel together={a.together} own />
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
        {activities.length === 0 && <p className="text-sm text-ink-mute">Noch keine Einträge.</p>}
      </div>
      <Modal open={loeschId !== null} onClose={() => setLoeschId(null)} title="Eintrag löschen?">
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setLoeschId(null)}>
            Abbrechen
          </Button>
          <Button variant="danger" onClick={() => loeschId !== null && remove.mutate(loeschId)}>
            Löschen
          </Button>
        </div>
      </Modal>
    </div>
  )
}
