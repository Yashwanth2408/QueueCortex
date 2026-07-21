import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  length?: number
  value: string
  onChange: (value: string) => void
  onComplete?: (value: string) => void
  disabled?: boolean
  autoFocus?: boolean
}

export function OtpInput({ length = 4, value, onChange, onComplete, disabled, autoFocus }: Props) {
  const refs = useRef<(HTMLInputElement | null)[]>([])
  const digits = Array.from({ length }, (_, i) => value[i] ?? '')
  const [pulseIndex, setPulseIndex] = useState<number | null>(null)
  const [focusedIndex, setFocusedIndex] = useState<number | null>(null)

  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus()
  }, [autoFocus])

  const pulse = (index: number) => {
    setPulseIndex(index)
    setTimeout(() => setPulseIndex((cur) => (cur === index ? null : cur)), 400)
  }

  const setDigit = (index: number, digit: string) => {
    const next = digits.slice()
    next[index] = digit
    const joined = next.join('')
    onChange(joined)
    if (digit) pulse(index)
    if (joined.length === length && !joined.includes('')) onComplete?.(joined)
  }

  const handleChange = (index: number, raw: string) => {
    const cleaned = raw.replace(/\D/g, '')
    if (!cleaned) {
      setDigit(index, '')
      return
    }
    if (cleaned.length > 1) {
      // pasted a full code into one box
      const next = value.split('')
      for (let i = 0; i < cleaned.length && index + i < length; i++) {
        next[index + i] = cleaned[i]
      }
      const joined = next.join('').slice(0, length)
      onChange(joined)
      pulse(Math.min(index + cleaned.length, length) - 1)
      const lastFilled = Math.min(index + cleaned.length, length) - 1
      refs.current[Math.min(lastFilled + 1, length - 1)]?.focus()
      if (joined.length === length && !joined.includes('')) onComplete?.(joined)
      return
    }
    setDigit(index, cleaned)
    if (index < length - 1) refs.current[index + 1]?.focus()
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !digits[index] && index > 0) {
      refs.current[index - 1]?.focus()
    } else if (e.key === 'ArrowLeft' && index > 0) {
      refs.current[index - 1]?.focus()
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      refs.current[index + 1]?.focus()
    }
  }

  return (
    <div className="flex justify-center gap-3">
      {digits.map((digit, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          maxLength={length}
          value={digit}
          disabled={disabled}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onFocus={() => setFocusedIndex(i)}
          onBlur={() => setFocusedIndex((cur) => (cur === i ? null : cur))}
          className={cn(
            'font-tabular h-14 w-12 rounded-lg bg-secondary text-center text-2xl font-semibold text-foreground',
            'border-2 border-transparent outline-none transition-[transform,box-shadow,border-color] duration-150',
            'focus:border-foreground/20 focus:ring-2 focus:ring-ring',
            focusedIndex === i && 'scale-105',
            pulseIndex === i && 'animate-pulse-once',
            'disabled:opacity-50',
          )}
        />
      ))}
    </div>
  )
}
