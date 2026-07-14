export type Me = {
  id: number
  username: string
  display_name: string
  avatar: string
  is_admin: boolean
}
export type Category = {
  id: number
  name: string
  factor: number
  color: string
  icon: string
  default_km: number
  is_active: boolean
  strava_sport_types: string[]
}
export type Milestone = { km: number; label: string; icon: string }
export type Season = {
  id: number
  year: number
  goal_km: number
  milestones: Milestone[]
  start_date: string | null
}
export type Activity = {
  id: number
  category_id: number
  date: string
  distance_km: number
  duration_min: number | null
  elevation_m: number | null
  note: string | null
  scaled_km: number
  edited: boolean
  source: string
  strava_url: string | null
}
export type ActivityInput = {
  category_id: number
  date: string
  distance_km: number
  duration_min?: number | null
  note?: string | null
}
export type CategoryShare = {
  category_id: number
  name: string
  color: string
  icon: string
  scaled_km: number
}
export type Segment = { date: string; category_id: number; color: string; scaled_km: number }
export type ComparisonUser = {
  user_id: number
  display_name: string
  avatar: string
  rank: number
  total_scaled_km: number
  km_factor: number
  by_category: CategoryShare[]
  segments: Segment[]
  cumulative: { date: string; scaled_km: number }[]
}
export type Comparison = {
  year: number
  goal_km: number
  milestones: Milestone[]
  users: ComparisonUser[]
  start_date: string | null
  phase: string
}
export type WarmupWinner = {
  user_id: number
  display_name: string
  avatar: string
  km: number
}
export type WarmupAchievement = {
  key: string
  title: string
  icon: string
  winners: WarmupWinner[]
}
export type WarmupOut = {
  final: boolean
  start_date: string | null
  achievements: WarmupAchievement[]
}
export type StravaBackfill = {
  state: 'idle' | 'running' | 'done' | 'error'
  total: number
  done: number
}
export type StravaStatus = {
  enabled: boolean
  connected: boolean
  consent?: boolean
  athlete_id?: number | null
  backfill?: StravaBackfill
}
export type AdminUser = {
  id: number
  username: string
  display_name: string
  avatar: string
  is_admin: boolean
  is_active: boolean
  km_factor: number
  created_at: string
}
export type AddOn = {
  id: number
  key: string
  label: string
  description: string
  enabled: boolean
  active_from: string | null
  active_until: string | null
  active: boolean
}
export type AchievementPart = { label: string; current_km: number; target_km: number }
export type Achievement = {
  key: string
  title: string
  description: string
  icon: string
  achieved: boolean
  progress: number
  parts: AchievementPart[]
}
export type Invite = {
  id: number
  token: string
  url: string
  display_name: string | null
  is_admin: boolean
  expires_at: string
  used_at: string | null
}
export type InvitePublic = {
  valid: boolean
  display_name?: string | null
  expired?: boolean
  used?: boolean
}

export type BetParticipant = {
  user_id: number
  display_name: string
  avatar: string
  role: string
  stake: number
  payout: number | null
  choice: { tipp_user_id?: number }
}
export type BetParams = {
  opponent_id?: number
  vorsprung_km?: number
  factor_creator?: number
  factor_opponent?: number
  target_km?: number
  streak_days?: number
  side?: 'ueber' | 'unter'
  month?: string
}
export type Bet = {
  id: number
  type: 'duell' | 'monats_tipp' | 'ziel' | 'streak' | 'ueber_unter'
  creator_id: number
  title: string
  stake: number
  period_start: string
  period_end: string
  status: 'offen' | 'laufend' | 'entschieden' | 'abgelehnt' | 'abgebrochen'
  jackpot: number
  created_at: string
  resolved_at: string | null
  params: BetParams
  result: {
    winner_ids?: number[]
    david?: boolean
    creator_value?: number
    opponent_value?: number
    ist?: number
    erreicht?: boolean
    gruppen_km?: number
    gewonnen?: string
    monats_sieger?: number[]
    pot?: number
    grund?: string
  }
  participants: BetParticipant[]
  standing: {
    creator_km?: number
    opponent_km?: number
    km?: number
    streak?: number
    gruppen_km?: number
    fuehrender_user_id?: number | null
  }
  my_role: string | null
}
export type BetCreateInput = {
  type: Bet['type']
  title: string
  stake: number
  period_start: string
  period_end: string
  params: BetParams
}
export type PointTransaction = {
  amount: number
  reason: string
  bet_id: number | null
  created_at: string
}
export type PointsInfo = { balance: number; transactions: PointTransaction[] }
export type PointsRankingEntry = {
  user_id: number
  display_name: string
  avatar: string
  balance: number
  rank: number
}
export type BetAchievement = {
  key: string
  title: string
  description: string
  icon: string
  achieved: boolean
  progress: number
}

/** Fehler mit HTTP-Status, damit Aufrufer 401 (Session weg) von Netz-/Serverfehlern trennen können. */
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!r.ok) {
    const detail = (await r.json().catch(() => null))?.detail
    throw new ApiError(r.status, typeof detail === 'string' ? detail : `Fehler ${r.status}`)
  }
  return r.status === 204 ? (undefined as T) : r.json()
}

const post = (body: unknown) => ({ method: 'POST', body: JSON.stringify(body) })
const patch = (body: unknown) => ({ method: 'PATCH', body: JSON.stringify(body) })

export const api = {
  login: (username: string, password: string) =>
    request<Me>('/api/auth/login', post({ username, password })),
  logout: () => request<unknown>('/api/auth/logout', { method: 'POST' }),
  me: () => request<Me>('/api/auth/me'),
  categories: () => request<Category[]>('/api/categories'),
  createCategory: (b: Omit<Category, 'id' | 'is_active'>) =>
    request<Category>('/api/categories', post(b)),
  patchCategory: (id: number, b: Partial<Omit<Category, 'id'>>) =>
    request<Category>(`/api/categories/${id}`, patch(b)),
  seasons: () => request<Season[]>('/api/seasons'),
  createSeason: (b: { year: number; goal_km: number; milestones?: Milestone[] }) =>
    request<Season>('/api/seasons', post(b)),
  patchSeason: (id: number, b: { goal_km?: number; milestones?: Milestone[] }) =>
    request<Season>(`/api/seasons/${id}`, patch(b)),
  activities: (year: number) => request<Activity[]>(`/api/activities?year=${year}`),
  createActivity: (b: ActivityInput) => request<Activity>('/api/activities', post(b)),
  patchActivity: (id: number, b: Partial<ActivityInput>) =>
    request<Activity>(`/api/activities/${id}`, patch(b)),
  deleteActivity: (id: number) => request<void>(`/api/activities/${id}`, { method: 'DELETE' }),
  createUser: (b: { username: string; password: string; display_name: string; avatar?: string }) =>
    request<Me>('/api/users', post(b)),
  patchMe: (b: { username?: string; display_name?: string; avatar?: string; password?: string }) =>
    request<Me>('/api/users/me', patch(b)),
  listUsers: () => request<AdminUser[]>('/api/users'),
  userActivities: (userId: number, year: number) =>
    request<Activity[]>(`/api/users/${userId}/activities?year=${year}`),
  patchUser: (id: number, b: { is_active?: boolean; km_factor?: number }) =>
    request<AdminUser>(`/api/users/${id}`, patch(b)),
  deleteUser: (id: number) => request<void>(`/api/users/${id}`, { method: 'DELETE' }),
  addons: () => request<AddOn[]>('/api/addons'),
  createAddon: (b: {
    key: string
    label: string
    description?: string
    enabled?: boolean
    active_from?: string | null
    active_until?: string | null
  }) => request<AddOn>('/api/addons', post(b)),
  patchAddon: (
    id: number,
    b: Partial<{
      label: string
      description: string
      enabled: boolean
      active_from: string | null
      active_until: string | null
    }>,
  ) => request<AddOn>(`/api/addons/${id}`, patch(b)),
  deleteAddon: (id: number) => request<void>(`/api/addons/${id}`, { method: 'DELETE' }),
  achievements: () => request<Achievement[]>('/api/achievements'),
  comparison: (year: number) => request<Comparison>(`/api/comparison/${year}`),
  comparisonWarmup: (year: number) =>
    request<Comparison>(`/api/comparison/${year}?phase=warmup`),
  warmupAchievements: () => request<WarmupOut>('/api/achievements/warmup'),
  stravaStatus: () => request<StravaStatus>('/api/strava/status'),
  consentStrava: () => request<void>('/api/strava/consent', { method: 'POST' }),
  disconnectStrava: () => request<void>('/api/strava/disconnect', { method: 'DELETE' }),
  createInvite: (b: { display_name?: string | null; is_admin?: boolean }) =>
    request<Invite>('/api/invites', post(b)),
  listInvites: () => request<Invite[]>('/api/invites'),
  deleteInvite: (id: number) => request<void>(`/api/invites/${id}`, { method: 'DELETE' }),
  getInvite: (token: string) => request<InvitePublic>(`/api/invites/${token}`),
  acceptInvite: (
    token: string,
    b: { username: string; password: string; display_name: string; avatar: string },
  ) => request<Me>(`/api/invites/${token}/accept`, post(b)),
  bets: () => request<Bet[]>('/api/bets'),
  createBet: (b: BetCreateInput) => request<Bet>('/api/bets', post(b)),
  respondBet: (
    id: number,
    b: { action: string; stake?: number; choice?: { tipp_user_id?: number } },
  ) => request<Bet>(`/api/bets/${id}/respond`, post(b)),
  cancelBet: (id: number) => request<Bet>(`/api/bets/${id}/cancel`, { method: 'POST' }),
  points: () => request<PointsInfo>('/api/points'),
  pointsRanking: () => request<PointsRankingEntry[]>('/api/points/ranking'),
  betAchievements: () => request<BetAchievement[]>('/api/bets/achievements'),
}
