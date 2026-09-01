import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Achievement } from '../../api/client'
import AchievementsSection from './AchievementsSection'

type Props = { userId: number; own: boolean }

// Own profile: full list with progress and showcase toggles.
// Someone else's: only what they unlocked, read-only.
export default function ProfileAchievements({ userId, own }: Props) {
  const queryClient = useQueryClient()
  const { data: achievements = [], isLoading } = useQuery({
    queryKey: own ? ['achievements'] : ['user-achievements', userId],
    queryFn: () => (own ? api.achievements() : api.userAchievements(userId)),
  })
  const toggle = useMutation({
    mutationFn: ({ key, showcased }: { key: string; showcased: boolean }) =>
      api.patchAchievement(key, showcased),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['achievements'] })
      queryClient.invalidateQueries({ queryKey: ['comparison'] })
    },
  })
  if (isLoading) return <p className="text-sm text-ink-mute">Lädt…</p>
  const onToggle = own
    ? (a: Achievement) => toggle.mutate({ key: a.key, showcased: !(a.showcased ?? true) })
    : undefined
  return <AchievementsSection achievements={achievements} onToggle={onToggle} />
}
