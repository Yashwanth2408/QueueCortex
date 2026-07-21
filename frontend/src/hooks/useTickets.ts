import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { request } from '@/lib/api'
import type { LocalNote, TicketDetail, TicketListResponse } from '@/types'

export interface TicketFilters {
  status?: string
  level?: string
  derived_type?: string
  tag?: string
  assigned_to?: string
  search?: string
  needs_attention?: boolean
  closed_today?: boolean
  taken_from_me?: boolean
  sort?: string
  page?: number
  page_size?: number
}

function buildQuery(filters: TicketFilters): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  })
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export function useTickets(filters: TicketFilters) {
  return useQuery({
    queryKey: ['tickets', filters],
    queryFn: () => request<TicketListResponse>(`/tickets${buildQuery(filters)}`),
    placeholderData: (prev) => prev,
  })
}

export interface StatusCounts {
  open: number
  pending: number
  closed: number
  rejected: number
  blocked: number
  escalated: number
  unassigned: number
  closed_today: number
  fresh_closed_today: number
  reclosed_today: number
  reopened_today: number
  customer_reopened_today: number
  needs_attention: number
  taken_from_me: number
}

export function useStatusCounts() {
  return useQuery({
    queryKey: ['status-counts'],
    queryFn: () => request<StatusCounts>('/tickets/status-counts'),
    refetchInterval: 60_000,
  })
}

export function useNeedsAttention() {
  return useQuery({
    queryKey: ['needs-attention'],
    queryFn: () => request<TicketListResponse>('/queue/needs-attention'),
  })
}

export function useTicketDetail(ticketId: string | null) {
  return useQuery({
    queryKey: ['ticket', ticketId],
    queryFn: () => request<TicketDetail>(`/tickets/${ticketId}`),
    enabled: !!ticketId,
  })
}

export function useAddTicketByNumber() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (num: number) => request<TicketDetail>('/tickets/by-number', { method: 'POST', body: JSON.stringify({ num }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tickets'] })
      qc.invalidateQueries({ queryKey: ['needs-attention'] })
    },
  })
}

export function useComments(ticketId: string) {
  return useQuery({
    queryKey: ['comments', ticketId],
    queryFn: () => request<LocalNote[]>(`/tickets/${ticketId}/comments`),
    enabled: !!ticketId,
  })
}

export function useAddComment(ticketId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: string) =>
      request<LocalNote>(`/tickets/${ticketId}/comments`, { method: 'POST', body: JSON.stringify({ body }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments', ticketId] })
      qc.invalidateQueries({ queryKey: ['ticket', ticketId] })
      qc.invalidateQueries({ queryKey: ['roster-ticket', ticketId] })
    },
  })
}

export function useDeleteComment(ticketId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (commentId: number) => request<void>(`/comments/${commentId}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['comments', ticketId] })
      qc.invalidateQueries({ queryKey: ['ticket', ticketId] })
      qc.invalidateQueries({ queryKey: ['roster-ticket', ticketId] })
    },
  })
}
