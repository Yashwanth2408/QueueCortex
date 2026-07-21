import { ChevronDown, ExternalLink, MessageCircle, RotateCcw, UserX } from 'lucide-react'
import { TableCell, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { TicketHistoryPanel } from '@/components/tickets/TicketHistoryPanel'
import { useTicketDetail } from '@/hooks/useTickets'
import { absoluteTime, relativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { TicketListItem } from '@/types'

const STATUS_VARIANT: Record<string, 'default' | 'amber' | 'success' | 'destructive' | 'outline'> = {
  OPEN: 'default',
  PENDING: 'amber',
  CLOSED: 'success',
  REJECTED: 'destructive',
  BLOCKED: 'outline',
}

interface Props {
  ticket: TicketListItem
  expanded: boolean
  onToggle: () => void
}

export function TicketRow({ ticket, expanded, onToggle }: Props) {
  const customerName = [ticket.customer?.first_name, ticket.customer?.last_name].filter(Boolean).join(' ') || ticket.customer?.email
  const { data: detail, isLoading: detailLoading } = useTicketDetail(expanded ? ticket.id : null)

  return (
    <>
      <TableRow
        className={cn(
          ticket.needs_attention && 'bg-amber/40 hover:bg-amber/50',
          !ticket.needs_attention && ticket.taken_from_me_count > 0 && 'bg-red/50 hover:bg-red/70',
        )}
      >
        <TableCell className="font-mono text-xs">
          {ticket.trinity_url ? (
            <a href={ticket.trinity_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 hover:underline">
              #{ticket.num} <ExternalLink className="size-3 opacity-60" />
            </a>
          ) : (
            `#${ticket.num}`
          )}
        </TableCell>
        <TableCell className="max-w-70 truncate" title={ticket.subject ?? undefined}>
          {ticket.subject || <span className="text-muted-foreground">(no subject)</span>}
        </TableCell>
        <TableCell className="max-w-40 truncate text-sm text-muted-foreground" title={customerName ?? undefined}>
          {customerName || '—'}
        </TableCell>
        <TableCell>
          {ticket.derived_type ? <Badge variant="secondary">{ticket.derived_type}</Badge> : <span className="text-muted-foreground text-xs">—</span>}
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-1.5">
            <Badge variant={STATUS_VARIANT[ticket.status] ?? 'outline'}>{ticket.status}</Badge>
            {ticket.reopen_count > 0 && (
              <span className="text-indigo-foreground inline-flex items-center gap-0.5 text-xs" title={`Reopened ${ticket.reopen_count}x`}>
                <RotateCcw className="size-3" />
                <span className="font-tabular">{ticket.reopen_count}</span>
              </span>
            )}
          </div>
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">{ticket.level || '—'}</TableCell>
        <TableCell className="font-tabular text-xs whitespace-nowrap text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            {ticket.needs_attention && <MessageCircle className="text-amber-foreground size-3" />}
            {relativeTime(ticket.last_event_at)}
          </span>
        </TableCell>
        <TableCell className="max-w-35 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <span className="truncate">{ticket.assigned_to_email || 'Unassigned'}</span>
            {ticket.taken_from_me_count > 0 && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="text-destructive inline-flex shrink-0 items-center">
                    <UserX className="size-3.5" />
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  Taken from you {ticket.taken_from_me_count}x — last {absoluteTime(ticket.last_taken_from_me_at)}
                  {ticket.last_taken_from_me_reason ? ` (${ticket.last_taken_from_me_reason})` : ''}
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </TableCell>
        <TableCell>
          <button onClick={onToggle} className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground" aria-label="Toggle history">
            <ChevronDown className={cn('size-4 transition-transform duration-200', expanded && 'rotate-180')} />
          </button>
        </TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="hover:bg-transparent">
          <TableCell colSpan={9} className="p-0">
            <div className="mx-2 my-2 rounded-xl bg-muted/50 dark:bg-muted/30">
              <TicketHistoryPanel ticketId={ticket.id} detail={detail} isLoading={detailLoading} />
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}
