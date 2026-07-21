import { useEffect, useState } from 'react'
import { Loader2, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { useToast } from '@/components/ui/toast'
import { useAddTicketByNumber } from '@/hooks/useTickets'
import { ApiError } from '@/lib/api'

function extractNumber(input: string): number | null {
  const trimmed = input.trim()
  if (/^\d+$/.test(trimmed)) return Number(trimmed)
  const match = trimmed.match(/(\d{4,})/)
  return match ? Number(match[1]) : null
}

export function AddTicketModal() {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const addTicket = useAddTicketByNumber()
  const toast = useToast()

  const handleFetch = (value = input) => {
    const num = extractNumber(value)
    if (num === null) {
      setError('Enter a valid ticket number (or paste a Trinity URL).')
      return
    }
    setError(null)
    addTicket.mutate(num, {
      onSuccess: (data) => toast({ title: `Ticket #${data.num} added`, variant: 'success' }),
      onError: (err) => setError(err instanceof ApiError ? err.message : 'Failed to fetch ticket'),
    })
  }

  useEffect(() => {
    if (!addTicket.isSuccess) return
    const t = setTimeout(() => setOpen(false), 1100)
    return () => clearTimeout(t)
  }, [addTicket.isSuccess])

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) {
          setInput('')
          setError(null)
          addTicket.reset()
        }
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm" title="Add ticket (n)" data-add-ticket-trigger>
          <Plus className="size-4" />
          Add ticket
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a ticket by number</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor="ticket-num">Trinity ticket number or URL</Label>
          <Input
            id="ticket-num"
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPaste={(e) => {
              const pasted = e.clipboardData.getData('text')
              if (extractNumber(pasted) !== null) {
                setInput(pasted)
                setTimeout(() => handleFetch(pasted), 0)
              }
            }}
            placeholder="e.g. 199088"
            onKeyDown={(e) => e.key === 'Enter' && handleFetch()}
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          {addTicket.isSuccess && (
            <div className="mt-1 rounded-lg bg-muted/60 p-3 text-sm">
              <p className="font-medium">
                #{addTicket.data.num} — {addTicket.data.subject}
              </p>
              <p className="text-muted-foreground">
                {addTicket.data.status} · {addTicket.data.customer?.first_name} {addTicket.data.customer?.last_name}
              </p>
              {addTicket.data.trinity_url && (
                <a href={addTicket.data.trinity_url} target="_blank" rel="noreferrer" className="text-foreground underline underline-offset-2">
                  Open in Trinity ↗
                </a>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Close
          </Button>
          <Button onClick={() => handleFetch()} disabled={addTicket.isPending}>
            {addTicket.isPending && <Loader2 className="size-4 animate-spin" />}
            {addTicket.isSuccess ? 'Added ✓' : 'Fetch & add'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
