import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from '@/lib/api'
import type { SyncRun, SyncStatus } from '@/types'

export function useSyncStatus() {
  return useQuery({
    queryKey: ['sync-status'],
    queryFn: () => request<SyncStatus>('/sync/status'),
    refetchInterval: 30_000,
  })
}

export function useTriggerSync() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mode: 'incremental' | 'full') =>
      request<{ sync_run_id: number }>('/sync/run', { method: 'POST', body: JSON.stringify({ mode }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sync-status'] })
    },
  })
}

export function useSyncRun(runId: number | null) {
  return useQuery({
    queryKey: ['sync-run', runId],
    queryFn: () => request<SyncRun>(`/sync/runs/${runId}`),
    enabled: !!runId,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 2000 : false),
  })
}
