import { GitBranch, Loader2, CircleCheck } from 'lucide-react'
import { AGENTS, agentClasses } from '@/lib/agents'
import { cn } from '@/lib/utils'
import { useWorkspace } from './workspace-context'

export function StatusBar() {
  const { runningAgent, evaRunning, view, activeFile, fileIndex, cursor, dirty } = useWorkspace()
  const busyAgent = runningAgent ?? (evaRunning ? 'eva' : null)
  const file = view === 'code' && activeFile ? fileIndex.get(activeFile) : undefined

  return (
    <footer className="flex h-6 shrink-0 items-center gap-4 border-t border-border bg-base px-3 text-[11px] text-subtle">
      <span className="flex items-center gap-1">
        <GitBranch className="size-3" aria-hidden="true" /> main
      </span>
      <span role="status" className="flex items-center gap-1">
        {busyAgent ? (
          <>
            <Loader2 className={cn('size-3 animate-spin', agentClasses(busyAgent).text)} aria-hidden="true" />
            {AGENTS[busyAgent].name} working…
          </>
        ) : (
          <>
            <CircleCheck className="size-3 text-green" aria-hidden="true" /> Agents idle
          </>
        )}
      </span>
      {dirty.size > 0 && <span className="text-peach">{dirty.size} unsaved</span>}
      {file && (
        <span className="ml-auto hidden items-center gap-4 sm:flex">
          <span>
            Ln {cursor.line}, Col {cursor.column}
          </span>
          <span>Spaces: 2</span>
          <span>UTF-8</span>
          <span className="capitalize">{file.language}</span>
        </span>
      )}
    </footer>
  )
}
