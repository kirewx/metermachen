import type { Season } from '../../api/client'

// Fensterstart = 1. Januar des Season-Jahres. Ende = end_date; fehlt es:
// mit start_date offen (Jahreswechsel!), ohne start_date 31.12. (Kalenderjahr).
function fensterStart(s: Season): number {
  return Date.parse(`${s.year}-01-01T00:00:00`)
}

function fensterEnde(s: Season): number | null {
  if (s.end_date) return Date.parse(`${s.end_date}T23:59:59`)
  if (s.start_date) return null
  return Date.parse(`${s.year}-12-31T23:59:59`)
}

export function aktiveSeason(seasons: Season[], now = Date.now()): Season | undefined {
  const begonnen = seasons.filter((s) => fensterStart(s) <= now)
  const enthaltend = begonnen.filter((s) => {
    const ende = fensterEnde(s)
    return ende === null || now <= ende
  })
  const spaetesterStart = (a: Season, b: Season) => fensterStart(b) - fensterStart(a)
  if (enthaltend.length > 0) return [...enthaltend].sort(spaetesterStart)[0]
  if (begonnen.length > 0) return [...begonnen].sort(spaetesterStart)[0]
  return [...seasons].sort((a, b) => fensterStart(a) - fensterStart(b))[0]
}

export function saisonLabel(season: Season | undefined): string {
  if (!season) return String(new Date().getFullYear())
  const endJahr = season.end_date ? Number(season.end_date.slice(0, 4)) : season.year
  if (endJahr === season.year) return String(season.year)
  return `Saison ${season.year}/${String(endJahr).slice(2)}`
}
