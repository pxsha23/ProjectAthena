import { Separator } from 'react-resizable-panels'
import { cn } from '@/lib/utils'

/** Thin 1px divider with a wider invisible hit area; lights up lavender on hover / drag / focus. */
export function ResizeHandle({ direction }: { direction: 'horizontal' | 'vertical' }) {
  return (
    <Separator
      className={cn(
        'relative shrink-0 bg-border outline-none transition-colors',
        'data-[separator=hover]:bg-lavender/60 data-[separator=active]:bg-lavender data-[separator=focus]:bg-lavender',
        direction === 'horizontal'
          ? 'w-px after:absolute after:inset-y-0 after:-left-1 after:w-2'
          : 'h-px after:absolute after:inset-x-0 after:-top-1 after:h-2',
      )}
    />
  )
}
