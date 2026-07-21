import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { OtpInput } from '@/components/auth/OtpInput'
import { useAuth } from '@/context/AuthContext'
import { ApiError, request } from '@/lib/api'

type Step = 'email' | 'otp'

export function Login() {
  const { setAuthed } = useAuth()
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [devCode, setDevCode] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const emailRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    emailRef.current?.focus()
  }, [])

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(t)
  }, [cooldown])

  const sendCode = async () => {
    setError(null)
    setLoading(true)
    try {
      const res = await request<{ sent: boolean; dev_code: string | null }>('/auth/request-otp', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim() }),
      })
      setDevCode(res.dev_code)
      setStep('otp')
      setCode('')
      setCooldown(20)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to send code')
    } finally {
      setLoading(false)
    }
  }

  const verifyCode = async (fullCode: string) => {
    setError(null)
    setLoading(true)
    try {
      const res = await request<{ ok: boolean; email: string }>('/auth/verify-otp', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), code: fullCode }),
      })
      setAuthed(res.email)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Verification failed')
      setCode('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="mb-8 flex flex-col items-center gap-2.5 text-center"
        >
          <div className="flex size-11 items-center justify-center rounded-2xl bg-foreground text-lg font-bold text-background">Q</div>
          <h1 className="text-[28px] font-bold tracking-[-0.02em]">QueueCortex</h1>
          <p className="text-sm text-muted-foreground">Sign in to your ticket dashboard</p>
        </motion.div>

        <div className="overflow-hidden rounded-2xl bg-card p-6 shadow-[0_24px_60px_-12px_rgba(0,0,0,0.35)] dark:border dark:border-border dark:shadow-[0_24px_60px_-12px_rgba(0,0,0,0.6)]">
          <AnimatePresence mode="wait" initial={false}>
            {step === 'email' ? (
              <motion.form
                key="email"
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col gap-4"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (email.trim()) sendCode()
                }}
              >
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="login-email">Email address</Label>
                  <Input
                    id="login-email"
                    ref={emailRef}
                    type="email"
                    autoComplete="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" disabled={loading || !email.trim()} className="mt-1 w-full">
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  Send code
                </Button>
              </motion.form>
            ) : (
              <motion.div
                key="otp"
                initial={{ opacity: 0, x: 12 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 12 }}
                transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col gap-5"
              >
                <button
                  onClick={() => {
                    setStep('email')
                    setError(null)
                  }}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
                >
                  <ArrowLeft className="size-3.5" /> Back
                </button>

                <div className="text-center">
                  <p className="text-sm text-muted-foreground">
                    Enter the 4-digit code sent to
                    <br />
                    <span className="font-medium text-foreground">{email}</span>
                  </p>
                </div>

                {devCode && (
                  <div className="bg-amber text-amber-foreground rounded-lg px-3 py-2 text-center text-xs">
                    Email delivery isn't configured yet — your code is <span className="font-tabular font-semibold">{devCode}</span>
                  </div>
                )}

                <OtpInput value={code} onChange={setCode} onComplete={verifyCode} disabled={loading} autoFocus />

                {error && <p className="text-center text-sm text-destructive">{error}</p>}

                <Button onClick={() => verifyCode(code)} disabled={loading || code.length !== 4} className="w-full">
                  {loading && <Loader2 className="size-4 animate-spin" />}
                  Verify & continue
                </Button>

                <button
                  onClick={sendCode}
                  disabled={cooldown > 0 || loading}
                  className="text-center text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                >
                  {cooldown > 0 ? `Resend code in ${cooldown}s` : 'Resend code'}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
