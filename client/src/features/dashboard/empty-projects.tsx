import { Plus } from 'lucide-react'
import { LogoIcon } from '@/components/logo'
import { Button } from '@/components/ui/button'

interface EmptyProjectsProps {
  hasQuery: boolean
  onCreate: () => void
  onClear: () => void
}

export function EmptyProjects({ hasQuery, onCreate, onClear }: EmptyProjectsProps) {
  return (
    <div className="flex flex-col items-center px-4 py-16 text-center">
      <LogoIcon size={48} className="text-subtle" />
      <h2 className="mt-4 font-semibold">{hasQuery ? 'No matching projects' : 'No projects here yet'}</h2>
      <p className="mt-1 max-w-sm text-sm text-muted">
        {hasQuery
          ? 'Try a different search or clear the filters.'
          : 'Describe an idea and the agents will take it from there.'}
      </p>
      <div className="mt-6">
        {hasQuery ? (
          <Button variant="secondary" onClick={onClear}>
            Clear filters
          </Button>
        ) : (
          <Button onClick={onCreate}>
            <Plus aria-hidden="true" /> New project
          </Button>
        )}
      </div>
    </div>
  )
}
