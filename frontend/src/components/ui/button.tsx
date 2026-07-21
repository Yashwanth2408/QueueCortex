import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { motion } from 'motion/react'

import { cn } from '@/lib/utils'

const MotionButtonEl = motion.create('button')
const MotionSlotEl = motion.create(Slot)

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-ring",
  {
    variants: {
      variant: {
        default: 'rounded-full bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'rounded-full bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'rounded-md border border-border bg-transparent hover:bg-accent',
        secondary: 'rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/70',
        ghost: 'rounded-md hover:bg-accent',
        link: 'text-foreground underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 px-3 text-xs',
        lg: 'h-11 px-6',
        icon: 'h-9 w-9 rounded-full',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

type ButtonProps = Omit<React.ComponentProps<'button'>, 'onAnimationStart' | 'onAnimationEnd' | 'onDrag' | 'onDragStart' | 'onDragEnd'> &
  VariantProps<typeof buttonVariants> & { asChild?: boolean }

function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
  const MotionComp = asChild ? MotionSlotEl : MotionButtonEl
  return (
    <MotionComp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      whileTap={{ scale: 0.97 }}
      transition={{ duration: 0.09, ease: [0.2, 0, 0, 1] }}
      {...props}
    />
  )
}

export { Button, buttonVariants }
