import { Check, Circle, Loader2 } from 'lucide-react'
import { AgentAvatar } from '@/components/agent-badge'
import { AGENTS, STAGES, agentClasses } from '@/lib/agents'
import { cn } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'
import { SidebarSection } from './sidebar-section'

export function PipelineOverview() {
  const { view, setView, stageStatus, runningStage } = useWorkspace()

  return (
    <SidebarSection title="Pipeline">
      <ol className="flex flex-col gap-0.5 px-2 pb-3">
        {STAGES.map((stage) => {
          const status = stageStatus(stage.id)
          const running = runningStage === stage.id
          const c = agentClasses(stage.agentId)
          return (
            <li key={stage.id}>
              <button
                type="button"
                onClick={() => setView(stage.id)}
                aria-current={view === stage.id ? 'step' : undefined}
                className={cn(
                  'flex w-full cursor-pointer items-start gap-3 rounded-md p-2 text-left transition-colors',
                  view === stage.id ? 'bg-raised' : 'hover:bg-raised/60',
                )}
              >
                <AgentAvatar agentId={stage.agentId} size="sm" className={cn(status === 'pending' && !running && 'opacity-50')} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className={cn('text-sm font-medium', status === 'pending' ? 'text-muted' : 'text-text')}>
                      {stage.label}
                    </span>
                    {running ? (
                      <Loader2 className={cn('size-3.5 animate-spin', c.text)} aria-label="In progress" />
                    ) : status === 'done' ? (
                      <Check className="size-3.5 text-green" aria-label="Done" />
                    ) : status === 'active' ? (
                      <Circle className={cn('size-2.5 fill-current', c.text)} aria-label="Current" />
                    ) : null}
                  </span>
                  <span className="block text-xs text-subtle">{stage.description}</span>
                  <span className={cn('mt-0.5 block text-[11px]', c.text)}>{AGENTS[stage.agentId].name}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </SidebarSection>
  )
}
