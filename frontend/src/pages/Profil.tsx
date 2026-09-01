import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import ProfileAchievements from '../components/achievements/ProfileAchievements'
import { formatHm } from '../components/comparison/monatsFarbe'
import AktivitaetenListe from '../components/profile/AktivitaetenListe'
import SettingsSection from '../components/profile/SettingsSection'
import { profilAchsen } from '../components/profile/achsen'
import Spinnennetz from '../components/profile/Spinnennetz'
import { bestimmeTyp } from '../components/profile/typ'
import AuszeichnungsBadges from '../components/ui/AuszeichnungsBadges'
import Avatar from '../components/ui/Avatar'
import Card from '../components/ui/Card'
import SectionTitle from '../components/ui/SectionTitle'
import Select from '../components/ui/Select'
import StatValue from '../components/ui/StatValue'
import { aktiveSeason, saisonLabel } from '../components/ui/season'

/**
 * Profilseite eines Mitglieds: wer ist das für ein Sportler-Typ, wie sieht das
 * Spinnennetz über die fünf Achsen aus — und wie stehe ich selbst dagegen.
 */
export default function Profil() {
  const { userId } = useParams()
  const id = Number(userId)
  const [params, setParams] = useSearchParams()
  const [vergleichAn, setVergleichAn] = useState(true)

  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const aktive = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const jahrParam = Number(params.get('jahr'))
  const year = Number.isInteger(jahrParam) && jahrParam > 0 ? jahrParam : aktive

  const { data: me } = useQuery({ queryKey: ['me'], queryFn: api.me })
  const { data, error } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
  })
  const { data: activities = [] } = useQuery({
    queryKey: ['user-activities', id, year],
    queryFn: () => api.userActivities(id, year),
    enabled: Number.isFinite(id),
  })

  const zurueck = (
    <Link to="/" className="text-xs font-bold text-accent hover:underline">
      ← Vergleich
    </Link>
  )

  if (error) return <p className="text-sm text-danger">{error.message}</p>
  if (!data) return <p className="text-sm text-ink-mute">Lädt…</p>

  const user = data.users.find((u) => u.user_id === id)
  if (!user)
    return (
      <div className="space-y-3">
        {zurueck}
        <p className="text-sm text-ink-mute">Dieses Mitglied gibt es (in dieser Saison) nicht.</p>
      </div>
    )

  const achsen = profilAchsen(user, data.users)
  const spezialId = achsen.find((a) => a.key === 'spezial')?.category_id ?? null
  const typ = bestimmeTyp(user, data.users, achsen)
  const ich = me && me.id !== user.user_id ? data.users.find((u) => u.user_id === me.id) : null
  const vergleich =
    ich && vergleichAn
      ? { name: ich.display_name, achsen: profilAchsen(ich, data.users, spezialId) }
      : null

  const laengste = activities.reduce((m, a) => Math.max(m, a.scaled_km), 0)
  const schnitt = activities.length > 0 ? user.total_scaled_km / activities.length : 0
  const sportarten = [...user.by_category].sort((a, b) => b.scaled_km - a.scaled_km)
  const maxKategorie = sportarten[0]?.scaled_km ?? 0

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        {zurueck}
        <Select
          label="Saison"
          value={year}
          onChange={(e) => {
            params.set('jahr', e.target.value)
            setParams(params, { replace: true })
          }}
          className="ml-auto w-24"
        >
          {[...seasons].sort((a, b) => b.year - a.year).map((s) => (
            <option key={s.id} value={s.year}>
              {saisonLabel(s)}
            </option>
          ))}
        </Select>
      </div>

      <Card glow className="space-y-4">
        <div className="flex items-start gap-3">
          <Avatar value={user.avatar} size="lg" />
          <div className="min-w-0">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.25em] text-ink-tech">
              Platz {user.rank} · Saison {year}
            </p>
            <h1 className="truncate text-xl font-black text-ink">
              {user.display_name}
              <AuszeichnungsBadges liste={user.auszeichnungen ?? []} />
            </h1>
            <p className="text-lg font-black tracking-wide text-accent [text-shadow:var(--t-glow)]">
              {typ.emoji} {typ.label.toUpperCase()}
            </p>
            <p className="text-sm text-ink-soft">{typ.satz}</p>
          </div>
        </div>

        <div>
          <SectionTitle>Sportprofil</SectionTitle>
          {ich && (
            <button
              type="button"
              aria-pressed={vergleichAn}
              onClick={() => setVergleichAn((v) => !v)}
              className={`mb-1 rounded-full border px-2.5 py-1 text-xs font-bold transition ${
                vergleichAn ? 'border-accent text-accent' : 'border-line text-ink-mute hover:text-ink'
              }`}
            >
              {vergleichAn ? '✓ ' : ''}Mit mir vergleichen
            </button>
          )}
          <Spinnennetz name={user.display_name} achsen={achsen} vergleich={vergleich} />
          <p className="mt-1 text-[11px] text-ink-mute">
            Außenring = Bestwert der Gruppe auf dieser Achse.
            {vergleich ? ` Gestrichelt: ${vergleich.name}.` : ''}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatValue label="Gewertet" value={`${Math.round(user.total_scaled_km)} MM`} glow />
          <StatValue label="Echte km" value={`${Math.round(user.total_real_km)}`} />
          <StatValue label="Höhe" value={`${formatHm(user.total_elevation_m)} m`} />
          <StatValue label="Einträge" value={`${activities.length}`} />
        </div>
        <p className="text-xs text-ink-mute">
          Ø{' '}
          {schnitt.toLocaleString('de-DE', {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1,
          })}{' '}
          MM je Eintrag · längste Aktivität {Math.round(laengste)} MM
        </p>
      </Card>

      <Card>
        <SectionTitle>Sportarten</SectionTitle>
        <div className="space-y-2">
          {sportarten.map((c) => (
            <div key={c.category_id}>
              <div className="flex justify-between text-xs">
                <span className="text-ink-soft">{c.name}</span>
                <span className="font-mono tabular-nums text-ink-mute">
                  {Math.round(c.scaled_km)} MM
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface">
                <span
                  className="balken-wachsen block h-full"
                  style={{
                    width: `${maxKategorie > 0 ? (c.scaled_km / maxKategorie) * 100 : 0}%`,
                    background: c.color,
                  }}
                />
              </div>
            </div>
          ))}
          {sportarten.length === 0 && (
            <p className="text-sm text-ink-mute">Noch keine Aktivitäten in dieser Saison.</p>
          )}
        </div>
      </Card>

      <Card>
        <SectionTitle>Achievements</SectionTitle>
        <ProfileAchievements userId={user.user_id} own={me?.id === user.user_id} />
      </Card>

      <Card>
        <SectionTitle>Letzte Aktivitäten</SectionTitle>
        <AktivitaetenListe userId={id} year={year} />
      </Card>

      {me && me.id === user.user_id && <SettingsSection me={me} />}
    </div>
  )
}
