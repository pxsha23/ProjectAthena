import { Loader2 } from 'lucide-react'
import { useState } from 'react'
import { GithubIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { useAuth, useAuthProviders } from '@/lib/auth'

/**
 * "Continue with GitHub" plus the divider below it.
 * Renders nothing when the server has no GitHub OAuth app configured.
 */
export function GithubSignIn({ disabled }: { disabled?: boolean }) {
  const { loginWithGithub } = useAuth()
  const providers = useAuthProviders()
  const [redirecting, setRedirecting] = useState(false)

  if (!providers.data?.github) return null

  return (
    <>
      <Button
        variant="secondary"
        className="w-full"
        disabled={disabled || redirecting}
        onClick={() => {
          setRedirecting(true)
          loginWithGithub()
        }}
      >
        {redirecting ? <Loader2 className="animate-spin" aria-hidden="true" /> : <GithubIcon aria-hidden="true" />}
        Continue with GitHub
      </Button>
      <div className="my-5 flex items-center gap-3 text-xs text-subtle" role="separator">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
    </>
  )
}

const GITHUB_ERRORS: Record<string, string> = {
  github_state: 'GitHub sign-in expired or was started in another tab. Please try again.',
  github_failed: 'GitHub sign-in did not complete. Please try again.',
}

export function githubErrorMessage(search: string): string | null {
  const code = new URLSearchParams(search).get('error')
  return code ? (GITHUB_ERRORS[code] ?? 'Sign-in failed. Please try again.') : null
}
