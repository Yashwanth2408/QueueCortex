import { useEffect, useRef, useState } from 'react'
import { Check, Loader2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useToast } from '@/components/ui/toast'
import { TagMappingTable } from '@/components/settings/TagMappingTable'
import { useSettings, useUpdateSetting } from '@/hooks/useSettings'
import { useRosterAgents, useUploadRoster } from '@/hooks/useRoster'
import type { SettingValue } from '@/types'

function useSavedFlash() {
  const [saved, setSaved] = useState(false)
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const flash = () => {
    setSaved(true)
    if (timeoutRef.current) clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => setSaved(false), 1600)
  }
  return { saved, flash }
}

function SavedBadge({ show }: { show: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs text-green-foreground transition-opacity duration-300 ${show ? 'opacity-100' : 'opacity-0'}`}
    >
      <Check className="size-3.5" /> Saved
    </span>
  )
}

function RosterCard() {
  const { data: agents } = useRosterAgents()
  const { data: settings } = useSettings()
  const updateSetting = useUpdateSetting()
  const uploadRoster = useUploadRoster()
  const toast = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [unassignedBucketId, setUnassignedBucketId] = useState('')
  const [assignedBucketId, setAssignedBucketId] = useState('')
  const unassignedFlash = useSavedFlash()
  const assignedFlash = useSavedFlash()

  useEffect(() => {
    if (!settings) return
    const get = (k: string) => settings.find((s) => s.key === k)?.value
    if (get('roster_bucket_unassigned_id')) setUnassignedBucketId(String(get('roster_bucket_unassigned_id')))
    if (get('roster_bucket_assigned_id')) setAssignedBucketId(String(get('roster_bucket_assigned_id')))
  }, [settings])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    uploadRoster.mutate(file, {
      onSuccess: (result) => {
        toast({
          title: 'Roster uploaded',
          description: `${result.agents} agents, ${result.shift_rows} shift rows (${result.date_range[0] ?? '?'} – ${result.date_range[1] ?? '?'})`,
          variant: 'success',
        })
      },
      onError: (err) => {
        toast({ title: 'Upload failed', description: err instanceof Error ? err.message : undefined, variant: 'error' })
      },
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>L2 Roster</CardTitle>
        <p className="text-sm text-muted-foreground">
          Upload the shift-roster CSV to power Shift Watch — tickets held by an L2 agent who's currently off-shift. Tickets come only
          from the two Trinity buckets below, so L1/Expo tickets never show up here.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleFileChange} />
          <Button onClick={() => fileInputRef.current?.click()} disabled={uploadRoster.isPending}>
            {uploadRoster.isPending ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />}
            Upload roster CSV
          </Button>
          {agents && agents.length > 0 && <span className="text-sm text-muted-foreground">{agents.length} agents loaded</span>}
        </div>

        <div className="grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="bucket-unassigned">"L2 - Unassigned Tickets" bucket ID</Label>
              <SavedBadge show={unassignedFlash.saved} />
            </div>
            <Input
              id="bucket-unassigned"
              value={unassignedBucketId}
              onChange={(e) => setUnassignedBucketId(e.target.value)}
              onBlur={() => updateSetting.mutate({ key: 'roster_bucket_unassigned_id', value: unassignedBucketId }, { onSuccess: unassignedFlash.flash })}
              className="font-mono text-xs"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="bucket-assigned">"L2 - Assigned (New Assigned + Re-opens)" bucket ID</Label>
              <SavedBadge show={assignedFlash.saved} />
            </div>
            <Input
              id="bucket-assigned"
              value={assignedBucketId}
              onChange={(e) => setAssignedBucketId(e.target.value)}
              onBlur={() => updateSetting.mutate({ key: 'roster_bucket_assigned_id', value: assignedBucketId }, { onSuccess: assignedFlash.flash })}
              className="font-mono text-xs"
            />
          </div>
        </div>

        {agents && agents.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Today</TableHead>
                  <TableHead>Tomorrow</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {agents.map((a) => (
                  <TableRow key={a.email}>
                    <TableCell>{a.name}</TableCell>
                    <TableCell className="text-muted-foreground">{a.role}</TableCell>
                    <TableCell className="font-tabular">{a.today_shift_code ?? '—'}</TableCell>
                    <TableCell className="font-tabular">{a.tomorrow_shift_code ?? '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function Settings() {
  const { data: settings } = useSettings()
  const updateSetting = useUpdateSetting()

  const [urlTemplate, setUrlTemplate] = useState('')
  const [pollInterval, setPollInterval] = useState(20)
  const [reportingTz, setReportingTz] = useState('Asia/Kolkata')
  const [slaOpen, setSlaOpen] = useState(24)
  const [slaPending, setSlaPending] = useState(48)

  const urlFlash = useSavedFlash()
  const pollFlash = useSavedFlash()
  const tzFlash = useSavedFlash()
  const slaFlash = useSavedFlash()

  useEffect(() => {
    if (!settings) return
    const get = (k: string) => settings.find((s) => s.key === k)?.value
    if (get('trinity_ticket_url_template')) setUrlTemplate(String(get('trinity_ticket_url_template')))
    if (get('poll_interval_minutes')) setPollInterval(Number(get('poll_interval_minutes')))
    if (get('reporting_timezone')) setReportingTz(String(get('reporting_timezone')))
    const sla = get('sla_thresholds_json') as Record<string, number> | undefined
    if (sla) {
      setSlaOpen(sla.OPEN ?? 24)
      setSlaPending(sla.PENDING ?? 48)
    }
  }, [settings])

  const commit = (key: string, value: SettingValue, flash: () => void) => {
    updateSetting.mutate({ key, value }, { onSuccess: flash })
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <h1 className="text-[28px] font-bold tracking-[-0.015em]">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col divide-y divide-border">
          <div className="flex flex-col gap-1.5 pb-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="url-template">Trinity ticket URL template</Label>
              <SavedBadge show={urlFlash.saved} />
            </div>
            <Input
              id="url-template"
              value={urlTemplate}
              onChange={(e) => setUrlTemplate(e.target.value)}
              onBlur={() => commit('trinity_ticket_url_template', urlTemplate, urlFlash.flash)}
            />
            <p className="text-xs text-muted-foreground">
              Use <code>{'{id}'}</code> as a placeholder for the ticket's Trinity ID (the hex string in the URL, not the ticket number).
            </p>
          </div>

          <div className="flex flex-col gap-1.5 py-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="poll-interval">Background sync interval (minutes)</Label>
              <SavedBadge show={pollFlash.saved} />
            </div>
            <Input
              id="poll-interval"
              type="number"
              min={5}
              value={pollInterval}
              onChange={(e) => setPollInterval(Number(e.target.value))}
              onBlur={() => commit('poll_interval_minutes', pollInterval, pollFlash.flash)}
              className="w-32"
            />
          </div>

          <div className="flex flex-col gap-1.5 py-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="reporting-tz">Reporting timezone (IANA name)</Label>
              <SavedBadge show={tzFlash.saved} />
            </div>
            <Input
              id="reporting-tz"
              value={reportingTz}
              onChange={(e) => setReportingTz(e.target.value)}
              onBlur={() => commit('reporting_timezone', reportingTz, tzFlash.flash)}
              className="w-56"
            />
            <p className="text-xs text-muted-foreground">Controls which calendar day a close/reopen event counts toward.</p>
          </div>

          <div className="flex flex-col gap-1.5 pt-4">
            <div className="flex items-center justify-between">
              <Label>Aging highlight thresholds (hours) — a local heuristic, not a real Trinity SLA</Label>
              <SavedBadge show={slaFlash.saved} />
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Open</span>
                <Input
                  type="number"
                  value={slaOpen}
                  onChange={(e) => setSlaOpen(Number(e.target.value))}
                  onBlur={() => commit('sla_thresholds_json', { OPEN: slaOpen, PENDING: slaPending }, slaFlash.flash)}
                  className="w-20"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Pending</span>
                <Input
                  type="number"
                  value={slaPending}
                  onChange={(e) => setSlaPending(Number(e.target.value))}
                  onBlur={() => commit('sla_thresholds_json', { OPEN: slaOpen, PENDING: slaPending }, slaFlash.flash)}
                  className="w-20"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tag → Type mapping</CardTitle>
          <p className="text-sm text-muted-foreground">
            Lower priority number wins when a ticket has multiple mapped tags. Changes apply instantly to the dashboard and analytics.
          </p>
        </CardHeader>
        <CardContent>
          <TagMappingTable />
        </CardContent>
      </Card>

      <RosterCard />
    </div>
  )
}
