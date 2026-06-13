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
  map_image: string | null
}
export type Activity = {
  id: number
  category_id: number
  date: string
  distance_km: number
  duration_min: number | null
  note: string | null
  scaled_km: number
  edited: boolean
  source: string
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
  by_category: CategoryShare[]
  segments: Segment[]
  cumulative: { date: string; scaled_km: number }[]
}
export type Comparison = {
  year: number
  goal_km: number
  milestones: Milestone[]
  map_image: string | null
  users: ComparisonUser[]
}
export type StravaStatus = {
  enabled: boolean
  connected: boolean
  athlete_id?: number | null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!r.ok) {
    const detail = (await r.json().catch(() => null))?.detail
    throw new Error(typeof detail === 'string' ? detail : `Fehler ${r.status}`)
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
  uploadMapImage: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Season>(`/api/seasons/${id}/map-image`, { method: 'POST', body: form })
  },
  activities: (year: number) => request<Activity[]>(`/api/activities?year=${year}`),
  createActivity: (b: ActivityInput) => request<Activity>('/api/activities', post(b)),
  patchActivity: (id: number, b: Partial<ActivityInput>) =>
    request<Activity>(`/api/activities/${id}`, patch(b)),
  deleteActivity: (id: number) => request<void>(`/api/activities/${id}`, { method: 'DELETE' }),
  createUser: (b: { username: string; password: string; display_name: string; avatar?: string }) =>
    request<Me>('/api/users', post(b)),
  patchMe: (b: { display_name?: string; avatar?: string; password?: string }) =>
    request<Me>('/api/users/me', patch(b)),
  comparison: (year: number) => request<Comparison>(`/api/comparison/${year}`),
  stravaStatus: () => request<StravaStatus>('/api/strava/status'),
  disconnectStrava: () => request<void>('/api/strava/disconnect', { method: 'DELETE' }),
}
