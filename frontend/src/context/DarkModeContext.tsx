import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

const KEY = 'queuecortex-theme'

function getInitial(): boolean {
  const stored = localStorage.getItem(KEY)
  if (stored) return stored === 'dark'
  // Dark-first by default (the whole UI is designed around the dark theme);
  // still honor an explicit prior choice above.
  return true
}

interface DarkModeContextValue {
  dark: boolean
  toggle: () => void
}

const DarkModeContext = createContext<DarkModeContextValue | null>(null)

export function DarkModeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(getInitial)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem(KEY, dark ? 'dark' : 'light')
  }, [dark])

  return <DarkModeContext.Provider value={{ dark, toggle: () => setDark((d) => !d) }}>{children}</DarkModeContext.Provider>
}

export function useDarkMode() {
  const ctx = useContext(DarkModeContext)
  if (!ctx) throw new Error('useDarkMode must be used within DarkModeProvider')
  return ctx
}
