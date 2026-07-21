import { useQuery } from '@tanstack/react-query'
import { request } from '@/lib/api'
import type { AnalyticsSummaryBucket } from '@/types'

export function useAnalyticsSummary(period: 'day' | 'month' | 'year', from?: string, to?: string) {
  const params = new URLSearchParams({ period })
  if (from) params.set('from', from)
  if (to) params.set('to', to)
  return useQuery({
    queryKey: ['analytics-summary', period, from, to],
    queryFn: () => request<AnalyticsSummaryBucket[]>(`/analytics/summary?${params.toString()}`),
  })
}
