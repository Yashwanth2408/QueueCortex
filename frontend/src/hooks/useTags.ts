import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from '@/lib/api'
import type { TagMapping, TagOut } from '@/types'

export function useTags() {
  return useQuery({
    queryKey: ['tags'],
    queryFn: () => request<TagOut[]>('/tags'),
  })
}

export function useTagMappings() {
  return useQuery({
    queryKey: ['tag-mappings'],
    queryFn: () => request<TagMapping[]>('/tag-mappings'),
  })
}

export function useSaveTagMappings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mappings: TagMapping[]) =>
      request<TagMapping[]>('/tag-mappings', { method: 'PUT', body: JSON.stringify(mappings) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tag-mappings'] })
      qc.invalidateQueries({ queryKey: ['tickets'] })
    },
  })
}
