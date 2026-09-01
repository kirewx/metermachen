import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import Collapsible from '../ui/Collapsible'

// Read-only admin overview: the app never teases locked hidden achievements,
// so this is the one place to see what exists and who has it.
export default function HiddenAchievementsAdmin() {
  const { data: hidden = [] } = useQuery({
    queryKey: ['hidden-achievements-admin'],
    queryFn: api.hiddenAchievementsAdmin,
  })
  return (
    <Collapsible title="Versteckte Achievements">
      <ul className="space-y-2">
        {hidden.map((h) => (
          <li key={h.key} className="rounded-xl border border-line/40 p-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{h.emoji}</span>
              <span className="text-sm font-bold text-ink">{h.title}</span>
            </div>
            <p className="mt-1 text-xs text-ink-mute">{h.description}</p>
            <p className="mt-1 text-xs text-ink-soft">
              {h.unlocks.length === 0
                ? 'noch niemand'
                : h.unlocks
                    .map(
                      (u) =>
                        `${u.display_name} · ${new Date(u.unlocked_at).toLocaleDateString('de-DE')}`,
                    )
                    .join(', ')}
            </p>
          </li>
        ))}
      </ul>
    </Collapsible>
  )
}
