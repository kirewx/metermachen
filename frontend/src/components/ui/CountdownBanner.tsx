import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { challengeStartMs, formatCountdown } from './countdown'
import { aktiveSeason } from './season'

export default function CountdownBanner() {
  const { data: seasons } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const season = aktiveSeason(seasons ?? [])
  if (!season?.start_date) return null
  const label = formatCountdown(challengeStartMs(season.start_date) - now)
  if (!label) return null
  return (
    <div className="border-b border-accent/30 bg-card/60 px-4 py-1.5 text-center text-sm">
      <span className="text-ink-mute">Testphase — Challenge startet in </span>
      <span className="font-mono font-bold tabular-nums text-accent [text-shadow:var(--t-glow)]">
        {label}
      </span>
    </div>
  )
}
