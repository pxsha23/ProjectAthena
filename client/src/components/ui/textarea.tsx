import type { ComponentProps } from 'react'
import { cn } from '@/lib/utils'

export function Textarea({ className, ...props }: ComponentProps<'textarea'>) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        'min-h-20 w-full resize-none rounded-md border border-border bg-raised px-3 py-2 text-sm text-text placeholder:text-subtle transition-colors',
        'focus-visible:border-lavender focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lavender/30',
        'aria-invalid:border-red disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}
