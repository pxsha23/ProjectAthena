import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

/**
 * Athena's mark: a minimal geometric owl whose eyes are code brackets { }.
 * Drawn on a 24px grid so it stays crisp at 24px. The stroke does not scale with
 * the icon; it steps up with size instead, so lines stay thin at every size.
 */
const OWL_PATHS = [
  // Head and body with ear tufts
  'M4.75 2.75 L8.5 6 H15.5 L19.25 2.75 L20.25 10 V14 Q20.25 21.25 12 21.25 Q3.75 21.25 3.75 14 V10 Z',
  // Brow: the V that makes it read as an owl
  'M6.75 7.9 L12 10 L17.25 7.9',
  // Left eye {
  'M9.75 10.25 Q8.25 10.25 8.25 11.6 V12.1 Q8.25 12.85 7.25 12.85 Q8.25 12.85 8.25 13.6 V14.1 Q8.25 15.5 9.75 15.5',
  // Right eye }
  'M14.25 10.25 Q15.75 10.25 15.75 11.6 V12.1 Q15.75 12.85 16.75 12.85 Q15.75 12.85 15.75 13.6 V14.1 Q15.75 15.5 14.25 15.5',
  // Beak
  'M11 16.75 L12 18.25 L13 16.75',
]

/** Stroke width in screen pixels for a given icon size. */
function strokeFor(size: number): number {
  if (size <= 32) return 1.5
  if (size <= 80) return 2
  return 2.5
}

interface LogoIconProps {
  /** Rendered width and height in px. */
  size?: number
  className?: string
  /** Accessible name. Omit when the icon is decorative or labelled by nearby text. */
  title?: string
}

/** Icon-only logo. Colour comes from `currentColor` (lavender by default). */
export function LogoIcon({ size = 24, className, title }: LogoIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeFor(size)}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn('shrink-0 text-lavender', className)}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {OWL_PATHS.map((d) => (
        <path key={d} d={d} vectorEffect="non-scaling-stroke" />
      ))}
    </svg>
  )
}

interface LogoProps {
  className?: string
  /** Icon size in px; the wordmark scales with it. */
  size?: number
  /** Wrap in a link. Pass null to render without one. */
  to?: string | null
}

/** Icon + "Athena" wordmark. */
export function Logo({ className, size = 28, to = '/' }: LogoProps) {
  const content = (
    <>
      <LogoIcon size={size} />
      <span className="font-semibold tracking-tight text-text" style={{ fontSize: Math.round(size * 0.66) }}>
        Athena
      </span>
    </>
  )
  const classes = cn('inline-flex items-center gap-2 rounded-md', className)

  if (to === null) return <span className={classes}>{content}</span>
  return (
    <Link to={to} className={classes} aria-label="Athena home">
      {content}
    </Link>
  )
}
