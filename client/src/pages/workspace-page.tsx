import { AlertCircle, RotateCw } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { FullPageLoader } from '@/components/full-page-loader'
import { Button } from '@/components/ui/button'
import { WorkspaceLayout } from '@/features/workspace/workspace-layout'
import { WorkspaceProvider } from '@/features/workspace/workspace-context'
import { ApiError } from '@/lib/api/client'
import { useProjectQuery } from '@/lib/api/queries'
import NotFoundPage from './not-found-page'

export default function WorkspacePage() {
  const { projectId = '' } = useParams<{ projectId: string }>()
  const query = useProjectQuery(projectId)

  if (query.isPending) return <FullPageLoader label="Opening project…" />
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 404) return <NotFoundPage />
    return (
      <main role="alert" className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
        <AlertCircle className="size-10 text-red" aria-hidden="true" />
        <h1 className="text-xl font-semibold">Could not open this project</h1>
        <p className="max-w-md text-muted">{query.error.message}</p>
        <div className="flex gap-2">
          <Button variant="secondary" asChild>
            <Link to="/dashboard">Back to projects</Link>
          </Button>
          <Button onClick={() => void query.refetch()}>
            <RotateCw aria-hidden="true" /> Try again
          </Button>
        </div>
      </main>
    )
  }

  const project = query.data
  return (
    // Keyed by id so switching projects resets all workspace state.
    <WorkspaceProvider key={project.id} project={project}>
      <title>{`${project.name} | Athena`}</title>
      <WorkspaceLayout />
    </WorkspaceProvider>
  )
}
