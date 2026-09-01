import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import {
  api,
  type AddOn,
  type AdminUser,
  type Category,
  type Invite,
  type Milestone,
  type ResetLink,
  type Season,
} from '../api/client'
import ChallengesAdmin from '../components/admin/ChallengesAdmin'
import HiddenAchievementsAdmin from '../components/admin/HiddenAchievementsAdmin'
import Avatar from '../components/ui/Avatar'
import Button from '../components/ui/Button'
import Collapsible from '../components/ui/Collapsible'
import Icon from '../components/ui/Icon'
import IconPicker from '../components/ui/IconPicker'
import Input from '../components/ui/Input'
import Modal from '../components/ui/Modal'
import { MEILENSTEIN_ICONS, SPORT_ICONS } from '../components/ui/icons'
import { aktiveSeason, saisonLabel } from '../components/ui/season'
import Select from '../components/ui/Select'
import { useToast } from '../components/ui/Toast'

// Strava sport_type-Werte (Stand 2024+). Sportarten ohne Distanz (Tennis, Golf …)
// können zwar zugeordnet werden, zählen aber 0 km und werden beim Import übersprungen.
const STRAVA_SPORT_TYPES = [
  // Distanz-Sportarten (zählen km)
  'Run', 'TrailRun', 'VirtualRun', 'Walk', 'Hike', 'Ride', 'MountainBikeRide',
  'GravelRide', 'EBikeRide', 'EMountainBikeRide', 'VirtualRide', 'Velomobile',
  'Handcycle', 'Wheelchair', 'Swim', 'Rowing', 'VirtualRow', 'Kayaking',
  'Canoeing', 'StandUpPaddling', 'Surfing', 'Kitesurf', 'Windsurf', 'Sail',
  'NordicSki', 'AlpineSki', 'BackcountrySki', 'RollerSki', 'Snowboard',
  'Snowshoe', 'IceSkate', 'InlineSkate', 'Skateboard',
  // km-lose Sportarten (Zuordnung möglich, zählen aber nichts)
  'Tennis', 'TableTennis', 'Badminton', 'Squash', 'Racquetball', 'Pickleball',
  'Golf', 'Soccer', 'RockClimbing', 'Crossfit', 'Elliptical', 'StairStepper',
  'WeightTraining', 'Workout', 'HighIntensityIntervalTraining', 'Yoga', 'Pilates',
]

export default function Admin() {
  return (
    <div className="space-y-8">
      <Kategorien />
      <StravaMapping />
      <Jahr />
      <AddOns />
      <ChallengesAdmin />
      <Mitglieder />
      <Einladungen />
      <HiddenAchievementsAdmin />
    </div>
  )
}

// Speicherformat ist UTC-ISO, das <input type="datetime-local"> erwartet lokale Zeit.
function toLocalInput(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function fromLocalInput(v: string): string | null {
  return v ? new Date(v).toISOString() : null
}

function AddOns() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: addons = [] } = useQuery({ queryKey: ['addons'], queryFn: api.addons })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['addons'] })
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: number } & Parameters<typeof api.patchAddon>[1]) =>
      api.patchAddon(id, b),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
  const [neu, setNeu] = useState({ key: '', label: '' })
  const create = useMutation({
    mutationFn: () => api.createAddon({ key: neu.key, label: neu.label }),
    onSuccess: () => {
      setNeu({ key: '', label: '' })
      refresh()
    },
    onError: (e) => toast(e.message),
  })
  const [loeschAddon, setLoeschAddon] = useState<AddOn | null>(null)
  const loeschen = useMutation({
    mutationFn: (id: number) => api.deleteAddon(id),
    onSuccess: () => {
      setLoeschAddon(null)
      refresh()
    },
    onError: (e) => toast(e.message),
  })

  return (
    <Collapsible title="Add-ons">
      <p className="mb-3 text-xs text-ink-mute">
        Features an- und ausschalten. Optionales Zeitfenster: aktiv nur, wenn eingeschaltet
        <em> und</em> (falls gesetzt) innerhalb des Fensters.
      </p>
      <div className="space-y-3">
        {addons.map((a) => (
          <div key={a.id} className="border-b border-line/30 pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-32 flex-1 text-sm font-bold text-ink">{a.label}</span>
              <span className="font-mono text-xs text-ink-mute">{a.key}</span>
              <span
                className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                  a.active
                    ? 'border border-accent/40 text-accent'
                    : 'border border-line text-ink-tech'
                }`}
              >
                {a.active ? 'aktiv' : 'aus'}
              </span>
              <Button variant="ghost" onClick={() => patch.mutate({ id: a.id, enabled: !a.enabled })}>
                {a.enabled ? 'Deaktivieren' : 'Aktivieren'}
              </Button>
              <button
                aria-label={`Add-on ${a.key} löschen`}
                className="text-ink-mute hover:text-danger"
                onClick={() => setLoeschAddon(a)}
              >
                <Icon name="papierkorb" size={16} />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-3">
              <label className="flex flex-col gap-1 text-xs font-semibold text-ink-mute">
                Aktiv ab
                <input
                  type="datetime-local"
                  className="rounded-xl border border-line bg-surface px-2 py-1.5 text-sm text-ink"
                  defaultValue={toLocalInput(a.active_from)}
                  onBlur={(e) =>
                    patch.mutate({ id: a.id, active_from: fromLocalInput(e.target.value) })
                  }
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-semibold text-ink-mute">
                Aktiv bis
                <input
                  type="datetime-local"
                  className="rounded-xl border border-line bg-surface px-2 py-1.5 text-sm text-ink"
                  defaultValue={toLocalInput(a.active_until)}
                  onBlur={(e) =>
                    patch.mutate({ id: a.id, active_until: fromLocalInput(e.target.value) })
                  }
                />
              </label>
            </div>
          </div>
        ))}
        {addons.length === 0 && (
          <p className="text-sm text-ink-mute">Noch keine Add-ons angelegt.</p>
        )}
      </div>
      <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-dashed border-line pt-3">
        <Input
          label="Key (a-z, 0-9, _)"
          value={neu.key}
          onChange={(e) => setNeu({ ...neu, key: e.target.value.toLowerCase() })}
        />
        <Input
          label="Bezeichnung"
          value={neu.label}
          onChange={(e) => setNeu({ ...neu, label: e.target.value })}
        />
        <Button
          disabled={!/^[a-z0-9_]+$/.test(neu.key) || !neu.label || create.isPending}
          onClick={() => create.mutate()}
        >
          Add-on anlegen
        </Button>
      </div>
      <Modal
        open={loeschAddon !== null}
        onClose={() => setLoeschAddon(null)}
        title={`Add-on „${loeschAddon?.label ?? ''}" löschen?`}
      >
        <p className="mb-4 text-sm text-ink-mute">
          Das Feature wird abgeschaltet und die Konfiguration entfernt. Zum bloßen Pausieren
          reicht „Deaktivieren".
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setLoeschAddon(null)}>
            Abbrechen
          </Button>
          <Button
            variant="danger"
            disabled={loeschen.isPending}
            onClick={() => loeschAddon && loeschen.mutate(loeschAddon.id)}
          >
            Löschen
          </Button>
        </div>
      </Modal>
    </Collapsible>
  )
}

const datumKurz = (iso: string) => {
  const [y, m, d] = iso.split('-')
  return `${d}.${m}.${y}`
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
  const [faktorKat, setFaktorKat] = useState<Category | null>(null)
  const [neuFaktor, setNeuFaktor] = useState('')
  const [gueltigAb, setGueltigAb] = useState(() => new Date().toISOString().slice(0, 10))
  const createChange = useMutation({
    mutationFn: () =>
      api.createFactorChange(faktorKat!.id, {
        factor: parseFloat(neuFaktor),
        valid_from: gueltigAb,
      }),
    onSuccess: () => {
      setFaktorKat(null)
      setNeuFaktor('')
      refresh()
    },
    onError: (e) => toast(e.message),
  })
  const deleteChange = useMutation({
    mutationFn: ({ catId, changeId }: { catId: number; changeId: number }) =>
      api.deleteFactorChange(catId, changeId),
    onSuccess: () => {
      setFaktorKat(null)
      refresh()
    },
    onError: (e) => toast(e.message),
  })
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
    <Collapsible title="Kategorien & Faktoren" defaultOpen>
      <div className="space-y-2">
        {categories.map((c) => (
          <div
            key={c.id}
            className={`flex flex-wrap items-center gap-3 border-b border-line/30 py-2 ${
              c.is_active ? '' : 'opacity-40'
            }`}
          >
            <Icon name={c.icon} size={20} className="text-accent" />
            <span className="min-w-24 flex-1 text-sm font-bold text-ink">{c.name}</span>
            <div className="flex min-w-28 flex-col">
              <span className="text-xs font-semibold text-ink-mute">Faktor</span>
              <span className="font-mono tabular-nums text-accent">
                ×{c.factor}
                {c.pending_changes.length > 0 && (
                  <span className="ml-1 text-xs text-ink-mute">
                    → ab {datumKurz(c.pending_changes[0].valid_from)} ×{c.pending_changes[0].factor}
                  </span>
                )}
              </span>
            </div>
            <Button variant="ghost" onClick={() => setFaktorKat(c)}>
              Faktor ändern
            </Button>
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
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-3 border-t border-dashed border-line pt-3">
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
      <Modal
        open={faktorKat !== null}
        onClose={() => setFaktorKat(null)}
        title={`Faktor für ${faktorKat?.name ?? ''} ändern`}
      >
        <p className="mb-3 text-sm text-ink-mute">
          Gilt ab dem Stichtag für Aktivitäten ab diesem Datum — nie rückwirkend. Aktuell: ×
          {faktorKat?.factor}
        </p>
        <div className="flex flex-wrap gap-2">
          <Input
            label="Neuer Faktor"
            type="number"
            step="0.5"
            className="w-24"
            value={neuFaktor}
            onChange={(e) => setNeuFaktor(e.target.value)}
          />
          <Input
            label="Gültig ab"
            type="date"
            value={gueltigAb}
            onChange={(e) => setGueltigAb(e.target.value)}
          />
        </div>
        <Button
          className="mt-3"
          disabled={!(parseFloat(neuFaktor) > 0) || !gueltigAb}
          onClick={() => createChange.mutate()}
        >
          Änderung anlegen
        </Button>
        {(faktorKat?.pending_changes.length ?? 0) > 0 && (
          <div className="mt-4 space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-mute">
              Anstehend
            </p>
            {faktorKat!.pending_changes.map((p) => (
              <div key={p.id} className="flex items-center justify-between text-sm">
                <span>
                  ab {datumKurz(p.valid_from)}: ×{p.factor}
                </span>
                <Button
                  variant="ghost"
                  aria-label={`Änderung ab ${datumKurz(p.valid_from)} löschen`}
                  onClick={() => deleteChange.mutate({ catId: faktorKat!.id, changeId: p.id })}
                >
                  Löschen
                </Button>
              </div>
            ))}
          </div>
        )}
        {(faktorKat?.history.length ?? 0) > 0 && (
          <div className="mt-4 space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-mute">
              Historie
            </p>
            <p className="text-sm text-ink-mute">
              Ur-Faktor: ×{faktorKat!.base_factor}
              {faktorKat!.history.map((h) => (
                <span key={h.id}> · ab {datumKurz(h.valid_from)}: ×{h.factor}</span>
              ))}
            </p>
          </div>
        )}
      </Modal>
    </Collapsible>
  )
}

function StravaMapping() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const patch = useMutation({
    mutationFn: ({ id, types }: { id: number; types: string[] }) =>
      api.patchCategory(id, { strava_sport_types: types }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['categories'] }),
    onError: (e) => toast(e.message),
  })

  const aktuelleKat = (sport: string) =>
    categories.find((c) => c.strava_sport_types.includes(sport))?.id ?? 0

  function zuweisen(sport: string, zielId: number) {
    const alt = categories.find((c) => c.strava_sport_types.includes(sport))
    if (alt && alt.id !== zielId) {
      patch.mutate({ id: alt.id, types: alt.strava_sport_types.filter((s) => s !== sport) })
    }
    if (zielId) {
      const ziel = categories.find((c) => c.id === zielId)
      if (ziel && !ziel.strava_sport_types.includes(sport)) {
        patch.mutate({ id: ziel.id, types: [...ziel.strava_sport_types, sport] })
      }
    }
  }

  if (!categories.length) return null

  return (
    <Collapsible title="Strava-Zuordnung">
      <p className="mb-3 text-xs text-ink-mute">
        Jede Strava-Sportart zählt zu höchstens einer Kategorie. Sportarten ohne
        Distanz (Tennis, Golf, Kraftraum …) lassen sich zuordnen, zählen aber 0 km.
      </p>
      <div>
        {STRAVA_SPORT_TYPES.map((sport) => (
          <div key={sport} className="flex items-center justify-between border-b border-line/30 py-2">
            <span className="font-mono text-sm text-ink">{sport}</span>
            <Select
              label=""
              aria-label={`Zuordnung ${sport}`}
              value={aktuelleKat(sport)}
              onChange={(e) => zuweisen(sport, Number(e.target.value))}
              className="w-44"
            >
              <option value={0}>— ignorieren</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
        ))}
      </div>
    </Collapsible>
  )
}

function Jahr() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const season: Season | undefined = aktiveSeason(seasons)
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['seasons'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const [goal, setGoal] = useState('')
  const [milestones, setMilestones] = useState<Milestone[] | null>(null)
  const [startDatum, setStartDatum] = useState<string | null>(null)
  const [endDatum, setEndDatum] = useState<string | null>(null)
  if (!season) return null
  const ms = milestones ?? season.milestones

  return (
    <Collapsible title={`Saison ${saisonLabel(season)}`}>
      <Input
        label="Ziel (gewertete km)"
        type="number"
        className="w-36"
        defaultValue={season.goal_km}
        onChange={(e) => setGoal(e.target.value)}
      />
      <div className="mt-3 flex flex-wrap gap-3">
        <Input
          label="Saison-Start"
          type="date"
          className="w-40"
          defaultValue={season.start_date ?? ''}
          onChange={(e) => setStartDatum(e.target.value)}
        />
        <Input
          label="Saison-Ende (leer = offen)"
          type="date"
          className="w-40"
          defaultValue={season.end_date ?? ''}
          onChange={(e) => setEndDatum(e.target.value)}
        />
      </div>
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
              .patchSeason(season.id, {
                goal_km: goal ? parseFloat(goal) : undefined,
                milestones: ms,
                ...(startDatum !== null ? { start_date: startDatum || null } : {}),
                ...(endDatum !== null ? { end_date: endDatum || null } : {}),
              })
              .then(refresh)
              .catch((e) => toast(e.message))
          }
        >
          Speichern
        </Button>
      </div>
    </Collapsible>
  )
}

function Mitglieder() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.me })
  const { data: users = [] } = useQuery({ queryKey: ['users'], queryFn: api.listUsers })
  const [loeschUser, setLoeschUser] = useState<AdminUser | null>(null)
  const [resetUser, setResetUser] = useState<AdminUser | null>(null)
  const [resetLink, setResetLink] = useState<ResetLink | null>(null)
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['users'] })
    queryClient.invalidateQueries({ queryKey: ['comparison'] })
  }
  const umschalten = useMutation({
    mutationFn: (u: AdminUser) => api.patchUser(u.id, { is_active: !u.is_active }),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
  const faktor = useMutation({
    mutationFn: ({ id, km_factor }: { id: number; km_factor: number }) =>
      api.patchUser(id, { km_factor }),
    onSuccess: refresh,
    onError: (e) => toast(e.message),
  })
  const loeschen = useMutation({
    mutationFn: (id: number) => api.deleteUser(id),
    onSuccess: () => {
      setLoeschUser(null)
      refresh()
      toast('Account gelöscht', 'ok')
    },
    onError: (e) => toast(e.message),
  })
  const resetErstellen = useMutation({
    mutationFn: (u: AdminUser) => api.createResetLink(u.id),
    onSuccess: (link, u) => {
      setResetUser(u)
      setResetLink(link)
    },
    onError: (e) => toast(e.message),
  })

  // Vollständige URL: das Backend liefert nur einen relativen Pfad,
  // wenn PUBLIC_BASE_URL nicht gesetzt ist (wie bei Einladungen).
  const volleResetUrl = (link: ResetLink) =>
    link.url.startsWith('http') ? link.url : window.location.origin + link.url

  function kopieren(url: string) {
    if (!navigator.clipboard) {
      toast('Kopieren nicht möglich')
      return
    }
    navigator.clipboard
      .writeText(url)
      .then(() => toast('Link kopiert', 'ok'))
      .catch(() => toast('Kopieren fehlgeschlagen'))
  }

  return (
    <Collapsible title="Mitglieder" defaultOpen>
      <ul>
        {users.map((u) => (
          <li
            key={u.id}
            className={`flex items-center gap-3 border-b border-line/30 py-2 text-sm ${
              u.is_active ? '' : 'opacity-40'
            }`}
          >
            <Avatar value={u.avatar} size="sm" />
            <span className="min-w-0 flex-1 truncate">
              <span className="font-bold text-ink">{u.display_name}</span>
              <span className="ml-2 font-mono text-xs text-ink-mute">@{u.username}</span>
            </span>
            {u.is_admin && (
              <span className="rounded-full border border-accent/40 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-accent">
                Admin
              </span>
            )}
            {!u.is_active && (
              <span className="font-mono text-xs uppercase tracking-wider text-ink-tech">
                deaktiviert
              </span>
            )}
            <Input
              label="Faktor"
              type="number"
              step="0.1"
              min="0.1"
              defaultValue={u.km_factor}
              className="w-20"
              onBlur={(e) => {
                const km_factor = parseFloat(e.target.value)
                if (km_factor > 0 && km_factor !== u.km_factor)
                  faktor.mutate({ id: u.id, km_factor })
              }}
            />
            <Button
              variant="ghost"
              disabled={resetErstellen.isPending}
              onClick={() => resetErstellen.mutate(u)}
            >
              Reset-Link
            </Button>
            {u.id !== me?.id && (
              <>
                <Button
                  variant="ghost"
                  disabled={umschalten.isPending}
                  onClick={() => umschalten.mutate(u)}
                >
                  {u.is_active ? 'Deaktivieren' : 'Aktivieren'}
                </Button>
                <button
                  aria-label={`Account ${u.username} löschen`}
                  className="text-ink-mute hover:text-danger"
                  onClick={() => setLoeschUser(u)}
                >
                  <Icon name="papierkorb" size={16} />
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      <Modal
        open={resetLink !== null}
        onClose={() => {
          setResetLink(null)
          setResetUser(null)
        }}
        title={`Passwort-Reset für ${resetUser?.display_name ?? ''}`}
      >
        {resetLink && (
          <div className="space-y-3">
            <p className="text-sm text-danger">
              Achtung: Dieser Link gewährt vollen Zugriff auf das Konto. Gib ihn
              nur direkt an {resetUser?.display_name ?? 'die Person'} weiter.
            </p>
            <p className="text-xs text-ink-mute">
              Einmalig nutzbar, gültig 24 Stunden. Mit dem Setzen eines neuen
              Passworts werden alle offenen Links ungültig.
            </p>
            <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
              <div className="rounded-lg bg-white p-2">
                <QRCodeSVG value={volleResetUrl(resetLink)} size={120} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="mb-1 font-mono text-xs uppercase tracking-wider text-ink-tech">
                  Reset-Link
                </p>
                <p className="break-all text-sm text-ink">{volleResetUrl(resetLink)}</p>
                <Button
                  variant="ghost"
                  className="mt-2"
                  onClick={() => kopieren(volleResetUrl(resetLink))}
                >
                  Link kopieren
                </Button>
              </div>
            </div>
          </div>
        )}
      </Modal>
      <Modal
        open={loeschUser !== null}
        onClose={() => setLoeschUser(null)}
        title={`${loeschUser?.display_name ?? ''} löschen?`}
      >
        <p className="mb-4 text-sm text-ink-mute">
          Der Account und alle seine Aktivitäten werden endgültig gelöscht. Zum
          vorübergehenden Ausschließen reicht „Deaktivieren".
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setLoeschUser(null)}>
            Abbrechen
          </Button>
          <Button
            variant="danger"
            disabled={loeschen.isPending}
            onClick={() => loeschUser && loeschen.mutate(loeschUser.id)}
          >
            Endgültig löschen
          </Button>
        </div>
      </Modal>
    </Collapsible>
  )
}

function Einladungen() {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [displayName, setDisplayName] = useState('')
  const [istAdmin, setIstAdmin] = useState(false)
  const [neu, setNeu] = useState<Invite | null>(null)
  const { data: invites = [] } = useQuery({ queryKey: ['invites'], queryFn: api.listInvites })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['invites'] })

  // Vollständige URL: das Backend liefert ggf. nur einen relativen Pfad,
  // wenn PUBLIC_BASE_URL nicht gesetzt ist.
  const volleUrl = (invite: Invite) =>
    invite.url.startsWith('http') ? invite.url : window.location.origin + invite.url

  const erstellen = useMutation({
    mutationFn: () =>
      api.createInvite({ display_name: displayName || null, is_admin: istAdmin }),
    onSuccess: (invite) => {
      setNeu(invite)
      setDisplayName('')
      setIstAdmin(false)
      refresh()
    },
    onError: (e) => toast(e.message),
  })
  const widerrufen = useMutation({
    mutationFn: (id: number) => api.deleteInvite(id),
    onSuccess: (_data, id) => {
      // Falls die widerrufene Einladung gerade im QR-Panel steht, ausblenden.
      setNeu((aktuell) => (aktuell?.id === id ? null : aktuell))
      refresh()
    },
    onError: (e) => toast(e.message),
  })

  function kopieren(url: string) {
    // navigator.clipboard fehlt auf unsicheren Ursprüngen (HTTP) — nur bei
    // echtem Erfolg den OK-Toast zeigen, sonst Fehlermeldung.
    if (!navigator.clipboard) {
      toast('Kopieren nicht möglich')
      return
    }
    navigator.clipboard
      .writeText(url)
      .then(() => toast('Link kopiert', 'ok'))
      .catch(() => toast('Kopieren fehlgeschlagen'))
  }

  return (
    <Collapsible title="Mitglied einladen">
      <div className="flex flex-wrap items-end gap-2">
        <Input
          label="Anzeigename (optional)"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
        <label className="flex items-center gap-2 pb-2 text-xs font-semibold text-ink-mute">
          <input
            type="checkbox"
            checked={istAdmin}
            onChange={(e) => setIstAdmin(e.target.checked)}
          />
          Admin
        </label>
        <Button onClick={() => erstellen.mutate()} disabled={erstellen.isPending}>
          Einladung erstellen
        </Button>
      </div>

      {neu && (
        <div className="mt-4 flex flex-col items-center gap-3 border border-line p-4 sm:flex-row sm:items-start">
          <div className="rounded-lg bg-white p-2">
            <QRCodeSVG value={volleUrl(neu)} size={120} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="mb-1 font-mono text-xs uppercase tracking-wider text-ink-tech">
              Einladungslink
            </p>
            <p className="break-all text-sm text-ink">{volleUrl(neu)}</p>
            <Button
              variant="ghost"
              className="mt-2"
              onClick={() => kopieren(volleUrl(neu))}
            >
              Link kopieren
            </Button>
          </div>
        </div>
      )}

      {invites.length > 0 && (
        <ul className="mt-4">
          {invites.map((i) => {
            const status = i.used_at
              ? 'genutzt'
              : new Date(i.expires_at) < new Date()
                ? 'abgelaufen'
                : 'offen'
            return (
              <li
                key={i.id}
                className="flex items-center gap-3 border-b border-line/30 py-2 text-sm"
              >
                <span className="flex-1 text-ink">{i.display_name || '—'}</span>
                <span className="font-mono text-xs uppercase tracking-wider text-ink-tech">
                  {status}
                </span>
                <button
                  aria-label="Einladung widerrufen"
                  className="text-ink-mute hover:text-danger"
                  onClick={() => widerrufen.mutate(i.id)}
                >
                  <Icon name="papierkorb" size={16} />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Collapsible>
  )
}
