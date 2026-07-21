import { useState } from 'react'
import { AlertTriangle, ChevronDown, ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { TicketHistoryPanel } from '@/components/tickets/TicketHistoryPanel'
import { useRosterOverdueTickets, useRosterTicketDetail } from '@/hooks/useRoster'
import { absoluteTime, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { RosterOverdueTicket, ShiftReason } from '@/types'

const COLUMNS = ['#', 'Holding', 'Type', 'Shift', 'Held', 'Last activity', '']

function formatShiftLabel(shiftCode: string | null, reason: ShiftReason): string {
  if (!shiftCode) return '—'
  if (reason === 'before_shift_start') return `${shiftCode} (not started)`
  if (reason === 'shift_ended') return `${shiftCode} (ended)`
  return shiftCode
}

function ShiftWatchRow({ ticket, expanded, onToggle }: { ticket: RosterOverdueTicket; expanded: boolean; onToggle: () => void }) {
  const { data: detail, isLoading } = useRosterTicketDetail(expanded ? ticket.id : null)

  return (
    <>
      <TableRow className={cn(ticket.is_associate_or_trainer && 'bg-red/50 hover:bg-red/70')}>
        <TableCell className="font-mono text-xs">
          {ticket.trinity_url ? (
            <a href={ticket.trinity_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
              #{ticket.num} <ExternalLink className="size-3 opacity-60" />
            </a>
          ) : (
            `#${ticket.num}`
          )}
        </TableCell>
        <TableCell className="max-w-45 truncate text-sm">
          <div className="flex flex-col">
            <span>{ticket.agent_name}</span>
            <span className="text-xs text-muted-foreground">{ticket.agent_role}</span>
          </div>
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1.5">
            {ticket.derived_type ? <Badge variant="secondary">{ticket.derived_type}</Badge> : <span className="text-xs text-muted-foreground">—</span>}
            {ticket.alert_tags.length > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex shrink-0 items-center text-destructive">
                    <AlertTriangle className="size-4" />
                  </span>
                </TooltipTrigger>
                <TooltipContent>Flagged tag{ticket.alert_tags.length > 1 ? 's' : ''}: {ticket.alert_tags.join(', ')}</TooltipContent>
              </Tooltip>
            )}
          </div>
        </TableCell>
        <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{formatShiftLabel(ticket.shift_code, ticket.reason)}</TableCell>
        <TableCell className="font-tabular text-xs whitespace-nowrap text-muted-foreground">
          {ticket.held_since ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <span>{relativeTime(ticket.held_since)}</span>
              </TooltipTrigger>
              <TooltipContent>Since {absoluteTime(ticket.held_since)}</TooltipContent>
            </Tooltip>
          ) : (
            '—'
          )}
        </TableCell>
        <TableCell className="font-tabular text-xs whitespace-nowrap text-muted-foreground">{relativeTime(ticket.last_event_at)}</TableCell>
        <TableCell>
          <button onClick={onToggle} className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground" aria-label="Toggle history">
            <ChevronDown className={cn('size-4 transition-transform duration-200', expanded && 'rotate-180')} />
          </button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={COLUMNS.length} className="p-0">
            <div className="mx-2 my-2 rounded-xl bg-muted/50 dark:bg-muted/30">
              <TicketHistoryPanel ticketId={ticket.id} detail={detail} isLoading={isLoading} />
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 4 }).map((_, i) => (
        <TableRow key={i}>
          <TableCell colSpan={COLUMNS.length}>
            <Skeleton className="h-5 w-full" />
          </TableCell>
        </TableRow>
      ))}
    </>
  )
}

export function ShiftWatch() {
  const { data: tickets, isLoading } = useRosterOverdueTickets()
  const [expandedId, setExpandedId] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-[28px] font-bold tracking-[-0.015em]">Shift Watch</h1>
        <p className="text-sm text-muted-foreground">
          Tickets held by an L2 agent who's currently off-shift — ended, not started yet today, or off/on leave.
        </p>
      </div>

      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {COLUMNS.map((c) => (
                <TableHead key={c}>{c}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <SkeletonRows />
            ) : tickets && tickets.length > 0 ? (
              tickets.map((t) => (
                <ShiftWatchRow key={t.id} ticket={t} expanded={expandedId === t.id} onToggle={() => setExpandedId(expandedId === t.id ? null : t.id)} />
              ))
            ) : (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={COLUMNS.length} className="py-8 text-center text-sm text-muted-foreground">
                  Nothing off-shift right now. Upload or update the roster in Settings if this looks stale.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
