import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Logo } from '@/components/logo'
import { MobileNav } from '@/components/mobile-nav'
import { SiteLink } from '@/components/site-link'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button } from '@/components/ui/button'
import { UserMenu } from '@/components/user-menu'
import { useAuth } from '@/lib/auth'
import { HEADER_LINKS } from '@/lib/site-config'
import { cn } from '@/lib/utils'

interface SiteHeaderProps {
  /** Marketing pages show section links; app pages don't. */
  variant?: 'marketing' | 'app'
  className?: string
}

/** True once the page has scrolled past a few pixels. */
function useScrolled(threshold = 8): boolean {
  const [scrolled, setScrolled] = useState(() => typeof window !== 'undefined' && window.scrollY > threshold)
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [threshold])
  return scrolled
}

export function SiteHeader({ variant = 'marketing', className }: SiteHeaderProps) {
  const { user } = useAuth()
  const scrolled = useScrolled()
  const marketing = variant === 'marketing'

  return (
    <header
      className={cn(
        'sticky top-0 z-40 border-b transition-[background-color,border-color,backdrop-filter] duration-300',
        scrolled || !marketing ? 'border-border bg-base/70 backdrop-blur-xl' : 'border-transparent bg-transparent',
        className,
      )}
    >
      <div className="relative mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Logo to={user ? '/dashboard' : '/'} />

        {marketing && (
          <nav aria-label="Main" className="absolute left-1/2 hidden -translate-x-1/2 md:block">
            <ul className="flex items-center gap-7 text-sm text-muted">
              {HEADER_LINKS.map((link) => (
                <li key={link.to}>
                  <SiteLink
                    link={link}
                    className="group relative rounded-sm py-1 transition-colors hover:text-text"
                  >
                    {link.label}
                    <span
                      aria-hidden="true"
                      className="absolute inset-x-0 -bottom-0.5 h-px origin-left scale-x-0 bg-lavender transition-transform duration-300 ease-out group-hover:scale-x-100 group-focus-visible:scale-x-100"
                    />
                  </SiteLink>
                </li>
              ))}
            </ul>
          </nav>
        )}

        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {user ? (
            <>
              {marketing && (
                <Button asChild variant="secondary" size="sm" className="hidden sm:inline-flex">
                  <Link to="/dashboard">Open dashboard</Link>
                </Button>
              )}
              <UserMenu />
            </>
          ) : (
            <>
              <Button asChild variant="ghost" size="sm" className={cn(marketing && 'hidden sm:inline-flex')}>
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild size="sm">
                <Link to="/signup">Get Started</Link>
              </Button>
            </>
          )}
          {marketing && <MobileNav />}
        </div>
      </div>
    </header>
  )
}
