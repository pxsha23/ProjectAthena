import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { readStorage, writeStorage } from './utils'

export type ThemeId = 'black' | 'mocha'

export const THEMES: { id: ThemeId; label: string; description: string }[] = [
  { id: 'black', label: 'Black', description: 'Default. True black with pastel accents.' },
  { id: 'mocha', label: 'Mocha', description: 'Soft navy, Catppuccin Mocha.' },
]

export const DEFAULT_THEME: ThemeId = 'black'
const STORAGE_KEY = 'athena.theme'

function isTheme(value: unknown): value is ThemeId {
  return THEMES.some((t) => t.id === value)
}

/** Writes the theme onto <html> right away, so anything reading CSS variables sees the new values. */
function applyTheme(theme: ThemeId) {
  document.documentElement.dataset.theme = theme
  const meta = document.querySelector('meta[name="theme-color"]')
  const base = getComputedStyle(document.documentElement).getPropertyValue('--c-base').trim()
  if (meta && base) meta.setAttribute('content', base)
}

interface ThemeContextValue {
  theme: ThemeId
  setTheme: (theme: ThemeId) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(() => {
    const stored = readStorage<unknown>(STORAGE_KEY, DEFAULT_THEME)
    const initial = isTheme(stored) ? stored : DEFAULT_THEME
    applyTheme(initial)
    return initial
  })

  const setTheme = useCallback((next: ThemeId) => {
    applyTheme(next)
    writeStorage(STORAGE_KEY, next)
    setThemeState(next)
  }, [])

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}
