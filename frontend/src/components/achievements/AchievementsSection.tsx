import type { Achievement } from '../../api/client'
import AchievementBadge from './AchievementBadge'
import { TIER_ORDER } from './constants'
import HiddenCard from './HiddenCard'
import LadderCard from './LadderCard'
import OneTimeCard from './OneTimeCard'
import TierCard from './TierCard'
import TimeAtTopCard from './TimeAtTopCard'

type Props = {
  achievements: Achievement[]
  // Present on the own profile only; without it no showcase toggles render.
  onToggle?: (a: Achievement) => void
}

// The trophy grid. Purely presentational: whoever renders it decides whose
// achievements these are and whether they may be toggled.
export default function AchievementsSection({ achievements, onToggle }: Props) {
  if (achievements.length === 0)
    return <p className="text-sm text-ink-mute">Noch keine Achievements.</p>

  const tiers = achievements.filter((a) => a.tier !== null)
  const disciplines = [...new Set(tiers.map((a) => a.discipline))] as string[]
  const ladderStages = achievements.filter((a) => a.ladder)
  const ladders = [...new Set(ladderStages.map((a) => a.ladder))] as string[]
  const rest = achievements.filter((a) => !a.ladder)
  const oneTime = rest.filter((a) => a.emoji !== null && !a.hidden && a.tier === null)
  const hidden = rest.filter((a) => a.hidden && a.achieved)
  const timeAtTop = rest.find((a) => a.key === 'zeit_an_der_spitze')
  const classic = rest.filter(
    (a) => a.tier === null && !a.hidden && a.emoji === null && a.key !== 'zeit_an_der_spitze',
  )

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {classic.map((a) => (
        <AchievementBadge key={a.key} a={a} />
      ))}
      {timeAtTop && <TimeAtTopCard a={timeAtTop} />}
      {disciplines.map((d) => (
        <TierCard
          key={d}
          tiers={TIER_ORDER.map((t) => tiers.find((s) => s.discipline === d && s.tier === t)).filter(
            (s): s is Achievement => Boolean(s),
          )}
        />
      ))}
      {ladders.map((l) => (
        <LadderCard
          key={l}
          stages={ladderStages.filter((a) => a.ladder === l)}
          onToggle={onToggle}
        />
      ))}
      {oneTime.map((a) => (
        <OneTimeCard key={a.key} a={a} onToggle={onToggle} />
      ))}
      {hidden.map((a) => (
        <HiddenCard key={a.key} a={a} onToggle={onToggle} />
      ))}
    </div>
  )
}
