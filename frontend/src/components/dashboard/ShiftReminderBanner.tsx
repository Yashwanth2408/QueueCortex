import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { X } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { useSettings } from '@/hooks/useSettings'
import type { MyShift } from '@/types'

function daysUntil(dateStr: string): number {
  const [y, m, d] = dateStr.split('-').map(Number)
  const target = new Date(y, m - 1, d)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / 86_400_000)
}

function todayKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

export function ShiftReminderBanner() {
  const { data: settings } = useSettings()
  const [dismissedDay, setDismissedDay] = useState<string | null>(null)

  useEffect(() => {
    setDismissedDay(localStorage.getItem('qc_shift_reminder_dismissed'))
  }, [])

  const myShift = settings?.find((s) => s.key === 'my_shift_json')?.value as MyShift | undefined
  if (!myShift?.valid_to || dismissedDay === todayKey()) return null

  const daysLeft = daysUntil(myShift.valid_to)
  if (daysLeft > 7) return null

  const expired = daysLeft < 0
  const urgent = daysLeft <= 3
  const message = expired
    ? 'Your shift info is out of date — update it in Settings.'
    : urgent
      ? `Your shift ends in ${daysLeft} day${daysLeft === 1 ? '' : 's'} — add the new shift in Settings.`
      : `Your shift ends in ${daysLeft} day${daysLeft === 1 ? '' : 's'} — update it in Settings when you know your next one.`

  const dismiss = () => {
    const key = todayKey()
    localStorage.setItem('qc_shift_reminder_dismissed', key)
    setDismissedDay(key)
  }

  return (
    <Card className={expired || urgent ? 'bg-red/40 dark:bg-red/20' : 'bg-amber/40 dark:bg-amber/20'}>
      <CardContent className="flex items-center justify-between gap-3 py-3 text-sm">
        <span className={expired || urgent ? 'text-destructive font-medium' : 'text-amber-foreground font-medium'}>{message}</span>
        <div className="flex items-center gap-3">
          <Link to="/settings" className="text-xs font-semibold underline underline-offset-2 hover:no-underline">
            Go to Settings
          </Link>
          <button onClick={dismiss} aria-label="Dismiss for today" className="text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        </div>
      </CardContent>
    </Card>
  )
}
