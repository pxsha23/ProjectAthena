import { AlertCircle, X } from 'lucide-react'
import { useWorkspace } from './workspace-context'

/** Shows the last stage failure reported by the server until dismissed. */
export function RunErrorBanner() {
  const { runError, dismissRunError, setBottomTab } = useWorkspace()
  if (!runError) return null
  return (
    <div role="alert" className="flex shrink-0 items-start gap-2 border-b border-red/30 bg-red/10 px-3 py-2 text-sm text-red">
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <p className="min-w-0 flex-1">
        <span className="font-medium">The agent run failed.</span> {runError}{' '}
        <button type="button" onClick={() => setBottomTab('output')} className="cursor-pointer underline underline-offset-2">
          See output
        </button>
      </p>
      <button
        type="button"
        onClick={dismissRunError}
        aria-label="Dismiss error"
        className="cursor-pointer rounded-sm p-0.5 hover:bg-red/15"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  )
}
