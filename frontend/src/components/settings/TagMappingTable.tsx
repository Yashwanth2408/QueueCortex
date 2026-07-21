import { useEffect, useState } from 'react'
import { Check, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useToast } from '@/components/ui/toast'
import { useSaveTagMappings, useTagMappings, useTags } from '@/hooks/useTags'
import type { TagMapping } from '@/types'

interface Row {
  tag_id: string
  label: string
  ticket_count: number
  type_label: string
  priority: number
}

export function TagMappingTable() {
  const { data: tags, isLoading: tagsLoading } = useTags()
  const { data: mappings, isLoading: mappingsLoading } = useTagMappings()
  const save = useSaveTagMappings()
  const toast = useToast()
  const [rows, setRows] = useState<Row[]>([])

  useEffect(() => {
    if (!tags) return
    const byId = new Map((mappings ?? []).map((m) => [m.tag_id, m]))
    setRows(
      tags.map((t) => {
        const existing = byId.get(t.tag_id)
        return {
          tag_id: t.tag_id,
          label: t.label,
          ticket_count: t.ticket_count,
          type_label: existing?.type_label ?? 'Uncategorized',
          priority: existing?.priority ?? 100,
        }
      }),
    )
  }, [tags, mappings])

  if (tagsLoading || mappingsLoading) {
    return <p className="text-sm text-muted-foreground">Loading tags…</p>
  }

  const datalistId = 'known-type-labels'
  const knownTypes = Array.from(new Set(rows.map((r) => r.type_label))).sort()

  const handleSave = () => {
    const payload: TagMapping[] = rows
      .filter((r) => r.type_label.trim())
      .map((r) => ({ tag_id: r.tag_id, type_label: r.type_label.trim(), priority: r.priority }))
    save.mutate(payload, {
      onSuccess: () => toast({ title: 'Tag mapping saved', description: 'Types recomputed across the dashboard.', variant: 'success' }),
      onError: () => toast({ title: 'Could not save tag mapping', variant: 'error' }),
    })
  }

  return (
    <div className="flex flex-col gap-3">
      <datalist id={datalistId}>
        {knownTypes.map((t) => (
          <option key={t} value={t} />
        ))}
      </datalist>
      <div className="overflow-hidden rounded-xl bg-card shadow-[0_1px_2px_rgba(0,0,0,0.06),0_8px_24px_-12px_rgba(0,0,0,0.18)] dark:border dark:border-border dark:shadow-none">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tag (as seen in Trinity)</TableHead>
              <TableHead className="text-right">Tickets</TableHead>
              <TableHead>Mapped type</TableHead>
              <TableHead className="w-24">Priority</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={row.tag_id}>
                <TableCell className="font-medium">{row.label}</TableCell>
                <TableCell className="text-right text-muted-foreground">{row.ticket_count}</TableCell>
                <TableCell>
                  <Input
                    list={datalistId}
                    value={row.type_label}
                    onChange={(e) => {
                      const value = e.target.value
                      setRows((r) => r.map((x, idx) => (idx === i ? { ...x, type_label: value } : x)))
                    }}
                    className="h-8"
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="number"
                    value={row.priority}
                    onChange={(e) => {
                      const value = Number(e.target.value)
                      setRows((r) => r.map((x, idx) => (idx === i ? { ...x, priority: value } : x)))
                    }}
                    className="h-8"
                  />
                </TableCell>
              </TableRow>
            ))}
            {rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  No tags observed yet — run a sync first.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center gap-2">
        <Button onClick={handleSave} disabled={save.isPending}>
          {save.isPending ? <Loader2 className="size-4 animate-spin" /> : <Check className="size-4" />}
          Save mapping
        </Button>
      </div>
    </div>
  )
}
