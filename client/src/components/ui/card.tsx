import type { ComponentProps } from 'react'
import { Spotlight } from '@/components/spotlight'
import { cn } from '@/lib/utils'

interface CardProps extends ComponentProps<'div'> {
  /** Adds the cursor-following light. Pass a CSS colour such as var(--color-green), or true for lavender. */
  spotlight?: string | boolean
}

export function Card({ className, spotlight, ...props }: CardProps) {
  const classes = cn('rounded-lg border border-border bg-panel', className)
  if (spotlight) {
    return (
      <Spotlight
        data-slot="card"
        color={typeof spotlight === 'string' ? spotlight : undefined}
        className={classes}
        {...props}
      />
    )
  }
  return <div data-slot="card" className={classes} {...props} />
}

export function CardHeader({ className, ...props }: ComponentProps<'div'>) {
  return <div data-slot="card-header" className={cn('flex flex-col gap-1.5 p-5', className)} {...props} />
}

export function CardTitle({ className, ...props }: ComponentProps<'h3'>) {
  return <h3 data-slot="card-title" className={cn('font-semibold leading-tight text-text', className)} {...props} />
}

export function CardDescription({ className, ...props }: ComponentProps<'p'>) {
  return <p data-slot="card-description" className={cn('text-sm text-muted', className)} {...props} />
}

export function CardContent({ className, ...props }: ComponentProps<'div'>) {
  return <div data-slot="card-content" className={cn('px-5 pb-5', className)} {...props} />
}

export function CardFooter({ className, ...props }: ComponentProps<'div'>) {
  return <div data-slot="card-footer" className={cn('flex items-center px-5 pb-5', className)} {...props} />
}
