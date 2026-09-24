import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { SiteLink as SiteLinkData } from '@/lib/site-config'

interface SiteLinkProps {
  link: SiteLinkData
  className?: string
  children?: ReactNode
  onClick?: () => void
}

/** Renders a config link as a router Link, or a new-tab anchor for external URLs. */
export function SiteLink({ link, className, children, onClick }: SiteLinkProps) {
  if (link.external) {
    return (
      <a href={link.to} target="_blank" rel="noreferrer" className={className} onClick={onClick}>
        {children ?? link.label}
        <span className="sr-only"> (opens in a new tab)</span>
      </a>
    )
  }
  return (
    <Link to={link.to} className={className} onClick={onClick}>
      {children ?? link.label}
    </Link>
  )
}
