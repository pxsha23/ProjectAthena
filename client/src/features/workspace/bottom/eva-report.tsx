import { CircleAlert, CircleCheck, CircleX, Loader2, Play, type LucideIcon } from 'lucide-react'
import { AgentAvatar } from '@/components/agent-badge'
import { Button } from '@/components/ui/button'
import type { EvaSeverity } from '@/lib/types'
import { cn, formatRelative } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'

const SEVERITY: Record<EvaSeverity, { icon: LucideIcon; className: string; label: string }> = {
  pass: { icon: CircleCheck, className: 'text-green', label: 'Passed' },
  warn: { icon: CircleAlert, className: 'text-yellow', label: 'Warning' },
  fail: { icon: CircleX, className: 'text-red', label: 'Failed' },
}

function scoreClass(score: number): string {
  if (score >= 85) return 'text-green'
  if (score >= 70) return 'text-yellow'
  return 'text-red'
}

export function EvaReport() {
  const { project, evaRunning, runEva, isReached, runs, runningStage } = useWorkspace()
  const eva = project.eva
  const lastRun = runs.find((r) => r.agent === 'eva' && r.status === 'succeeded')

  if (!isReached('code')) {
    return (
      <div className="flex h-full items-center justify-center gap-3 p-4 text-sm text-muted">
        <AgentAvatar agentId="eva" size="sm" />
        EVA tests your app with virtual users once code has been generated.
      </div>
    )
  }

  if (!eva) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-4 text-center text-sm text-muted">
        <AgentAvatar agentId="eva" size="md" />
        {evaRunning ? (
          <p role="status" className="flex items-center gap-2">
            <Loader2 className="size-4 animate-spin text-peach" aria-hidden="true" /> Alpha, Bravo and Charlie are
            walking through your app…
          </p>
        ) : (
          <>
            <p>EVA has not tested this version yet. It reads the code as three virtual users and reports issues.</p>
            <Button variant="secondary" size="sm" onClick={runEva} disabled={runningStage !== null}>
              <Play aria-hidden="true" /> Run EVA
            </Button>
          </>
        )}
      </div>
    )
  }

  const personaName = (id: string) => eva.personas.find((p) => p.id === id)?.name ?? 'User'

  return (
    <div className="grid h-full min-h-0 gap-4 overflow-y-auto p-4 md:grid-cols-[220px_1fr]">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-4">
          <div className="text-center">
            <p className={cn('text-4xl font-semibold tabular-nums', scoreClass(eva.score))}>{eva.score}</p>
            <p className="text-[11px] text-subtle">/ 100</p>
          </div>
          <div className="text-xs text-subtle">
            <p className="font-medium text-peach">EVA usability score</p>
            {lastRun && (
              <p>
                Last run {formatRelative(lastRun.startedAt)}
                {lastRun.model && <span className="block truncate">by {lastRun.model}</span>}
              </p>
            )}
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={runEva} disabled={runningStage !== null} className="justify-self-start">
          {evaRunning ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Play aria-hidden="true" />}
          {evaRunning ? 'Running personas…' : 'Re-run EVA'}
        </Button>
        <ul className="grid gap-2" aria-label="Virtual users">
          {eva.personas.map((persona) => (
            <li key={persona.id} className="rounded-md border border-border p-2 text-xs">
              <p className="font-medium text-text">
                {persona.name} <span className="font-normal text-subtle">· {persona.archetype}</span>
              </p>
              <p className="mt-0.5 text-muted">{persona.goal}</p>
            </li>
          ))}
        </ul>
      </div>

      <ul className="grid content-start gap-2" aria-label="Findings">
        {eva.findings.map((finding) => {
          const s = SEVERITY[finding.severity]
          const Icon = s.icon
          return (
            <li key={finding.id} className="flex gap-3 rounded-md border border-border bg-base/40 p-3">
              <Icon className={cn('mt-0.5 size-4 shrink-0', s.className)} aria-label={s.label} />
              <div className="min-w-0 text-sm">
                <p className="font-medium">{finding.title}</p>
                <p className="mt-0.5 text-muted">{finding.detail}</p>
                <p className="mt-1 text-xs text-subtle">Found by {personaName(finding.personaId)}</p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
