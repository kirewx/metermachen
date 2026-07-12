// Challenge startet um Mitternacht deutscher Zeit. Im Juli gilt CEST (+02:00);
// der feste Offset reicht, solange der Stichtag im Sommer liegt.
export function challengeStartMs(startDate: string): number {
  return Date.parse(`${startDate}T00:00:00+02:00`)
}

export function formatCountdown(msLeft: number): string | null {
  if (msLeft <= 0) return null
  const s = Math.floor(msLeft / 1000)
  const days = Math.floor(s / 86400)
  const hh = String(Math.floor((s % 86400) / 3600)).padStart(2, '0')
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0')
  const ss = String(s % 60).padStart(2, '0')
  return `${days} T ${hh}:${mm}:${ss}`
}

export function challengeLaeuft(startDate: string | null | undefined, now = Date.now()): boolean {
  if (!startDate) return true // ohne Stichtag gibt es keine Testphase
  return now >= challengeStartMs(startDate)
}
