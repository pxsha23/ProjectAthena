import { ArrowRight, Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'
import { AgentAvatar } from '@/components/agent-badge'
import { Button } from '@/components/ui/button'
import { AGENTS, agentClasses, getStage } from '@/lib/agents'
import type { StageId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'

interface StageShellProps {
  stage: StageId
  children: ReactNode
}

/** Common header + scroll container for the non-editor stage views. */
export function StageShell({ stage, children }: StageShellProps) {
  const { stageStatus, nextStage, runNextStage, runningStage, canAdvance } = useWorkspace()
  const meta = getStage(stage)
  const agent = AGENTS[meta.agentId]
  const c = agentClasses(meta.agentId)
  const isCurrent = stageStatus(stage) === 'active'
  const next = nextStage ? getStage(nextStage) : null

  return (
    <div className="h-full overflow-y-auto bg-panel">
      <div className="mx-auto max-w-3xl px-4 py-8 sm:px-8">
        <header className="flex flex-wrap items-start gap-4">
          <AgentAvatar agentId={meta.agentId} size="lg" />
          <div className="min-w-0 flex-1">
            <p className={cn('text-xs font-medium', c.text)}>{agent.name}</p>
            <h2 className="text-2xl font-semibold tracking-tight">{meta.label}</h2>
            <p className="mt-1 text-sm text-muted">{meta.description}</p>
          </div>
          {isCurrent && next && (canAdvance || runningStage === next.id) && (
            <Button variant="ai" onClick={() => void runNextStage()} disabled={!canAdvance}>
              {runningStage ? <Loader2 className="animate-spin" aria-hidden="true" /> : <ArrowRight aria-hidden="true" />}
              Continue to {next.label}
            </Button>
          )}
        </header>
        <div className="mt-8">{children}</div>
      </div>
    </div>
  )
}
