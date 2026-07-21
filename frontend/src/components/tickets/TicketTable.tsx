import { useState } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { TicketRow } from '@/components/tickets/TicketRow'
import type { TicketListItem } from '@/types'

const COLUMNS = ['#', 'Subject', 'Customer', 'Type', 'Status', 'Level', 'Last activity', 'Assigned', '']

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <TableRow key={i} className="hover:bg-transparent">
          {COLUMNS.map((_col, j) => (
            <TableCell key={j}>
              <Skeleton className="h-4 w-full max-w-24" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  )
}

interface Props {
  tickets: TicketListItem[]
  isLoading: boolean
  /** Changes only on genuine user-triggered filter/sort/search/page changes
   * (never on a background refetch) - remounting the body on key change is
   * what drives the one-time entrance fade, so background syncs never
   * cause the list to visually replay. */
  animationKey: string
}

export function TicketTable({ tickets, isLoading, animationKey }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (!isLoading && tickets.length === 0) {
    return <p className="py-10 text-center text-sm text-muted-foreground">No tickets match this filter.</p>
  }

  return (
    <div className="overflow-hidden rounded-xl bg-card shadow-[0_1px_2px_rgba(0,0,0,0.06),0_8px_24px_-12px_rgba(0,0,0,0.18)] dark:border dark:border-border dark:shadow-none">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            {COLUMNS.map((col, i) => (
              <TableHead key={i}>{col}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        {isLoading && tickets.length === 0 ? (
          <TableBody>
            <SkeletonRows />
          </TableBody>
        ) : (
          <TableBody key={animationKey} className="animate-fade-up">
            {tickets.map((t) => (
              <TicketRow key={t.id} ticket={t} expanded={expandedId === t.id} onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)} />
            ))}
          </TableBody>
        )}
      </Table>
    </div>
  )
}
