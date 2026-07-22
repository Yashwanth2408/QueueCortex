import { useEffect, useRef, useState } from 'react'
import { Check } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { TagMappingTable } from '@/components/settings/TagMappingTable'
import { useSettings, useUpdateSetting } from '@/hooks/useSettings'
import { cn } from '@/lib/utils'
import type { MyShift, SettingValue } from '@/types'

const SHIFT_CODES = ['6A-3P', '11A-8P', '9P-6A']
const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

function MyShiftCard() {
  const { data: settings } = useSettings()
  const updateSetting = useUpdateSetting()
  const flash = useSavedFlash()

  const [shiftCode, setShiftCode] = useState<string | null>(null)
  const [validFrom, setValidFrom] = useState('')
  const [validTo, setValidTo] = useState('')
  const [dayOff, setDayOff] = useState<string | null>(null)

  useEffect(() => {
    if (!settings) return
    const myShift = settings.find((s) => s.key === 'my_shift_json')?.value as MyShift | undefined
    if (!myShift) return
    setShiftCode(myShift.shift_code)
    setValidFrom(myShift.valid_from ?? '')
    setValidTo(myShift.valid_to ?? '')
    setDayOff(myShift.day_off)
  }, [settings])

  const save = (next: Partial<MyShift>) => {
    const merged: MyShift = {
      shift_code: shiftCode,
      valid_from: validFrom || null,
      valid_to: validTo || null,
      day_off: dayOff,
      ...next,
    }
    updateSetting.mutate({ key: 'my_shift_json', value: merged as unknown as SettingValue }, { onSuccess: flash.flash })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>My Shift</CardTitle>
        <p className="text-sm text-muted-foreground">
          Your own shift, so the Dashboard can remind you before it ends and Analytics can skip your day off when computing streaks.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <Label>Shift</Label>
          <SavedBadge show={flash.saved} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">Shift timing</Label>
            <Select
              value={shiftCode ?? undefined}
              onValueChange={(v) => {
                setShiftCode(v)
                save({ shift_code: v })
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select shift" />
              </SelectTrigger>
              <SelectContent>
                {SHIFT_CODES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="shift-from" className="text-xs text-muted-foreground">
              Valid from
            </Label>
            <Input
              id="shift-from"
              type="date"
              value={validFrom}
              onChange={(e) => setValidFrom(e.target.value)}
              onBlur={() => save({ valid_from: validFrom || null })}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="shift-to" className="text-xs text-muted-foreground">
              Valid to
            </Label>
            <Input
              id="shift-to"
              type="date"
              value={validTo}
              onChange={(e) => setValidTo(e.target.value)}
              onBlur={() => save({ valid_to: validTo || null })}
            />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label className="text-xs text-muted-foreground">Day off</Label>
          <div className="inline-flex w-fit items-center rounded-full bg-secondary p-0.75">
            {WEEKDAYS.map((day) => (
              <button
                key={day}
                onClick={() => {
                  const next = dayOff === day ? null : day
                  setDayOff(next)
                  save({ day_off: next })
                }}
                className={cn(
                  'rounded-full px-3 py-1 text-sm font-medium whitespace-nowrap transition-all duration-150',
                  dayOff === day ? 'bg-card text-foreground shadow-[0_1px_3px_rgba(0,0,0,0.12)]' : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {day.slice(0, 3)}
              </button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

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

function RosterBucketsCard() {
  const { data: settings } = useSettings()
  const updateSetting = useUpdateSetting()

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

  return (
    <Card>
      <CardHeader>
        <CardTitle>Shift Watch buckets</CardTitle>
        <p className="text-sm text-muted-foreground">
          The two Trinity buckets that define "L2, non-Expo" tickets for Shift Watch. Upload/manage the roster itself from the Shift
          Watch page.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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

      <MyShiftCard />

      <RosterBucketsCard />
    </div>
  )
}
