import { Check, Loader2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { STAGES, agentClasses } from '@/lib/agents'
import { cn } from '@/lib/utils'
import { useWorkspace } from './workspace-context'

/** Idea → Spec → Stack → Code → Export → Deploy. Click a reached stage to view it. */
export function PipelineStepper({ className }: { className?: string }) {
  const { view, setView, stageStatus, runningStage } = useWorkspace()
  const navRef = useRef<HTMLElement>(null)

  // On narrow screens the stepper scrolls; keep the selected stage visible.
  useEffect(() => {
    const nav = navRef.current
    const current = nav?.querySelector<HTMLElement>('[aria-current="step"]')
    if (!nav || !current) return
    const offset = current.getBoundingClientRect().left - nav.getBoundingClientRect().left + nav.scrollLeft
    const target = offset - (nav.clientWidth - current.offsetWidth) / 2
    nav.scrollTo({ left: Math.max(0, target), behavior: 'smooth' })
  }, [view])

  return (
    <nav ref={navRef} aria-label="Pipeline stages" className={cn('min-w-0 overflow-x-auto', className)}>
      <ol className="flex items-center gap-0.5">
        {STAGES.map((stage, index) => {
          const status = stageStatus(stage.id)
          const c = agentClasses(stage.agentId)
          const selected = view === stage.id
          const running = runningStage === stage.id
          const locked = status === 'pending' && !running

          return (
            <li key={stage.id} className="flex items-center">
              {index > 0 && (
                <span
                  aria-hidden="true"
                  className={cn('mx-0.5 h-px w-3 sm:w-4', status === 'pending' ? 'bg-border' : c.bg)}
                />
              )}
              <button
                type="button"
                onClick={() => setView(stage.id)}
                aria-current={selected ? 'step' : undefined}
                className={cn(
                  'flex cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium transition-colors',
                  selected ? cn('bg-raised', c.text) : 'text-muted hover:bg-raised/60 hover:text-text',
                  locked && !selected && 'text-subtle',
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'flex size-4 items-center justify-center rounded-full border text-[10px]',
                    status === 'done' && cn(c.bg, 'border-transparent text-on-accent'),
                    status === 'active' && cn(c.border, c.text),
                    status === 'pending' && 'border-border text-subtle',
                  )}
                >
                  {running ? (
                    <Loader2 className={cn('size-3 animate-spin', c.text)} />
                  ) : status === 'done' ? (
                    <Check className="size-2.5" strokeWidth={3} />
                  ) : (
                    index + 1
                  )}
                </span>
                {stage.label}
                <span className="sr-only">
                  {running ? '(in progress)' : status === 'done' ? '(done)' : status === 'active' ? '(current)' : '(not started)'}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
