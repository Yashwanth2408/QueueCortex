import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from '@/lib/api'
import type { Setting, SettingValue } from '@/types'

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: () => request<Setting[]>('/settings'),
  })
}

export function useUpdateSetting() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: SettingValue }) =>
      request<Setting>(`/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  })
}
