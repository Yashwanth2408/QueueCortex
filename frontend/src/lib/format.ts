import { formatDistanceToNowStrict } from 'date-fns'

/** Trinity/backend timestamps are naive-UTC ISO strings with up to 6-digit
 * microseconds and no offset (e.g. "2026-07-20T14:02:45.494000"). JS Date
 * parses bare ISO datetimes as *local* time, and chokes on >3 fractional
 * digits, so normalize to milliseconds + explicit Z before parsing. */
function toJsDate(iso: string): Date {
  const hasOffset = /[+-]\d{2}:\d{2}$|Z$/.test(iso)
  const truncated = iso.replace(/(\.\d{3})\d*$/, '$1')
  return new Date(hasOffset ? truncated : `${truncated}Z`)
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return `${formatDistanceToNowStrict(toJsDate(iso))} ago`
}

export function absoluteTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return toJsDate(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes == null) return '—'
  const totalMinutes = Math.round(minutes)
  const days = Math.floor(totalMinutes / 1440)
  const hours = Math.floor((totalMinutes % 1440) / 60)
  const mins = totalMinutes % 60
  const parts: string[] = []
  if (days) parts.push(`${days}d`)
  if (hours) parts.push(`${hours}h`)
  if (!days && mins) parts.push(`${mins}m`)
  return parts.length ? parts.join(' ') : '<1m'
}

export { toJsDate }
