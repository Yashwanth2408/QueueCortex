import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { request } from '@/lib/api'

interface AuthState {
  status: 'loading' | 'authed' | 'anon'
  email: string | null
}

interface AuthContextValue extends AuthState {
  refresh: () => Promise<void>
  setAuthed: (email: string) => void
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading', email: null })

  const refresh = async () => {
    try {
      const data = await request<{ email: string }>('/auth/me')
      setState({ status: 'authed', email: data.email })
    } catch {
      setState({ status: 'anon', email: null })
    }
  }

  useEffect(() => {
    refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const setAuthed = (email: string) => setState({ status: 'authed', email })

  const logout = async () => {
    try {
      await request('/auth/logout', { method: 'POST' })
    } finally {
      setState({ status: 'anon', email: null })
    }
  }

  return <AuthContext.Provider value={{ ...state, refresh, setAuthed, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
