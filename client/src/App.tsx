import { QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { FullPageLoader } from '@/components/full-page-loader'
import { RedirectIfAuthed, RequireAuth } from '@/components/route-guards'
import { TooltipProvider } from '@/components/ui/tooltip'
import { queryClient } from '@/lib/api/queries'
import { ThemeProvider } from '@/lib/theme'
import { INFO_PAGES } from '@/lib/site-config'
import DashboardPage from '@/pages/dashboard-page'
import InfoPage from '@/pages/info-page'
import LandingPage from '@/pages/landing-page'
import LoginPage from '@/pages/login-page'
import NotFoundPage from '@/pages/not-found-page'
import SignupPage from '@/pages/signup-page'

// The workspace pulls in Monaco, so it is split into its own chunk.
const WorkspacePage = lazy(() => import('@/pages/workspace-page'))

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={300}>
          <BrowserRouter>
            <Suspense fallback={<FullPageLoader />}>
              <Routes>
                <Route path="/" element={<LandingPage />} />
                {Object.keys(INFO_PAGES).map((slug) => (
                  <Route key={slug} path={`/${slug}`} element={<InfoPage slug={slug} />} />
                ))}
                <Route element={<RedirectIfAuthed />}>
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/signup" element={<SignupPage />} />
                </Route>
                <Route element={<RequireAuth />}>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/project/:projectId" element={<WorkspacePage />} />
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
