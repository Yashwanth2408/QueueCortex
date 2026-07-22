import { AlertTriangle, ArrowDownRight, ArrowUpRight, LogOut, UserX } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStatusCounts } from '@/hooks/useTickets'

export interface ChipFilter {
  status?: string
  closed_today?: boolean
}

export type ChipKey = 'open' | 'pending' | 'closed_today' | 'rejected'

const CHIPS: { key: ChipKey; label: string; filter: ChipFilter }[] = [
  { key: 'open', label: 'Open', filter: { status: 'OPEN' } },
  { key: 'pending', label: 'Pending', filter: { status: 'PENDING' } },
  { key: 'closed_today', label: 'Closed today', filter: { closed_today: true } },
  { key: 'rejected', label: 'Rejected', filter: { status: 'REJECTED' } },
]

interface Props {
  active: ChipKey | null
  needsAttentionActive: boolean
  takenFromMeActive: boolean
  selfReleasedActive: boolean
  escalatedByMeActive: boolean
  deescalatedByMeActive: boolean
  onSelect: (key: ChipKey | null, filter: ChipFilter | null) => void
  onToggleNeedsAttention: () => void
  onToggleTakenFromMe: () => void
  onToggleSelfReleased: () => void
  onToggleEscalatedByMe: () => void
  onToggleDeescalatedByMe: () => void
}

export function StatusChips({
  active,
  needsAttentionActive,
  takenFromMeActive,
  selfReleasedActive,
  escalatedByMeActive,
  deescalatedByMeActive,
  onSelect,
  onToggleNeedsAttention,
  onToggleTakenFromMe,
  onToggleSelfReleased,
  onToggleEscalatedByMe,
  onToggleDeescalatedByMe,
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
      <button
        onClick={onToggleSelfReleased}
        title="Tickets you unassigned yourself from"
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors duration-100',
          selfReleasedActive ? 'bg-secondary text-foreground font-semibold' : 'text-muted-foreground hover:bg-secondary',
        )}
      >
        <LogOut className="size-3.5" />
        Self-released <span className="font-tabular opacity-70">{counts?.self_released ?? 0}</span>
      </button>
      <button
        onClick={onToggleEscalatedByMe}
        title="Tickets you pushed from L2 to L3 and handed off yourself"
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors duration-100',
          escalatedByMeActive ? 'bg-red text-destructive font-semibold' : 'text-destructive/80 hover:bg-red/60',
        )}
      >
        <ArrowUpRight className="size-3.5" />
        Escalated <span className="font-tabular opacity-70">{counts?.escalated_count ?? 0}</span>
      </button>
      <button
        onClick={onToggleDeescalatedByMe}
        title="Tickets you pushed from L2 to L1 and handed off yourself"
        className={cn(
          'inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-colors duration-100',
          deescalatedByMeActive ? 'bg-amber text-amber-foreground font-semibold' : 'text-amber-foreground/80 hover:bg-amber/50',
        )}
      >
        <ArrowDownRight className="size-3.5" />
        De-escalated <span className="font-tabular opacity-70">{counts?.deescalated_count ?? 0}</span>
      </button>
    </div>
  )
}
