import type { ComponentProps, CSSProperties, MouseEvent } from 'react'
import { cn } from '@/lib/utils'

interface SpotlightProps extends ComponentProps<'div'> {
  /** CSS colour reference for the glow, e.g. var(--color-pink). Defaults to lavender. */
  color?: string
  /** Also brighten the element's border near the cursor. Needs a rounded, bordered element. */
  border?: boolean
  /** Glow radius in px. */
  size?: number
}

/**
 * Wraps any surface with a soft light that follows the pointer.
 * Only CSS variables change on mouse move, so it stays cheap to render.
 */
export function Spotlight({
  color = 'var(--color-lavender)',
  border = true,
  size = 420,
  className,
  style,
  children,
  onMouseMove,
  ...props
}: SpotlightProps) {
  function handleMove(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--mx', `${event.clientX - rect.left}px`)
    event.currentTarget.style.setProperty('--my', `${event.clientY - rect.top}px`)
    onMouseMove?.(event)
  }

  return (
    <div
      {...props}
      onMouseMove={handleMove}
      style={{ ...style, '--spot': color, '--spot-size': `${size}px` } as CSSProperties}
      className={cn('group/spot relative isolate', className)}
    >
      {/* Fill glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100"
        style={{
          background:
            'radial-gradient(var(--spot-size) circle at var(--mx, 50%) var(--my, 50%), color-mix(in oklab, var(--spot) 14%, transparent), transparent 65%)',
        }}
      />
      {/* Border glow: the same gradient, masked so only a 1px ring shows. */}
      {border && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -inset-px z-10 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover/spot:opacity-100"
          style={{
            padding: 1,
            background:
              'radial-gradient(calc(var(--spot-size) * 0.6) circle at var(--mx, 50%) var(--my, 50%), color-mix(in oklab, var(--spot) 75%, transparent), transparent 70%)',
            WebkitMask: 'linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)',
            WebkitMaskComposite: 'xor',
            mask: 'linear-gradient(#000 0 0) content-box exclude, linear-gradient(#000 0 0)',
          }}
        />
      )}
      {children}
    </div>
  )
}
