import { useState } from 'react'
import { Loader2, MessageSquareQuote, Send, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { useAddComment, useDeleteComment, useTicketDetail } from '@/hooks/useTickets'
import { absoluteTime, relativeTime } from '@/lib/format'
import type { AssignmentEventOut, StatusTransition, CsatEventOut } from '@/types'

type TimelineEntry = {
  created_at: string
  label: string
  tone: 'default' | 'reopen' | 'close' | 'muted' | 'taken'
  indent?: boolean
}

function buildTimeline(
  transitions: StatusTransition[],
  csats: CsatEventOut[],
  assignmentEvents: AssignmentEventOut[],
): TimelineEntry[] {
  const entries: TimelineEntry[] = []
  let gainCount = 0
  for (const a of assignmentEvents) {
    if (a.is_gain_for_tracked_agent) {
      gainCount += 1
      entries.push({
        created_at: a.created_at,
        label: gainCount === 1 ? 'Self-assigned to you' : 'Reassigned back to you',
        tone: 'default',
      })
    } else if (a.is_taken_from_tracked_agent) {
      let label: string
      if (a.is_system_action) {
        label = a.reason === 'reopen_offline_assignee' ? 'Unassigned by system — you were offline on reopen' : 'Unassigned by system'
      } else if (a.new_assignee) {
        label = `Taken from you — reassigned to ${a.new_assignee}`
      } else {
        label = `Unassigned — by ${a.performed_by_email ?? 'someone'}`
      }
      entries.push({ created_at: a.created_at, label, tone: 'taken' })
    }
  }
  for (const t of transitions) {
    if (t.is_reopen) {
      entries.push({
        created_at: t.created_at,
        label: t.is_customer_triggered_reopen ? 'Reopened — customer replied' : 'Reopened',
        tone: 'reopen',
      })
    } else if (t.is_close) {
      entries.push({ created_at: t.created_at, label: `Closed (${t.new_status})`, tone: 'close' })
    } else {
      entries.push({ created_at: t.created_at, label: `${t.old_status ?? '—'} → ${t.new_status}`, tone: 'default' })
    }
  }
  for (const c of csats) {
    entries.push({
      created_at: c.created_at,
      label: c.action === 'csat_sent' ? 'CSAT survey sent' : 'CSAT cancelled',
      tone: 'muted',
      indent: true,
    })
  }
  return entries.sort((a, b) => a.created_at.localeCompare(b.created_at))
}

const DOT_CLASS: Record<TimelineEntry['tone'], string> = {
  default: 'bg-foreground',
  reopen: 'bg-indigo-foreground',
  close: 'bg-green-foreground',
  muted: 'bg-muted-foreground/50',
  taken: 'bg-destructive',
}

export function TicketHistoryPanel({ ticketId }: { ticketId: string }) {
  const { data: detail, isLoading } = useTicketDetail(ticketId)
  const [showAll, setShowAll] = useState(false)
  const [draft, setDraft] = useState('')
  const addComment = useAddComment(ticketId)
  const deleteComment = useDeleteComment(ticketId)

  if (isLoading || !detail) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading history…
      </div>
    )
  }

  const timeline = buildTimeline(detail.status_transitions, detail.csat_events, detail.assignment_events)
  const TRUNCATE_AT = 8
  const visible = showAll || timeline.length <= TRUNCATE_AT ? timeline : timeline.slice(-TRUNCATE_AT)
  const hiddenCount = timeline.length - visible.length

  return (
    <div className="grid grid-cols-1 gap-6 px-5 py-5 md:grid-cols-2">
      <div>
        <h4 className="mb-3 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Open/close history</h4>
        {hiddenCount > 0 && (
          <button className="mb-2 text-xs font-medium text-foreground hover:underline" onClick={() => setShowAll(true)}>
            Show {hiddenCount} earlier event{hiddenCount === 1 ? '' : 's'}
          </button>
        )}
        <ol className="space-y-3 border-l border-border pl-4">
          {visible.map((e, i) => (
            <li key={i} className={cnIndent(e.indent)}>
              <span className={`absolute -left-5.25 mt-1 size-2.5 rounded-full ring-4 ring-background ${DOT_CLASS[e.tone]}`} />
              <div className="flex items-baseline justify-between gap-2">
                <span className={e.tone === 'muted' ? 'text-xs text-muted-foreground' : 'text-sm font-medium'}>{e.label}</span>
                <span title={absoluteTime(e.created_at)} className="font-tabular shrink-0 text-xs text-muted-foreground">
                  {absoluteTime(e.created_at)}
                </span>
              </div>
            </li>
          ))}
        </ol>
        {timeline.length > TRUNCATE_AT && showAll && (
          <button className="mt-2 text-xs font-medium text-foreground hover:underline" onClick={() => setShowAll(false)}>
            Show less
          </button>
        )}
        {detail.duplicates.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {detail.duplicates.map((d) => (
              <Badge key={d.id} variant="secondary">
                Duplicate of #{d.duplicate_of_num}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4">
        <div>
          <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            <MessageSquareQuote className="size-3.5" /> Your last internal note (Trinity)
          </h4>
          {detail.last_trinity_internal_note ? (
            <div
              className="rounded-md border bg-muted/40 px-3 py-2 text-sm [&_p]:m-0"
              dangerouslySetInnerHTML={{ __html: detail.last_trinity_internal_note }}
            />
          ) : (
            <p className="text-sm text-muted-foreground">No internal note from you yet.</p>
          )}
        </div>

        <div>
          <h4 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">My tracker notes</h4>
          <div className="mb-2 space-y-2">
            {detail.local_notes.map((n) => (
              <div key={n.id} className="group flex items-start justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                <div>
                  <p>{n.body}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{relativeTime(n.created_at)}</p>
                </div>
                <button
                  className="text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                  onClick={() => deleteComment.mutate(n.id)}
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            ))}
            {detail.local_notes.length === 0 && <p className="text-sm text-muted-foreground">No notes yet.</p>}
          </div>
          <div className="flex gap-2">
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add a private note (not sent to the customer or Trinity)…"
              className="min-h-10"
            />
            <Button
              size="icon"
              disabled={!draft.trim() || addComment.isPending}
              onClick={() => {
                addComment.mutate(draft, { onSuccess: () => setDraft('') })
              }}
            >
              <Send className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function cnIndent(indent?: boolean) {
  return `relative ${indent ? 'ml-4 opacity-80' : ''}`
}
