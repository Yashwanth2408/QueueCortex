export type TicketStatus = 'OPEN' | 'PENDING' | 'CLOSED' | 'REJECTED' | 'BLOCKED'

export interface Customer {
  id: string
  email: string | null
  first_name: string | null
  last_name: string | null
  custom_fields: Record<string, unknown> | null
}

export interface TicketListItem {
  id: string
  num: number
  subject: string | null
  status: TicketStatus
  level: string | null
  tags_cache: string[] | null
  derived_type: string | null
  assigned_to_email: string | null
  customer: Customer | null
  last_event_at: string
  last_customer_message_at: string | null
  created_at_trinity: string
  trinity_url: string | null
  overwatch_status: string | null
  reopen_count: number
  last_close_at: string | null
  last_reopen_at: string | null
  needs_attention: boolean
  taken_from_me_count: number
  last_taken_from_me_at: string | null
  last_taken_from_me_reason: string | null
}

export interface TicketListResponse {
  items: TicketListItem[]
  total: number
  page: number
  page_size: number
}

export interface StatusTransition {
  id: number
  seq: number
  old_status: string | null
  new_status: string | null
  is_close: boolean
  is_reopen: boolean
  is_customer_triggered_reopen: boolean
  event_date: string
  agent_email: string | null
  created_at: string
}

export interface AssignmentEventOut {
  id: number
  seq: number
  action: 'assigned' | 'unassigned'
  old_assignee: string | null
  new_assignee: string | null
  is_gain_for_tracked_agent: boolean
  is_taken_from_tracked_agent: boolean
  is_system_action: boolean
  reason: string | null
  performed_by_email: string | null
  event_date: string
  created_at: string
}

export interface CsatEventOut {
  id: number
  action: string
  close_cycle_index: number | null
  created_at: string
}

export interface TicketDuplicateOut {
  id: number
  duplicate_of_num: number
  detected_at: string
}

export interface LocalNote {
  id: number
  ticket_id: string
  agent_email: string
  body: string
  created_at: string
  updated_at: string
}

export interface TicketDetail
  extends Omit<
    TicketListItem,
    'reopen_count' | 'last_close_at' | 'last_reopen_at' | 'needs_attention' | 'taken_from_me_count' | 'last_taken_from_me_at' | 'last_taken_from_me_reason'
  > {
  channel: string | null
  source: string | null
  team: string | null
  ticket_custom_fields: Record<string, unknown> | null
  thread_total_events: number | null
  thread_messages: number | null
  thread_notes: number | null
  updated_at_trinity: string
  first_assigned_to_agent_at: string | null
  added_to_tracker_at: string
  status_transitions: StatusTransition[]
  assignment_events: AssignmentEventOut[]
  csat_events: CsatEventOut[]
  duplicates: TicketDuplicateOut[]
  last_trinity_internal_note: string | null
  local_notes: LocalNote[]
}

export interface SyncStatus {
  last_full_backfill_at: string | null
  last_incremental_sync_at: string | null
  last_incremental_sync_status: string | null
  last_incremental_sync_error: string | null
  next_poll_at: string | null
  is_running: boolean
}

export interface SyncRun {
  id: number
  run_type: string
  started_at: string
  finished_at: string | null
  status: string
  tickets_checked: number
  tickets_updated: number
  events_ingested: number
  error_summary: string | null
}

export interface TagOut {
  tag_id: string
  label: string
  ticket_count: number
}

export interface TagMapping {
  tag_id: string
  type_label: string
  priority: number
}

export interface AnalyticsSummaryBucket {
  bucket: string
  closed_count: number
  fresh_close_count: number
  reclose_count: number
  reopened_count: number
  customer_reopened_count: number
  avg_time_to_respond_minutes: number | null
  avg_time_to_final_close_minutes: number | null
}

export type SettingValue = string | number | boolean | Record<string, unknown>

export interface Setting {
  key: string
  value: SettingValue
}

export interface RosterUploadResult {
  agents: number
  shift_rows: number
  date_range: (string | null)[]
}

export interface RosterAgentOut {
  email: string
  name: string
  role: string
  today_shift_code: string | null
  tomorrow_shift_code: string | null
}

export type ShiftReason = 'on_shift' | 'shift_ended' | 'off_day' | 'before_shift_start' | 'no_data'

export interface RosterOverdueTicket {
  id: string
  num: number
  derived_type: string | null
  assigned_to_email: string
  agent_name: string
  agent_role: string
  is_associate_or_trainer: boolean
  shift_code: string | null
  reason: ShiftReason
  held_since: string | null
  last_event_at: string
  trinity_url: string | null
  alert_tags: string[]
}
