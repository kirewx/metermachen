import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api, type Milestone, type Season } from '../api/client'
import AvatarWahl from '../components/ui/AvatarWahl'
import Button from '../components/ui/Button'
import Card from '../components/ui/Card'
import Icon from '../components/ui/Icon'
import IconPicker from '../components/ui/IconPicker'
import Input from '../components/ui/Input'
import { MEILENSTEIN_ICONS, SPORT_ICONS } from '../components/ui/icons'
import { useToast } from '../components/ui/Toast'

const H = ({ children }: { children: React.ReactNode }) => (
  <h2 className="mb-3 text-[10px] font-bold uppercase tracking-[0.2em] text-ink-mute">{children}</h2>
)

const STRAVA_SPORT_TYPES = [
  'Run', 'TrailRun', 'Walk', 'Hike', 'Ride', 'MountainBikeRide', 'GravelRide',
  'EBikeRide', 'VirtualRide', 'VirtualRun', 'Swim', 'Rowing', 'Kayaking',
  'NordicSki', 'AlpineSki', 'BackcountrySki', 'Snowboard', 'IceSkate',
  'InlineSkate', 'Elliptical', 'StairStepper', 'Workout', 'WeightTraining',
]

export default function Admin() {
  return (
    <div className="space-y-6">
      <Kategorien />
      <Jahr />
      <NeuerUser />
    </div>
  )
}

function Kategorien() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['categories'] })
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: number; factor?: number; default_km?: number; is_active?: boolean; strava_sport_types?: string[] }) =>
      api.patchCategory(id, b),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
  const leer = { name: '', factor: '1', color: '#00b3cc', icon: 'medaille', default_km: '10' }
  const [neu, setNeu] = useState(leer)
  const create = useMutation({
    mutationFn: () =>
      api.createCategory({
        name: neu.name,
        factor: parseFloat(neu.factor),
        color: neu.color,
        icon: neu.icon,
        default_km: parseFloat(neu.default_km),
        strava_sport_types: [],
      }),
    onSuccess: () => {
      setNeu(leer)
      refresh()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <Card>
      <H>Kategorien & Faktoren</H>
      <div className="space-y-2">
        {categories.map((c) => (
          <div
            key={c.id}
            className={`flex flex-wrap items-center gap-3 rounded-xl border border-line p-2 ${
              c.is_active ? '' : 'opacity-40'
            }`}
          >
            <Icon name={c.icon} size={20} className="text-accent" />
            <span className="min-w-24 flex-1 text-sm font-bold text-ink">{c.name}</span>
            <Input
              label="Faktor"
              type="number"
              step="0.5"
              defaultValue={c.factor}
              className="w-20"
              onBlur={(e) => {
                const factor = parseFloat(e.target.value)
                if (factor > 0 && factor !== c.factor) patch.mutate({ id: c.id, factor })
              }}
            />
            <Input
              label="Standard-km"
              type="number"
              step="1"
              min="1"
              defaultValue={c.default_km}
              className="w-24"
              onBlur={(e) => {
                const default_km = parseFloat(e.target.value)
                if (default_km > 0 && default_km !== c.default_km)
                  patch.mutate({ id: c.id, default_km })
              }}
            />
            <Button
              variant="ghost"
              onClick={() => patch.mutate({ id: c.id, is_active: !c.is_active })}
            >
              {c.is_active ? 'Deaktivieren' : 'Aktivieren'}
            </Button>
            <div className="w-full">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-mute">
                Strava-Sportarten
              </div>
              <div className="flex flex-wrap gap-1">
                {STRAVA_SPORT_TYPES.map((sport) => {
                  const aktiv = c.strava_sport_types.includes(sport)
                  return (
                    <button
                      key={sport}
                      type="button"
                      onClick={() => {
                        const next = aktiv
                          ? c.strava_sport_types.filter((s) => s !== sport)
                          : [...c.strava_sport_types, sport]
                        patch.mutate({ id: c.id, strava_sport_types: next })
                      }}
                      className={`rounded-full border px-2 py-0.5 text-[11px] transition ${
                        aktiv
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-line text-ink-mute hover:border-accent'
                      }`}
                    >
                      {sport}
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-3 rounded-xl border border-dashed border-line p-3">
        <div className="flex flex-wrap gap-2">
          <Input label="Name" value={neu.name} onChange={(e) => setNeu({ ...neu, name: e.target.value })} />
          <Input
            label="Faktor"
            type="number"
            step="0.5"
            className="w-20"
            value={neu.factor}
            onChange={(e) => setNeu({ ...neu, factor: e.target.value })}
          />
          <Input
            label="Standard-km"
            type="number"
            className="w-24"
            value={neu.default_km}
            onChange={(e) => setNeu({ ...neu, default_km: e.target.value })}
          />
          <label className="flex flex-col gap-1 text-xs font-semibold text-ink-mute">
            Farbe
            <input
              type="color"
              className="h-9 w-12 rounded-xl border border-line bg-surface"
              value={neu.color}
              onChange={(e) => setNeu({ ...neu, color: e.target.value })}
            />
          </label>
        </div>
        <IconPicker auswahl={SPORT_ICONS} value={neu.icon} onChange={(icon) => setNeu({ ...neu, icon })} />
        <Button
          disabled={!neu.name || !(parseFloat(neu.factor) > 0) || !(parseFloat(neu.default_km) > 0)}
          onClick={() => create.mutate()}
        >
          Kategorie anlegen
        </Button>
      </div>
    </Card>
  )
}

function Jahr() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season: Season | undefined = seasons.find((s) => s.year === new Date().getFullYear())
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['seasons'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const [goal, setGoal] = useState('')
  const [milestones, setMilestones] = useState<Milestone[] | null>(null)
  if (!season) return null
  const ms = milestones ?? season.milestones

  return (
    <Card>
      <H>Jahr {season.year}</H>
      <Input
        label="Ziel (gewertete km)"
        type="number"
        className="w-36"
        defaultValue={season.goal_km}
        onChange={(e) => setGoal(e.target.value)}
      />
      <h3 className="mt-4 mb-1 text-xs font-semibold text-ink-mute">Meilensteine</h3>
      <div className="space-y-2">
        {ms.map((m, i) => (
          <div key={i} className="flex flex-wrap items-end gap-2">
            <Input
              label="km"
              type="number"
              className="w-24"
              value={m.km}
              onChange={(e) =>
                setMilestones(ms.map((x, j) => (j === i ? { ...x, km: Number(e.target.value) } : x)))
              }
            />
            <Input
              label="Bezeichnung"
              className="flex-1"
              value={m.label}
              onChange={(e) =>
                setMilestones(ms.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))
              }
            />
            <IconPicker
              auswahl={MEILENSTEIN_ICONS}
              value={m.icon}
              onChange={(icon) => setMilestones(ms.map((x, j) => (j === i ? { ...x, icon } : x)))}
            />
            <button
              aria-label="Meilenstein entfernen"
              className="pb-2 text-ink-mute hover:text-danger"
              onClick={() => setMilestones(ms.filter((_, j) => j !== i))}
            >
              <Icon name="x" size={16} />
            </button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <Button
          variant="ghost"
          onClick={() => setMilestones([...ms, { km: 0, label: '', icon: 'fahne' }])}
        >
          + Meilenstein
        </Button>
        <Button
          onClick={() =>
            api
              .patchSeason(season.id, { goal_km: goal ? parseFloat(goal) : undefined, milestones: ms })
              .then(refresh)
              .catch((e) => toast(e.message))
          }
        >
          Speichern
        </Button>
      </div>
      <h3 className="mt-4 mb-1 text-xs font-semibold text-ink-mute">Kartenbild (Aquarell)</h3>
      <input
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="text-sm text-ink-mute"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) api.uploadMapImage(season.id, file).then(refresh).catch((err) => toast(err.message))
        }}
      />
      {season.map_image && <p className="mt-1 text-xs text-ink-mute">Aktuell: {season.map_image}</p>}
    </Card>
  )
}

function NeuerUser() {
  const toast = useToast()
  const leer = { username: '', password: '', display_name: '', avatar: 'icon:laufen' }
  const [form, setForm] = useState(leer)
  const create = useMutation({
    mutationFn: () => api.createUser(form),
    onSuccess: (u) => {
      toast(`${u.display_name} angelegt`, 'ok')
      setForm(leer)
    },
    onError: (e) => toast(e.message),
  })
  return (
    <Card>
      <H>Neues Mitglied</H>
      <div className="flex flex-wrap gap-2">
        <Input
          label="Benutzername"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        />
        <Input
          label="Anzeigename"
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
        <Input
          label="Passwort"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
      </div>
      <div className="mt-3">
        <div className="mb-1 text-xs font-semibold text-ink-mute">Avatar</div>
        <AvatarWahl value={form.avatar} onChange={(avatar) => setForm({ ...form, avatar })} />
      </div>
      <Button
        className="mt-3"
        disabled={!form.username || form.password.length < 4 || !form.display_name}
        onClick={() => create.mutate()}
      >
        Anlegen
      </Button>
    </Card>
  )
}
