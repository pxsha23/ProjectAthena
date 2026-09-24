import { cn, initials } from '@/lib/utils'

interface AvatarProps {
  name: string
  className?: string
}

/** Initials avatar. Accounts have no profile images. */
export function Avatar({ name, className }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-flex size-8 shrink-0 select-none items-center justify-center rounded-full border border-lavender/40 bg-lavender/15 text-xs font-semibold text-lavender',
        className,
      )}
    >
      {initials(name)}
    </span>
  )
}
