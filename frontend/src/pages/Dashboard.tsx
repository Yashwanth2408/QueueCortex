import { useEffect, useMemo, useRef, useState } from 'react'
import { Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { StatusChips, type ChipFilter, type ChipKey } from '@/components/tickets/StatusChips'
import { FilterBar } from '@/components/tickets/FilterBar'
import { TicketTable } from '@/components/tickets/TicketTable'
import { AddTicketModal } from '@/components/tickets/AddTicketModal'
import { useStatusCounts, useTickets } from '@/hooks/useTickets'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'

export function Dashboard() {
  const [activeChip, setActiveChip] = useState<ChipKey | null>(null)
  const [chipFilter, setChipFilter] = useState<ChipFilter | null>(null)
  const [needsAttention, setNeedsAttention] = useState(false)
  const [takenFromMe, setTakenFromMe] = useState(false)
  const [search, setSearch] = useState('')
  const [derivedType, setDerivedType] = useState('')
  const [sort, setSort] = useState('last_event_at:desc')
  const [page, setPage] = useState(1)
  const searchRef = useRef<HTMLInputElement>(null)

  const debouncedSearch = useDebouncedValue(search, 280)

  const filters = {
    ...chipFilter,
    derived_type: derivedType || undefined,
    search: debouncedSearch || undefined,
    needs_attention: needsAttention || undefined,
    taken_from_me: takenFromMe || undefined,
    sort,
    page,
    page_size: 25,
  }

  const { data, isLoading, isFetching } = useTickets(filters)

  // Only the user-controlled filter shape drives the table's entrance
  // animation - never the fetched data itself, so a background sync never
  // replays the fade-in under the user.
  const animationKey = JSON.stringify(filters)

  const { data: statusCounts } = useStatusCounts()

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
      if (e.key === '/') {
        e.preventDefault()
        searchRef.current?.focus()
      } else if (e.key === 'n') {
        document.querySelector<HTMLButtonElement>('[data-add-ticket-trigger]')?.click()
      } else if (e.key === 's') {
        document.querySelector<HTMLButtonElement>('[data-sync-trigger]')?.click()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const totalPages = useMemo(() => (data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1), [data])

  return (
    <div className="flex flex-col gap-5">
      {statusCounts && (statusCounts.closed_today > 0 || statusCounts.reopened_today > 0) && (
        <Card className="bg-green/40 dark:bg-green/20">
          <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-1 py-4 text-sm">
            <span className="text-green-foreground font-tabular font-semibold" title="Tickets currently sitting closed that were closed today (excludes any that later reopened)">
              Today: {statusCounts.closed_today} closed
            </span>
            {statusCounts.closed_today > 0 && (
              <span className="font-tabular text-muted-foreground">
                ({statusCounts.fresh_closed_today} fresh, {statusCounts.reclosed_today} re-closed)
              </span>
            )}
            {statusCounts.reopened_today > 0 && (
              <span className="font-tabular text-muted-foreground">
                {statusCounts.reopened_today} reopened
                {statusCounts.customer_reopened_today > 0 ? ` (${statusCounts.customer_reopened_today} by customer)` : ''}
              </span>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusChips
          active={activeChip}
          needsAttentionActive={needsAttention}
          takenFromMeActive={takenFromMe}
          onSelect={(key, filter) => {
            setActiveChip(key)
            setChipFilter(filter)
            setPage(1)
          }}
          onToggleNeedsAttention={() => {
            setNeedsAttention((v) => !v)
            setPage(1)
          }}
          onToggleTakenFromMe={() => {
            setTakenFromMe((v) => !v)
            setPage(1)
          }}
        />
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <a href="/api/v1/export/tickets.csv" download>
              <Download className="size-4" />
              Export CSV
            </a>
          </Button>
          <AddTicketModal />
        </div>
      </div>

      <FilterBar
        search={search}
        onSearchChange={(v) => {
          setSearch(v)
          setPage(1)
        }}
        derivedType={derivedType}
        onDerivedTypeChange={(v) => {
          setDerivedType(v)
          setPage(1)
        }}
        sort={sort}
        onSortChange={setSort}
        searchInputRef={searchRef}
      />

      <TicketTable tickets={data?.items ?? []} isLoading={isLoading} animationKey={animationKey} />

      {data && data.total > data.page_size && (
        <div className="flex items-center justify-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </Button>
          <span className="font-tabular text-muted-foreground">
            Page {page} of {totalPages} {isFetching && '· loading…'}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
