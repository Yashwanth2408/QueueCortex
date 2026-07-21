import { AlertTriangle, UserX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStatusCounts } from '@/hooks/useTickets'

export interface ChipFilter {
  status?: string
  level?: string
  assigned_to?: string
  closed_today?: boolean
}

export type ChipKey = 'open' | 'pending' | 'closed_today' | 'rejected' | 'blocked' | 'escalated' | 'unassigned'

const CHIPS: { key: ChipKey; label: string; filter: ChipFilter }[] = [
  { key: 'open', label: 'Open', filter: { status: 'OPEN' } },
  { key: 'pending', label: 'Pending', filter: { status: 'PENDING' } },
  { key: 'closed_today', label: 'Closed today', filter: { closed_today: true } },
  { key: 'rejected', label: 'Rejected', filter: { status: 'REJECTED' } },
  { key: 'blocked', label: 'Blocked', filter: { status: 'BLOCKED' } },
  { key: 'escalated', label: 'Escalated', filter: { level: 'L3' } },
  { key: 'unassigned', label: 'Unassigned', filter: { assigned_to: 'unassigned' } },
]

interface Props {
  active: ChipKey | null
  needsAttentionActive: boolean
  takenFromMeActive: boolean
  onSelect: (key: ChipKey | null, filter: ChipFilter | null) => void
  onToggleNeedsAttention: () => void
  onToggleTakenFromMe: () => void
}

export function StatusChips({
  active,
  needsAttentionActive,
  takenFromMeActive,
  onSelect,
  onToggleNeedsAttention,
  onToggleTakenFromMe,
}: Props) {
  const { data: counts } = useStatusCounts()

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {CHIPS.map((chip) => {
        const isActive = active === chip.key
        const count = counts?.[chip.key]
        return (
          <button
            key={chip.key}
            onClick={() => onSelect(isActive ? null : chip.key, isActive ? null : chip.filter)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors duration-100',
              isActive ? 'bg-foreground/10 text-foreground font-semibold' : 'text-muted-foreground hover:bg-secondary',
            )}
          >
            {chip.label} <span className="font-tabular opacity-70">{count ?? 0}</span>
          </button>
        )
      })}
      <button
        onClick={onToggleNeedsAttention}
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors duration-100',
          needsAttentionActive ? 'bg-amber text-amber-foreground font-semibold' : 'text-amber-foreground/80 hover:bg-amber/50',
        )}
      >
        <AlertTriangle className="size-3.5" />
        Needs attention <span className="font-tabular opacity-70">{counts?.needs_attention ?? 0}</span>
      </button>
      <button
        onClick={onToggleTakenFromMe}
        title="Tickets a person or the system unassigned you from"
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors duration-100',
          takenFromMeActive ? 'bg-red text-destructive font-semibold' : 'text-destructive/80 hover:bg-red/60',
        )}
      >
        <UserX className="size-3.5" />
        Taken from me <span className="font-tabular opacity-70">{counts?.taken_from_me ?? 0}</span>
      </button>
    </div>
  )
}
