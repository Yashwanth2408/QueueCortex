import { useMemo, useState } from 'react'
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { useAnalyticsSummary } from '@/hooks/useAnalytics'
import { useTickets } from '@/hooks/useTickets'
import { useSettings } from '@/hooks/useSettings'
import { useDarkMode } from '@/context/DarkModeContext'
import { formatMinutes } from '@/lib/format'
import type { AnalyticsSummaryBucket, MyShift } from '@/types'

type Period = 'day' | 'month' | 'year'

const PALETTE = {
  light: { strong: '#1c1c1e', muted: '#a0a0a6', indigo: '#6d4fd1', red: '#dc4444', grid: '#00000012' },
  dark: { strong: '#f5f5f7', muted: '#8e8e96', indigo: '#a794f0', red: '#f0776a', grid: '#ffffff14' },
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-popover/90 px-3 py-2 text-xs shadow-[0_4px_16px_-4px_rgba(0,0,0,0.2)] backdrop-blur-xl backdrop-saturate-150">
      <p className="font-tabular mb-1 font-medium text-foreground">{label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-1.5 text-muted-foreground">
          <span className="size-1.5 rounded-full" style={{ backgroundColor: p.color }} />
          {p.name}: <span className="font-tabular font-medium text-foreground">{p.value}</span>
        </p>
      ))}
    </div>
  )
}

function KpiCard({ label, value, sub, loading }: { label: string; value: string; sub?: string; loading?: boolean }) {
  return (
    <Card>
      <CardContent className="py-4">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        {loading ? (
          <Skeleton className="mt-2 h-7 w-16" />
        ) : (
          <p className="font-tabular mt-1 text-[22px] leading-tight font-semibold tracking-[-0.01em]">{value}</p>
        )}
        {sub && !loading && <p className="text-xs text-muted-foreground">{sub}</p>}
      </CardContent>
    </Card>
  )
}

function ChartCardSkeleton({ height }: { height: number }) {
  return <Skeleton className="w-full rounded-lg" style={{ height }} />
}

const WEEKDAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

/** bucket dates are plain "YYYY-MM-DD" strings - parse via local components,
 * not `new Date(str)`, which parses bare dates as UTC midnight and can shift
 * a day off in either direction depending on the viewer's timezone offset. */
function parseLocalDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function isDayOff(dateStr: string, myShift: MyShift | undefined): boolean {
  if (!myShift?.day_off) return false
  const date = parseLocalDate(dateStr)
  if (myShift.valid_from && date < parseLocalDate(myShift.valid_from)) return false
  if (myShift.valid_to && date > parseLocalDate(myShift.valid_to)) return false
  return WEEKDAY_NAMES[date.getDay()] === myShift.day_off
}

/** Walks backward from most recent; a day off is skipped (doesn't break or
 * extend the streak), since it was never expected to have a close. */
function computeStreak(buckets: { bucket: string; closed_count: number }[], myShift?: MyShift): number {
  let streak = 0
  for (let i = buckets.length - 1; i >= 0; i--) {
    if (buckets[i].closed_count > 0) streak++
    else if (isDayOff(buckets[i].bucket, myShift)) continue
    else break
  }
  return streak
}

function computeBestStreak(buckets: { bucket: string; closed_count: number }[], myShift?: MyShift): number {
  let best = 0
  let current = 0
  for (const b of buckets) {
    if (b.closed_count > 0) {
      current++
      best = Math.max(best, current)
    } else if (!isDayOff(b.bucket, myShift)) {
      current = 0
    }
  }
  return best
}

function streakFlair(streak: number): string {
  if (streak >= 14) return '🏆'
  if (streak >= 7) return '⚡'
  if (streak >= 3) return '🔥'
  return ''
}

const GOOD_DAY_MESSAGES = [
  'Nice work today — keep the momentum going.',
  'Solid pace today. Your queue is feeling it.',
  "You're on a roll today — nicely done.",
]
const SLOW_DAY_MESSAGES = [
  "Quiet day so far — that's alright, tomorrow's a fresh start.",
  'Every ticket counts, even the tricky ones. Keep going.',
  "Not every day is a sprint. You've got this.",
]
const STREAK_MESSAGES = [
  "consecutive days closing tickets — that's real consistency.",
  "days in a row. Don't stop now!",
  'days running. Impressive discipline.',
]

function dayOfYear(): number {
  const now = new Date()
  const start = new Date(now.getFullYear(), 0, 0)
  return Math.floor((now.getTime() - start.getTime()) / 86_400_000)
}

function motivationalLine(streak: number, closedToday: number): string {
  const seed = dayOfYear()
  if (streak >= 7) return `${streak} ${STREAK_MESSAGES[seed % STREAK_MESSAGES.length]}`
  if (closedToday > 0) return GOOD_DAY_MESSAGES[seed % GOOD_DAY_MESSAGES.length]
  return SLOW_DAY_MESSAGES[seed % SLOW_DAY_MESSAGES.length]
}

function weekOverWeek(buckets: AnalyticsSummaryBucket[]): { thisWeek: number; lastWeek: number } | null {
  if (buckets.length < 8) return null
  const last7 = buckets.slice(-7)
  const prev7 = buckets.slice(-14, -7)
  if (prev7.length === 0) return null
  return {
    thisWeek: last7.reduce((s, b) => s + b.closed_count, 0),
    lastWeek: prev7.reduce((s, b) => s + b.closed_count, 0),
  }
}

export function Analytics() {
  const [period, setPeriod] = useState<Period>('day')
  const { data: summary, isLoading } = useAnalyticsSummary(period)
  const { data: allTickets } = useTickets({ page_size: 200, sort: 'num:desc' })
  const { data: settings } = useSettings()
  const { dark } = useDarkMode()
  const colors = dark ? PALETTE.dark : PALETTE.light
  const myShift = settings?.find((s) => s.key === 'my_shift_json')?.value as MyShift | undefined

  const totals = useMemo(() => {
    if (!summary) return null
    const closed = summary.reduce((s, b) => s + b.closed_count, 0)
    const reopened = summary.reduce((s, b) => s + b.reopened_count, 0)
    const custReopened = summary.reduce((s, b) => s + b.customer_reopened_count, 0)
    const respondSamples = summary.filter((b) => b.avg_time_to_respond_minutes != null)
    const finalCloseSamples = summary.filter((b) => b.avg_time_to_final_close_minutes != null)
    const avgRespond = respondSamples.length
      ? respondSamples.reduce((s, b) => s + (b.avg_time_to_respond_minutes ?? 0), 0) / respondSamples.length
      : null
    const avgFinal = finalCloseSamples.length
      ? finalCloseSamples.reduce((s, b) => s + (b.avg_time_to_final_close_minutes ?? 0), 0) / finalCloseSamples.length
      : null
    const reopenRate = closed > 0 ? (reopened / closed) * 100 : 0
    return { closed, reopened, custReopened, avgRespond, avgFinal, reopenRate }
  }, [summary])

  const typeBreakdown = useMemo(() => {
    if (!allTickets) return []
    const counts = new Map<string, number>()
    for (const t of allTickets.items) {
      const key = t.derived_type || 'Uncategorized'
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    return Array.from(counts.entries())
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count)
  }, [allTickets])

  const streak = summary && period === 'day' ? computeStreak(summary, myShift) : null
  const bestStreak = summary && period === 'day' ? computeBestStreak(summary, myShift) : null
  const wow = summary && period === 'day' ? weekOverWeek(summary) : null
  const closedToday = summary && period === 'day' && summary.length > 0 ? summary[summary.length - 1].closed_count : 0
  const tickStyle = { fontSize: 11, fill: colors.muted }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <h1 className="text-[28px] font-bold tracking-[-0.015em]">Analytics</h1>
        <Tabs value={period} onValueChange={(v) => setPeriod(v as Period)}>
          <TabsList>
            <TabsTrigger value="day">Day</TabsTrigger>
            <TabsTrigger value="month">Month</TabsTrigger>
            <TabsTrigger value="year">Year</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard label="Closed" value={String(totals?.closed ?? 0)} loading={isLoading} />
        <KpiCard label="Reopened" value={String(totals?.reopened ?? 0)} sub={`${totals?.custReopened ?? 0} by customer`} loading={isLoading} />
        <KpiCard label="Reopen rate" value={`${(totals?.reopenRate ?? 0).toFixed(0)}%`} loading={isLoading} />
        <KpiCard label="Avg. time to respond" value={formatMinutes(totals?.avgRespond)} loading={isLoading} />
        <KpiCard label="Avg. time to final close" value={formatMinutes(totals?.avgFinal)} loading={isLoading} />
      </div>

      {streak !== null && streak > 0 && (
        <Card>
          <CardContent className="flex flex-col gap-2 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-1">
              <span>
                {streakFlair(streak)} Current streak: <span className="font-tabular font-semibold">{streak}</span> consecutive day
                {streak === 1 ? '' : 's'} with at least one close
              </span>
              {bestStreak !== null && bestStreak > streak && (
                <span className="text-muted-foreground">
                  Best ever: <span className="font-tabular font-semibold text-foreground">{bestStreak}</span>
                </span>
              )}
              {wow && (
                <span className="text-muted-foreground">
                  This week: <span className="font-tabular font-semibold text-foreground">{wow.thisWeek}</span> vs last week{' '}
                  <span className="font-tabular font-semibold text-foreground">{wow.lastWeek}</span>
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground">{motivationalLine(streak, closedToday)}</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>Tickets closed per {period}</CardTitle>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ backgroundColor: colors.strong }} /> Fresh close
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ backgroundColor: colors.muted }} /> Re-close
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <ChartCardSkeleton height={280} />
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={summary}>
                <XAxis dataKey="bucket" tick={tickStyle} axisLine={{ stroke: colors.grid }} tickLine={false} />
                <YAxis allowDecimals={false} tick={tickStyle} axisLine={false} tickLine={false} />
                <RTooltip content={<ChartTooltip />} cursor={{ fill: colors.grid }} />
                <Bar dataKey="fresh_close_count" stackId="a" name="Fresh close" fill={colors.strong} radius={[0, 0, 0, 0]} />
                <Bar dataKey="reclose_count" stackId="a" name="Re-close" fill={colors.muted} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle>Reopens per {period}</CardTitle>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ backgroundColor: colors.indigo }} /> Reopened
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ backgroundColor: colors.red }} /> By customer reply
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <ChartCardSkeleton height={220} />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={summary}>
                <XAxis dataKey="bucket" tick={tickStyle} axisLine={{ stroke: colors.grid }} tickLine={false} />
                <YAxis allowDecimals={false} tick={tickStyle} axisLine={false} tickLine={false} />
                <RTooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="reopened_count" name="Reopened" stroke={colors.indigo} strokeWidth={2} dot={false} />
                <Line
                  type="monotone"
                  dataKey="customer_reopened_count"
                  name="By customer reply"
                  stroke={colors.red}
                  strokeWidth={2}
                  strokeDasharray="4 3"
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ticket type breakdown</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <ChartCardSkeleton height={160} />
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(160, typeBreakdown.length * 36)}>
              <BarChart data={typeBreakdown} layout="vertical" margin={{ left: 24 }}>
                <XAxis type="number" allowDecimals={false} tick={tickStyle} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="type" width={120} tick={tickStyle} axisLine={false} tickLine={false} />
                <RTooltip content={<ChartTooltip />} cursor={{ fill: colors.grid }} />
                <Bar dataKey="count" fill={colors.indigo} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
