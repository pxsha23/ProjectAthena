import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { LogoIcon } from '@/components/logo'
import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'
import { Button } from '@/components/ui/button'
import { INFO_PAGES } from '@/lib/site-config'
import NotFoundPage from './not-found-page'

/** Simple page for the Docs / About / legal links until their full content is written. */
export default function InfoPage({ slug }: { slug: string }) {
  const page = INFO_PAGES[slug]
  if (!page) return <NotFoundPage />

  return (
    <div className="flex min-h-dvh flex-col">
      <title>{`${page.title} | Athena`}</title>
      <SiteHeader />
      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-start px-4 py-24 sm:px-6">
        <LogoIcon size={40} />
        <h1 className="mt-6 text-4xl font-semibold tracking-tight">{page.title}</h1>
        <p className="mt-4 text-lg text-muted">{page.description}</p>
        <p className="mt-8 rounded-lg border border-border bg-panel px-4 py-3 text-sm text-subtle">
          This page is being written and will be filled in soon.
        </p>
        <Button asChild variant="secondary" className="mt-8">
          <Link to="/">
            <ArrowLeft aria-hidden="true" /> Back home
          </Link>
        </Button>
      </main>
      <SiteFooter />
    </div>
  )
}
