import { useEffect, useRef, useState } from 'react'
import { LogOut, Moon, RefreshCw, Sun } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useToast } from '@/components/ui/toast'
import { useAuth } from '@/context/AuthContext'
import { useDarkMode } from '@/context/DarkModeContext'
import { useSyncRun, useSyncStatus, useTriggerSync } from '@/hooks/useSync'
import { relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { APP_VERSION } from '@/lib/version'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings', label: 'Settings' },
]

function SegmentedNav() {
  return (
    <nav className="inline-flex h-9 w-fit items-center justify-center rounded-full bg-secondary p-0.75">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={({ isActive }) =>
            cn(
              'inline-flex items-center justify-center rounded-full px-3.5 py-1 text-sm font-medium whitespace-nowrap transition-all duration-150',
              isActive ? 'bg-card text-foreground shadow-[0_1px_3px_rgba(0,0,0,0.12)]' : 'text-muted-foreground hover:text-foreground',
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function TopBar() {
  const { dark, toggle } = useDarkMode()
  const { data: status } = useSyncStatus()
  const triggerSync = useTriggerSync()
  const { email, logout } = useAuth()
  const toast = useToast()

  const [watchedRunId, setWatchedRunId] = useState<number | null>(null)
  const { data: run } = useSyncRun(watchedRunId)
  const notifiedRef = useRef<number | null>(null)

  useEffect(() => {
    if (!run || run.status === 'running' || notifiedRef.current === run.id) return
    notifiedRef.current = run.id
    if (run.status === 'success') {
      toast({
        title: 'Sync complete',
        description: run.events_ingested > 0 ? `${run.events_ingested} new event${run.events_ingested === 1 ? '' : 's'}` : 'Already up to date',
        variant: 'success',
      })
    } else {
      toast({ title: 'Sync failed', description: run.error_summary ?? undefined, variant: 'error' })
    }
    setWatchedRunId(null)
  }, [run, toast])

  const isRunning = status?.is_running ?? false
  const lastSync = status?.last_incremental_sync_at ?? status?.last_full_backfill_at ?? null
  const initial = (email ?? '?').charAt(0).toUpperCase()

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/72 backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex size-6 items-center justify-center rounded-lg bg-foreground text-[13px] font-bold text-background">Q</div>
          <span className="text-[15px] font-semibold tracking-tight">QueueCortex</span>
          <span className="font-tabular text-[11px] font-medium text-muted-foreground">v{APP_VERSION}</span>
        </div>
        <SegmentedNav />
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden min-w-26 text-right text-xs text-muted-foreground sm:inline">
            {isRunning ? 'syncing…' : lastSync ? `synced ${relativeTime(lastSync)}` : 'not synced yet'}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={isRunning}
            onClick={() =>
              triggerSync.mutate('incremental', {
                onSuccess: (data) => setWatchedRunId(data.sync_run_id),
                onError: () => toast({ title: 'Could not start sync', variant: 'error' }),
              })
            }
            title="Sync now (s)"
            data-sync-trigger
          >
            <RefreshCw className={cn('size-4', isRunning && 'animate-spin')} />
            Sync now
          </Button>
          <Button variant="ghost" size="icon" onClick={toggle} title="Toggle dark mode">
            {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex size-8 items-center justify-center rounded-full bg-secondary text-xs font-medium text-secondary-foreground transition-colors hover:bg-accent">
                {initial}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel className="text-[11px] font-normal normal-case text-muted-foreground">{email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => logout()} className="text-destructive focus:text-destructive">
                <LogOut className="size-3.5" />
                Log out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  )
}
