import { useEffect, useState } from 'react'
import { Route, Routes } from 'react-router-dom'
import { TopBar } from '@/components/layout/TopBar'
import { Preloader } from '@/components/layout/Preloader'
import { Dashboard } from '@/pages/Dashboard'
import { Analytics } from '@/pages/Analytics'
import { Settings } from '@/pages/Settings'
import { ShiftWatch } from '@/pages/ShiftWatch'
import { Login } from '@/pages/Login'
import { useAuth } from '@/context/AuthContext'

// Held for a minimum visible duration so the branded preloader genuinely
// shows on every tab open/reload, not just a few-ms flash when auth
// resolves instantly from an already-valid session cookie.
const MIN_PRELOADER_MS = 900

function App() {
  const { status } = useAuth()
  const [minTimeElapsed, setMinTimeElapsed] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setMinTimeElapsed(true), MIN_PRELOADER_MS)
    return () => clearTimeout(t)
  }, [])

  if (status === 'loading' || !minTimeElapsed) {
    return <Preloader />
  }

  if (status === 'anon') {
    return <Login />
  }

  return (
    <div className="min-h-screen bg-background">
      <TopBar />
      <main className="mx-auto max-w-7xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/shift-watch" element={<ShiftWatch />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
