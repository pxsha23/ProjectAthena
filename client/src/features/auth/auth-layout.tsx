import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { LogoIcon } from '@/components/logo'
import { Spotlight } from '@/components/spotlight'

interface AuthLayoutProps {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}

export function AuthLayout({ title, subtitle, children, footer }: AuthLayoutProps) {
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <Link to="/" aria-label="Athena home" className="rounded-md">
            <LogoIcon size={48} />
          </Link>
          <h1 className="mt-5 text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted">{subtitle}</p>
        </div>
        <Spotlight className="rounded-xl border border-border bg-panel p-6">{children}</Spotlight>
        <p className="mt-6 text-center text-sm text-muted">{footer}</p>
      </div>
    </main>
  )
}
