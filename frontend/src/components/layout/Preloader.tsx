import { motion } from 'motion/react'
import logo from '@/assets/Gemini_Generated_Image_zbvogszbvogszbvo_bgremoved.png'

export function Preloader() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background">
      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="flex size-14 items-center justify-center rounded-2xl bg-foreground p-2.5"
      >
        <img src={logo} alt="" className="size-full object-contain dark:invert" />
      </motion.div>
      <motion.span
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
        className="text-[15px] font-semibold tracking-tight text-foreground"
      >
        QueueCortex
      </motion.span>
    </div>
  )
}
