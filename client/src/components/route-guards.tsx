import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { FullPageLoader } from '@/components/full-page-loader'
import { useAuth } from '@/lib/auth'

interface FromState {
  from?: string
}

/** Only signed-in users can see these routes. */
export function RequireAuth() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <FullPageLoader label="Checking your session…" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}

/**
 * Signed-in users skip the login / signup pages.
 * This also handles the redirect right after a successful sign-in,
 * sending the user back to the page they originally asked for.
 */
export function RedirectIfAuthed() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  if (isLoading) return <FullPageLoader />
  if (user) {
    const from = (location.state as FromState | null)?.from
    return <Navigate to={from?.startsWith('/') ? from : '/dashboard'} replace />
  }
  return <Outlet />
}
