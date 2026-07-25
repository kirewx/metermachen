import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { api } from '../api/client'
import type { FeedEvent } from '../api/client'
import FeedItem from '../components/feed/FeedItem'
import { aktiveSeason } from '../components/ui/season'

function tagLabel(iso: string): string {
  const d = new Date(iso)
  const heute = new Date()
  const gestern = new Date(heute)
  gestern.setDate(heute.getDate() - 1)
  const gleicherTag = (a: Date, b: Date) => a.toDateString() === b.toDateString()
  if (gleicherTag(d, heute)) return 'Heute'
  if (gleicherTag(d, gestern)) return 'Gestern'
  const tage = (heute.getTime() - d.getTime()) / 86_400_000
  if (tage < 7) return d.toLocaleDateString('de-DE', { weekday: 'long' })
  return d.toLocaleDateString('de-DE')
}

export default function Feed() {
  const queryClient = useQueryClient()
  const { data: seasons = [] } = useQuery({ queryKey: ['seasons'], queryFn: api.seasons })
  const year = aktiveSeason(seasons)?.year ?? new Date().getFullYear()
  const { data, error, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['feed', year],
    queryFn: ({ pageParam }) => api.feed(year, pageParam ?? undefined),
    initialPageParam: null as number | null,
    getNextPageParam: (last) => last.next_before,
    enabled: seasons.length > 0,
  })
  useEffect(() => {
    api.markFeedSeen().then(() => {
      queryClient.invalidateQueries({ queryKey: ['feed-unseen'] })
    }).catch(() => {})
  }, [queryClient])

  const events: FeedEvent[] = data?.pages.flatMap((p) => p.events) ?? []
  let letzterTag = ''
  if (error) return <p className="text-sm text-danger">{error.message}</p>
  return (
    <div className="mx-auto max-w-xl space-y-2.5">
      {events.map((ev) => {
        const tag = tagLabel(ev.created_at)
        const trenner = tag !== letzterTag
        letzterTag = tag
        return (
          <div key={ev.id} className="space-y-2.5">
            {trenner && (
              <p className="px-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-ink-mute">
                {tag}
              </p>
            )}
            <FeedItem ev={ev} />
          </div>
        )
      })}
      {events.length === 0 && (
        <p className="p-8 text-center text-sm text-ink-mute">
          Noch nichts passiert — trag eine Aktivität ein!
        </p>
      )}
      {hasNextPage && (
        <button
          onClick={() => fetchNextPage()}
          disabled={isFetchingNextPage}
          className="w-full rounded-xl border border-line py-2 text-sm text-ink-mute transition hover:text-ink"
        >
          {isFetchingNextPage ? 'Lädt…' : 'Mehr laden …'}
        </button>
      )}
    </div>
  )
}
