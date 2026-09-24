import { Link } from 'react-router-dom'
import { LogoIcon } from '@/components/logo'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <LogoIcon size={64} />
      <p className="font-mono text-sm text-peach">404</p>
      <h1 className="text-2xl font-semibold">This page flew away</h1>
      <p className="max-w-sm text-muted">The page you are looking for does not exist or was moved.</p>
      <Button asChild>
        <Link to="/">Back home</Link>
      </Button>
    </main>
  )
}
