import { ArrowUp, Mail } from 'lucide-react'
import type { ReactNode } from 'react'
import { GithubIcon, LinkedinIcon } from '@/components/icons'
import { Logo } from '@/components/logo'
import { SiteLink } from '@/components/site-link'
import { ThemeToggle } from '@/components/theme-toggle'
import { FOOTER_COLUMNS, SOCIAL_LINKS } from '@/lib/site-config'

const SOCIALS: { label: string; href: string; icon: ReactNode; external: boolean }[] = [
  { label: 'GitHub', href: SOCIAL_LINKS.github, icon: <GithubIcon className="size-4" aria-hidden="true" />, external: true },
  { label: 'LinkedIn', href: SOCIAL_LINKS.linkedin, icon: <LinkedinIcon className="size-4" aria-hidden="true" />, external: true },
  { label: 'Email', href: `mailto:${SOCIAL_LINKS.email}`, icon: <Mail className="size-4" aria-hidden="true" />, external: false },
]

export function SiteFooter() {
  return (
    <footer className="relative overflow-hidden border-t border-border bg-panel/40">
      <div className="mx-auto max-w-6xl px-4 pt-16 sm:px-6">
        <div className="grid gap-12 lg:grid-cols-[1.3fr_2fr]">
          {/* Brand */}
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed text-muted">
              Athena turns a one-line app idea into deployed code with a team of AI agents.
              <br />
              Every step is explained, so you learn as you build.
            </p>
            <ul className="mt-6 flex items-center gap-2" aria-label="Social links">
              {SOCIALS.map((s) => (
                <li key={s.label}>
                  <a
                    href={s.href}
                    aria-label={s.label}
                    {...(s.external ? { target: '_blank', rel: 'noreferrer' } : {})}
                    className="flex size-9 items-center justify-center rounded-md border border-border text-muted transition-colors hover:border-subtle hover:bg-raised hover:text-text"
                  >
                    {s.icon}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Link columns */}
          <div className="grid grid-cols-2 gap-10 sm:grid-cols-4">
            {FOOTER_COLUMNS.map((column) => (
              <div key={column.title}>
                <h2 className="font-mono text-xs tracking-widest text-subtle uppercase">{column.title}</h2>
                <ul className="mt-4 space-y-2.5 text-sm">
                  {column.links.map((link) => (
                    <li key={link.label}>
                      <SiteLink link={link} className="rounded-sm text-muted transition-colors hover:text-text" />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div className="mt-16 flex flex-col gap-4 border-t border-border py-6 text-sm text-subtle md:flex-row md:items-center">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>&copy; {new Date().getFullYear()} Athena</span>
            <span className="hidden h-3 w-px bg-border sm:inline-block" aria-hidden="true" />
            <span>Built as a final year project</span>
          </p>
          <div className="flex flex-wrap items-center gap-3 md:ml-auto">
            <span className="inline-flex items-center gap-2 text-xs">
              <span className="relative flex size-2" aria-hidden="true">
                <span className="absolute inset-0 animate-ping rounded-full bg-green/60" />
                <span className="relative size-2 rounded-full bg-green" />
              </span>
              All systems normal
            </span>
            <span className="h-4 w-px bg-border" aria-hidden="true" />
            <ThemeToggle />
            <button
              type="button"
              onClick={() => window.scrollTo({ top: 0 })}
              className="inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors hover:bg-raised hover:text-text"
            >
              <ArrowUp className="size-3.5" aria-hidden="true" /> Back to top
            </button>
          </div>
        </div>
      </div>

      {/* Oversized wordmark fading into the page. */}
      <p
        aria-hidden="true"
        className="pointer-events-none -mb-[0.26em] bg-linear-to-b from-raised to-transparent bg-clip-text text-center text-[19vw] leading-none font-semibold tracking-tighter text-transparent select-none"
      >
        ATHENA
      </p>
    </footer>
  )
}
