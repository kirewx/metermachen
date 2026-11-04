import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Suggestion } from '../../api/client'
import Avatar from '../ui/Avatar'
import Button from '../ui/Button'
import Card from '../ui/Card'
import { useToast } from '../ui/Toast'
import { undListe } from '../ui/undListe'
import { invalidateTogether, km, tagKurz, useTogetherAktiv } from './together'

/** Offene Zusammen-Vorschläge und Tags oben im Feed; nichts, wenn keine offen sind. */
export default function SuggestionCards() {
  const aktiv = useTogetherAktiv()
  const { data: vorschlaege = [] } = useQuery({
    queryKey: ['together-suggestions'],
    queryFn: api.togetherSuggestions,
    enabled: aktiv,
  })
  if (!aktiv || vorschlaege.length === 0) return null
  return (
    <div className="space-y-2.5">
      {vorschlaege.map((s) => (
        <VorschlagKarte key={s.participant_id} s={s} />
      ))}
    </div>
  )
}

function VorschlagKarte({ s }: { s: Suggestion }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const [auswahl, setAuswahl] = useState<number | null>(s.candidates[0]?.id ?? null)
  const antwort = useMutation({
    mutationFn: (art: { dabei: true; activityId?: number } | { dabei: false }) =>
      art.dabei
        ? api.togetherConfirm(s.participant_id, art.activityId)
        : api.togetherDecline(s.participant_id),
    onSuccess: () => invalidateTogether(queryClient),
    onError: (e) => toast(e.message),
  })
  const namen = undListe(s.partners.map((p) => p.display_name))
  const erster = s.partners[0]
  const catName = (id: number) => categories.find((c) => c.id === id)?.name ?? 'Aktivität'
  const ablehnen = (
    <Button
      variant="ghost"
      className="min-h-11 flex-1"
      disabled={antwort.isPending}
      onClick={() => antwort.mutate({ dabei: false })}
    >
      War ich nicht dabei
    </Button>
  )

  const kopf = (titel: string, zeile: React.ReactNode) => (
    <div className="flex items-center gap-2.5">
      {erster && <Avatar value={erster.avatar} />}
      <div className="min-w-0">
        <p className="text-[15px] font-bold text-ink">{titel}</p>
        <p className="text-xs text-ink-mute">{zeile}</p>
      </div>
    </div>
  )

  if (s.my_activity) {
    const a = s.my_activity
    return (
      <Card glow className="space-y-3">
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-accent">
          Zusammen unterwegs?
        </p>
        {kopf(
          `Warst du mit ${namen} unterwegs?`,
          <>
            {tagKurz(a.date)} · {catName(a.category_id)}
            {s.km_together > 0 && (
              <>
                {' '}
                · <b className="text-accent">{km(s.km_together)} km</b> gemeinsam
                {s.share != null && ` (${Math.round(s.share * 100)} %)`}
              </>
            )}
          </>,
        )}
        <div className="flex gap-2">
          <Button
            className="min-h-11 flex-1"
            disabled={antwort.isPending}
            onClick={() => antwort.mutate({ dabei: true })}
          >
            Ja, zusammen
          </Button>
          {ablehnen}
        </div>
      </Card>
    )
  }

  const p = s.partner_activity
  return (
    <Card glow className="space-y-3">
      <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-accent">
        Getaggt
      </p>
      {kopf(
        `${namen} ${s.partners.length > 1 ? 'sagen' : 'sagt'}, ihr wart zusammen unterwegs`,
        p && (
          <>
            {tagKurz(p.date)} · {p.category_name}
            {p.duration_min ? ` · ${p.duration_min} min` : ''} · {km(p.distance_km)} km
          </>
        ),
      )}
      <fieldset className="space-y-1.5">
        <legend className="mb-1.5 text-xs font-bold text-ink-mute">Welche Aktivität war das?</legend>
        {s.candidates.map((c) => (
          <label
            key={c.id}
            className={`flex min-h-11 cursor-pointer items-center gap-2.5 rounded-xl border px-3 text-sm ${
              auswahl === c.id ? 'border-accent bg-accent/10' : 'border-line/60'
            }`}
          >
            <input
              type="radio"
              name={`kandidat-${s.participant_id}`}
              checked={auswahl === c.id}
              onChange={() => setAuswahl(c.id)}
              className="accent-[var(--t-accent)]"
            />
            <span className="flex-1 text-ink">
              {tagKurz(c.date)} · {catName(c.category_id)}
            </span>
            <span className="font-mono text-xs text-ink-mute">{km(c.distance_km)} km</span>
          </label>
        ))}
        <Link
          to={`/mymeters?verknuepfen=${s.participant_id}`}
          className="flex min-h-11 items-center justify-center rounded-xl border border-dashed border-accent/60 text-sm font-bold text-accent hover:bg-accent/10"
        >
          ＋ Neu anlegen
        </Link>
      </fieldset>
      <div className="flex gap-2">
        {s.candidates.length > 0 && (
          <Button
            className="min-h-11 flex-1"
            disabled={antwort.isPending || auswahl == null}
            onClick={() => auswahl != null && antwort.mutate({ dabei: true, activityId: auswahl })}
          >
            Verknüpfen
          </Button>
        )}
        {ablehnen}
      </div>
    </Card>
  )
}
