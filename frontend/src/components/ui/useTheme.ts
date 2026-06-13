import { useEffect, useState } from 'react'

export type Theme = 'dunkel' | 'hell'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    localStorage.getItem('theme') === 'hell' ? 'hell' : 'dunkel',
  )
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dunkel')
    localStorage.setItem('theme', theme)
  }, [theme])
  return { theme, toggle: () => setTheme((t) => (t === 'dunkel' ? 'hell' : 'dunkel')) }
}
