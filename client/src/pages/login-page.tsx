import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { AuthLayout } from '@/features/auth/auth-layout'
import { FormError } from '@/features/auth/form-error'
import { FormField } from '@/features/auth/form-field'
import { GithubSignIn, githubErrorMessage } from '@/features/auth/github-button'
import { useAuth } from '@/lib/auth'

export default function LoginPage() {
  const { login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    // RedirectIfAuthed navigates as soon as the session exists.
    login.mutate({ email, password })
  }

  const error = login.error?.message ?? githubErrorMessage(location.search)

  return (
    <AuthLayout
      title="Welcome back"
      subtitle="Sign in to continue to your projects."
      footer={
        <>
          New to Athena?{' '}
          <Link to="/signup" state={location.state} className="font-medium text-lavender hover:underline">
            Create an account
          </Link>
        </>
      }
    >
      <GithubSignIn disabled={login.isPending} />
      <form onSubmit={handleSubmit} className="grid gap-4">
        <FormField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <FormField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError message={error} />
        <Button type="submit" disabled={login.isPending}>
          {login.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
          Sign in
        </Button>
      </form>
    </AuthLayout>
  )
}
