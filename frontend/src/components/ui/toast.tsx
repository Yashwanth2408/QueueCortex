import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastVariant = 'success' | 'error' | 'info'

interface ToastInput {
  title: string
  description?: string
  variant?: ToastVariant
}

interface ToastItem extends ToastInput {
  id: number
}

interface ToastContextValue {
  toast: (input: ToastInput) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS: Record<ToastVariant, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const AUTO_DISMISS_MS: Record<ToastVariant, number | null> = {
  success: 3000,
  info: 3000,
  error: null,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<ToastItem | null>(null)
  const queueRef = useRef<ToastItem[]>([])
  const idRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const advance = useCallback(() => {
    const next = queueRef.current.shift() ?? null
    setCurrent(next)
  }, [])

  const dismiss = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    advance()
  }, [advance])

  const toast = useCallback((input: ToastInput) => {
    const item: ToastItem = { id: idRef.current++, variant: 'info', ...input }
    queueRef.current.push(item)
    setCurrent((existing) => (existing ? existing : queueRef.current.shift() ?? null))
  }, [])

  useEffect(() => {
    if (!current) return
    const ms = AUTO_DISMISS_MS[current.variant ?? 'info']
    if (ms == null) return
    timerRef.current = setTimeout(() => advance(), ms)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [current, advance])

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed top-16 left-1/2 z-[100] -translate-x-1/2">
        <AnimatePresence>
          {current && (
            <motion.div
              key={current.id}
              initial={{ opacity: 0, y: -12, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ type: 'spring', stiffness: 400, damping: 28 }}
              className={cn(
                'pointer-events-auto flex max-w-sm items-start gap-2.5 rounded-xl border border-border bg-popover/90 px-4 py-3 text-sm backdrop-blur-xl backdrop-saturate-150',
                'shadow-[0_8px_24px_-6px_rgba(0,0,0,0.25)]',
              )}
            >
              {(() => {
                const Icon = ICONS[current.variant ?? 'info']
                const iconColor =
                  current.variant === 'success'
                    ? 'text-green-foreground'
                    : current.variant === 'error'
                      ? 'text-destructive'
                      : 'text-muted-foreground'
                return <Icon className={cn('mt-0.5 size-4 shrink-0', iconColor)} />
              })()}
              <div className="flex-1">
                <p className="font-medium text-foreground">{current.title}</p>
                {current.description && <p className="mt-0.5 text-xs text-muted-foreground">{current.description}</p>}
              </div>
              <button
                onClick={dismiss}
                className="shrink-0 rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <X className="size-3.5" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx.toast
}
