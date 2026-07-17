import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Achievement, type Activity, type ActivityInput } from '../api/client'
import SchnellwahlCard from '../components/activities/SchnellwahlCard'
import Button from '../components/ui/Button'
import Icon from '../components/ui/Icon'
import Modal from '../components/ui/Modal'
import { aktiveSeason, saisonLabel } from '../components/ui/season'
import { useToast } from '../components/ui/Toast'

export default function MeineAktivitaeten() {
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season = aktiveSeason(seasons)
  const year = season?.year ?? new Date().getFullYear()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<Activity | null>(null)
  const [loeschId, setLoeschId] = useState<number | null>(null)

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
    mutationFn: (input: ActivityInput) =>
      editing ? api.patchActivity(editing.id, input) : api.createActivity(input),
    onSuccess: () => {
      if (editing) toast('Eintrag aktualisiert', 'ok')
      setEditing(null)
      invalidate()
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
      <SchnellwahlCard
        key={editing?.id ?? 'neu'}
        categories={categories}
        initial={editing ?? undefined}
        onSubmit={(input) => save.mutateAsync(input)}
        onCancel={editing ? () => setEditing(null) : undefined}
      />
      <div className="flex items-baseline justify-between">
        <h2 className="text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
          Meine Einträge {saisonLabel(season)}
        </h2>
        <span className="text-sm font-black tabular-nums text-accent [text-shadow:var(--t-glow)]">
          {Math.round(gesamt)} km gewertet
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
                  {Math.round(summe)} km
                </span>
              </button>
              {auf && (
                <ul className="space-y-1 pb-2 pl-8">
                  {eintraege.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-3 border-t border-line/20 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-ink">
                          <span className="font-mono tabular-nums">{a.distance_km}</span> km
                          <span className="text-accent"> → {a.scaled_km} km</span>
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
                        <p className="truncate text-xs text-ink-mute">
                          {a.date}
                          {a.start_time ? ` · ${a.start_time.slice(0, 5)} Uhr` : ''}
                          {a.duration_min ? ` · ${a.duration_min} min` : ''}
                          {a.elevation_m ? ` · ${Math.round(a.elevation_m)} hm` : ''}
                          {a.note ? ` · ${a.note}` : ''}
                        </p>
                      </div>
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
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
        {activities.length === 0 && <p className="text-sm text-ink-mute">Noch keine Einträge.</p>}
      </div>
      <Achievements />
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

const TIER_REIHE = ['bronze', 'silber', 'gold'] as const
const TIER_LABEL = { bronze: 'Bronze', silber: 'Silber', gold: 'Gold' } as const

function Achievements() {
  const queryClient = useQueryClient()
  const { data: achievements = [] } = useQuery({
    queryKey: ['achievements'],
    queryFn: api.achievements,
  })
  const toggle = useMutation({
    mutationFn: ({ key, showcased }: { key: string; showcased: boolean }) =>
      api.patchAchievement(key, showcased),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['achievements'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
  })
  if (achievements.length === 0) return null

  const stufen = achievements.filter((a) => a.tier !== null)
  const disziplinen = [...new Set(stufen.map((a) => a.discipline))] as string[]
  const einmal = achievements.filter((a) => a.emoji !== null && !a.hidden && a.tier === null)
  const hidden = achievements.filter((a) => a.hidden)
  const klassisch = achievements.filter(
    (a) => a.tier === null && !a.hidden && a.emoji === null,
  )

  const onToggle = (a: Achievement) =>
    toggle.mutate({ key: a.key, showcased: !(a.showcased ?? true) })

  return (
    <div>
      <h2 className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">
        Achievements
      </h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {klassisch.map((a) => (
          <AchievementBadge key={a.key} a={a} />
        ))}
        {disziplinen.map((d) => (
          <StufenKarte
            key={d}
            stufen={TIER_REIHE.map(
              (t) => stufen.find((s) => s.discipline === d && s.tier === t)!,
            ).filter(Boolean)}
          />
        ))}
        {einmal.map((a) => (
          <EinmalKarte key={a.key} a={a} onToggle={onToggle} />
        ))}
        {hidden.map((a) => (
          <HiddenKarte key={a.key} a={a} onToggle={onToggle} />
        ))}
      </div>
    </div>
  )
}

function EmojiToggle({ a, onToggle }: { a: Achievement; onToggle: (a: Achievement) => void }) {
  if (!a.achieved || !a.emoji) return null
  const an = a.showcased ?? true
  return (
    <button
      type="button"
      onClick={() => onToggle(a)}
      className={`mt-2 flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
        an ? 'border-accent text-accent' : 'border-line text-ink-mute'
      }`}
      title="Emoji neben deinem Namen anzeigen"
    >
      <span className="text-sm">{a.emoji}</span>
      {an ? 'wird getragen' : 'abgelegt'}
    </button>
  )
}

function StufenKarte({ stufen }: { stufen: Achievement[] }) {
  const label = stufen[0]?.parts[0]?.label ?? ''
  const naechste = stufen.find((s) => !s.achieved)
  return (
    <div
      className={`rounded-xl border p-3 ${
        stufen.some((s) => s.achieved) ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon name={stufen[0].icon} size={20} className="text-accent" />
        <span className="text-sm font-bold text-ink">{label}</span>
      </div>
      <div className="mt-2 flex gap-1.5">
        {stufen.map((s) => (
          <span
            key={s.key}
            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${
              s.achieved
                ? s.tier === 'gold'
                  ? 'border-amber-400 text-amber-400'
                  : s.tier === 'silber'
                    ? 'border-slate-300 text-slate-300'
                    : 'border-amber-700 text-amber-700'
                : 'border-line/40 text-ink-mute'
            }`}
          >
            {TIER_LABEL[s.tier as keyof typeof TIER_LABEL]}
          </span>
        ))}
      </div>
      {naechste && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(naechste.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] tabular-nums text-ink-mute">
            {Math.round(naechste.parts[0]?.current_km ?? 0)}/
            {Math.round(naechste.parts[0]?.target_km ?? 0)} km bis{' '}
            {TIER_LABEL[naechste.tier as keyof typeof TIER_LABEL]}
          </p>
        </>
      )}
    </div>
  )
}

function EinmalKarte({ a, onToggle }: { a: Achievement; onToggle: (a: Achievement) => void }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        a.achieved ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className={`text-sm font-bold ${a.achieved ? 'text-accent' : 'text-ink'}`}>
          {a.title}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {!a.achieved && a.parts.length > 0 && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(a.progress * 100)}%` }}
            />
          </div>
          <p className="mt-1 font-mono text-[10px] tabular-nums text-ink-mute">
            {Math.round(a.parts[0].current_km)}/{Math.round(a.parts[0].target_km)} MM
          </p>
        </>
      )}
      {!a.achieved && a.parts.length === 0 && (
        <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-ink-mute">
          {a.claimed_by ? `vergeben an ${a.claimed_by}` : 'bekommt nur die erste Person'}
        </p>
      )}
      <EmojiToggle a={a} onToggle={onToggle} />
    </div>
  )
}

function HiddenKarte({ a, onToggle }: { a: Achievement; onToggle: (a: Achievement) => void }) {
  if (!a.achieved) {
    return (
      <div className="rounded-xl border border-line/40 p-3 opacity-60">
        <div className="flex items-center gap-2">
          <Icon name="medaille" size={20} className="text-ink-mute" />
          <span className="text-sm font-bold text-ink">???</span>
        </div>
        <p className="mt-1 text-xs text-ink-mute">Verstecktes Achievement.</p>
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-accent p-3 shadow-glow">
      <div className="flex items-center gap-2">
        <span className="text-lg">{a.emoji}</span>
        <span className="text-sm font-bold text-accent">{a.title}</span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {a.unlocked_at && (
        <p className="mt-1 font-mono text-[10px] text-ink-mute">
          freigeschaltet am {new Date(a.unlocked_at).toLocaleDateString('de-DE')}
        </p>
      )}
      <EmojiToggle a={a} onToggle={onToggle} />
    </div>
  )
}

function AchievementBadge({ a }: { a: Achievement }) {
  return (
    <div
      className={`rounded-xl border p-3 ${
        a.achieved ? 'border-accent shadow-glow' : 'border-line/40 opacity-60'
      }`}
    >
      <div className="flex items-center gap-2">
        <Icon
          name={a.icon}
          size={20}
          className={a.achieved ? 'text-accent' : 'text-ink-mute'}
        />
        <span className={`text-sm font-bold ${a.achieved ? 'text-accent' : 'text-ink'}`}>
          {a.title}
        </span>
      </div>
      <p className="mt-1 text-xs text-ink-mute">{a.description}</p>
      {!a.achieved && (
        <>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-line/40">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${Math.round(a.progress * 100)}%` }}
            />
          </div>
          {a.parts.some((p) => p.target_km >= 1) && (
            <p className="mt-1 space-x-2 font-mono text-[10px] tabular-nums text-ink-mute">
              {a.parts
                .filter((p) => p.target_km >= 1)
                .map((p) => (
                  <span key={p.label}>
                    {p.label}: {Math.round(p.current_km)}/{Math.round(p.target_km)} km
                  </span>
                ))}
            </p>
          )}
        </>
      )}
    </div>
  )
}
