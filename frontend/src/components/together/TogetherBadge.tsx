import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, type TogetherInfo, type TogetherPartner } from '../../api/client'
import Avatar from '../ui/Avatar'
import Button from '../ui/Button'
import { useToast } from '../ui/Toast'
import { undListe } from '../ui/undListe'
import { invalidateTogether, km } from './together'

type Eintrag = { partner: TogetherPartner; offen: boolean }

function eintraege(together: TogetherInfo, own: boolean): Eintrag[] {
  return [
    ...together.partners.map((partner) => ({ partner, offen: false })),
    ...(own ? (together.pending ?? []) : []).map((partner) => ({ partner, offen: true })),
  ]
}

type StapelProps = {
  together: TogetherInfo
  own: boolean
  offen: boolean
  onToggle: () => void
}

/** Avatar-Stapel am Ende einer Aktivitätszeile; Tippen klappt das Panel auf. */
export function TogetherStapel({ together, own, offen, onToggle }: StapelProps) {
  const liste = eintraege(together, own)
  const abgelehnt = together.status === 'declined'
  const namen = undListe(liste.map((e) => e.partner.display_name))
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={offen}
      aria-label={abgelehnt ? `Nicht dabei: ${namen}` : `Zusammen mit ${namen}`}
      className={`flex min-h-11 shrink-0 items-center px-1 ${abgelehnt ? 'opacity-40 grayscale' : ''}`}
    >
      {liste.slice(0, 3).map((e, i) => (
        <span
          key={e.partner.user_id}
          className={`rounded-full ring-2 ring-card ${i > 0 ? '-ml-2' : ''} ${
            e.offen ? 'opacity-60 outline-1 outline-dashed outline-accent' : ''
          }`}
        >
          <Avatar value={e.partner.avatar} size="sm" />
        </span>
      ))}
      {liste.length > 3 && (
        <span className="ml-1 text-[11px] font-bold text-ink-mute">+{liste.length - 3}</span>
      )}
    </button>
  )
}

/** Aufgeklapptes Badge: Partner, gemeinsame km und — bei der eigenen
 * Aktivität — Bestätigen, „War ich nicht dabei“ oder „Doch dabei“. */
export function TogetherPanel({ together, own }: { together: TogetherInfo; own: boolean }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const antwort = useMutation({
    mutationFn: (dabei: boolean) =>
      dabei
        ? api.togetherConfirm(together.participant_id)
        : api.togetherDecline(together.participant_id),
    onSuccess: () => invalidateTogether(queryClient),
    onError: (e) => toast(e.message),
  })
  const abgelehnt = together.status === 'declined'

  return (
    <div
      className={`mb-2 space-y-2 rounded-xl border p-3 text-sm ${
        abgelehnt ? 'border-line' : 'border-accent/60 bg-accent/5 shadow-glow'
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <b className="text-ink">{abgelehnt ? 'Ohne dich unterwegs' : 'Zusammen unterwegs'}</b>
        {together.km_together > 0 && (
          <span className="font-mono text-xs text-accent">
            {km(together.km_together)} km gemeinsam
          </span>
        )}
      </div>
      <ul className="space-y-1">
        {eintraege(together, own).map((e) => (
          <li key={e.partner.user_id} className="flex items-center gap-2">
            <Avatar value={e.partner.avatar} size="sm" />
            <span className="flex-1 text-ink">{e.partner.display_name}</span>
            <span
              className={`text-[11px] font-bold ${e.offen ? 'text-ink-mute' : 'text-accent'}`}
            >
              {e.offen ? 'offen' : 'bestätigt'}
            </span>
          </li>
        ))}
      </ul>
      {own && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          {abgelehnt && (
            <span className="mr-auto text-xs text-ink-mute">
              Du hast „nicht dabei“ gesagt.
            </span>
          )}
          {together.status === 'suggested' || abgelehnt ? (
            <Button disabled={antwort.isPending} onClick={() => antwort.mutate(true)}>
              {abgelehnt ? 'Doch dabei' : 'Bestätigen'}
            </Button>
          ) : null}
          {!abgelehnt && (
            <Button
              variant="ghost"
              disabled={antwort.isPending}
              onClick={() => antwort.mutate(false)}
            >
              War ich nicht dabei
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
