import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Input({ className, type = 'text', ...props }: ComponentProps<'input'>) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        'h-9 w-full min-w-0 rounded-md border border-border bg-raised px-3 text-sm text-text placeholder:text-subtle transition-colors',
        'focus-visible:border-lavender focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lavender/30',
        'aria-invalid:border-red aria-invalid:ring-red/30 disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}
