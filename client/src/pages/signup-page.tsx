import { Loader2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { AuthLayout } from '@/features/auth/auth-layout'
import { FormError } from '@/features/auth/form-error'
import { FormField } from '@/features/auth/form-field'
import { GithubSignIn } from '@/features/auth/github-button'
import { useAuth } from '@/lib/auth'

export default function SignupPage() {
  const { signup } = useAuth()
  const location = useLocation()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    signup.mutate({ name, email, password })
  }

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Start turning ideas into deployed apps."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" state={location.state} className="font-medium text-lavender hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <GithubSignIn disabled={signup.isPending} />
      <form onSubmit={handleSubmit} className="grid gap-4">
        <FormField
          id="name"
          label="Full name"
          autoComplete="name"
          required
          maxLength={120}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
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
          autoComplete="new-password"
          required
          minLength={8}
          hint="At least 8 characters."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError message={signup.error?.message ?? null} />
        <Button type="submit" disabled={signup.isPending}>
          {signup.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
