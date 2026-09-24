import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'
import { AgentsBento } from '@/features/landing/agents-bento'
import { Hero } from '@/features/landing/hero'
import { HowItWorks } from '@/features/landing/how-it-works'
import { WorkspaceShowcase } from '@/features/landing/workspace-showcase'

export default function LandingPage() {
  const { hash, key } = useLocation()

  // React Router doesn't scroll to #sections on navigation (e.g. footer links from other pages).
  useEffect(() => {
    if (!hash) return
    document.getElementById(hash.slice(1))?.scrollIntoView()
  }, [hash, key])

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Hero />
        <HowItWorks />
        <AgentsBento />
        <WorkspaceShowcase />
      </main>
      <SiteFooter />
    </div>
  )
}
