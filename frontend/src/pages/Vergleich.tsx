import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import JahresVerlauf from '../components/comparison/JahresVerlauf'
import RaceBahnen from '../components/comparison/RaceBahnen'
import WanderKarte from '../components/comparison/WanderKarte'

const TABS = ['Wanderkarte', 'Race-Bahnen', 'Jahresverlauf'] as const

export default function Vergleich() {
  const [tab, setTab] = useState<(typeof TABS)[number]>('Wanderkarte')
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const [year, setYear] = useState(new Date().getFullYear())
  const { data, error } = useQuery({
    queryKey: ['comparison', year],
    queryFn: () => api.comparison(year),
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1 text-sm ${
              tab === t ? 'bg-emerald-600 text-white' : 'bg-white shadow'
            }`}
          >
            {t}
          </button>
        ))}
        <select
          className="ml-auto rounded border bg-white p-1 text-sm"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {seasons.map((s) => (
            <option key={s.id} value={s.year}>{s.year}</option>
          ))}
        </select>
      </div>
      {error && <p className="text-red-600">{error.message}</p>}
      {data && tab === 'Wanderkarte' && <WanderKarte data={data} />}
      {data && tab === 'Race-Bahnen' && <RaceBahnen data={data} />}
      {data && tab === 'Jahresverlauf' && <JahresVerlauf data={data} />}
    </div>
  )
}
