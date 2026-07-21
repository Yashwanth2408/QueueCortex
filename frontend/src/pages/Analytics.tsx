import { useMemo, useState } from 'react'
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/ui/skeleton'
import { useAnalyticsSummary } from '@/hooks/useAnalytics'
import { useTickets } from '@/hooks/useTickets'
import { useDarkMode } from '@/context/DarkModeContext'
import { formatMinutes } from '@/lib/format'

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

function computeStreak(buckets: { bucket: string; closed_count: number }[]): number {
  let streak = 0
  for (let i = buckets.length - 1; i >= 0; i--) {
    if (buckets[i].closed_count > 0) streak++
    else break
  }
  return streak
}

export function Analytics() {
  const [period, setPeriod] = useState<Period>('day')
  const { data: summary, isLoading } = useAnalyticsSummary(period)
  const { data: allTickets } = useTickets({ page_size: 200, sort: 'num:desc' })
  const { dark } = useDarkMode()
  const colors = dark ? PALETTE.dark : PALETTE.light

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

  const streak = summary && period === 'day' ? computeStreak(summary) : null
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
          <CardContent className="py-3 text-sm">
            🔥 Current streak: <span className="font-tabular font-semibold">{streak}</span> consecutive day{streak === 1 ? '' : 's'} with at
            least one close
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
