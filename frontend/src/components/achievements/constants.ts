export const TIER_ORDER = ['bronze', 'silber', 'gold'] as const
export const TIER_LABEL = { bronze: 'Bronze', silber: 'Silber', gold: 'Gold' } as const
// Personal specials without a race: the "only the first person" hint is wrong here.
export const NO_RACE_KEYS = new Set([
  'fruehstarter',
  'early_bird',
  'together_first',
  'together_dream_team',
  'together_pack',
  'together_social_butterfly',
])
