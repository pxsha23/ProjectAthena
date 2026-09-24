import { cva, type VariantProps } from 'class-variance-authority'
import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export const badgeVariants = cva(
  'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium [&_svg]:size-3',
  {
    variants: {
      tone: {
        neutral: 'border-border bg-raised text-muted',
        lavender: 'border-lavender/30 bg-lavender/10 text-lavender',
        mauve: 'border-mauve/30 bg-mauve/10 text-mauve',
        green: 'border-green/30 bg-green/10 text-green',
        peach: 'border-peach/30 bg-peach/10 text-peach',
        red: 'border-red/30 bg-red/10 text-red',
        sky: 'border-sky/30 bg-sky/10 text-sky',
        yellow: 'border-yellow/30 bg-yellow/10 text-yellow',
        pink: 'border-pink/30 bg-pink/10 text-pink',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
)

export interface BadgeProps extends ComponentProps<'span'>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span data-slot="badge" className={cn(badgeVariants({ tone }), className)} {...props} />
}
