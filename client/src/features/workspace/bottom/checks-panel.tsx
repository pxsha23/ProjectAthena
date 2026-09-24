import { CircleAlert, CircleCheck, CircleX, ShieldCheck } from 'lucide-react'
import type { ConsistencyCheck } from '@/lib/types'
import { cn, formatRelative } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'

const STAGE_LABEL: Record<string, string> = {
  idea: 'Spec',
  stack: 'Tech Stack',
  code: 'Code',
  deploy: 'Deploy',
}

/** Keeps only the most recent result of each check (the list arrives newest first). */
export function latestChecks(checks: ConsistencyCheck[]): ConsistencyCheck[] {
  const seen = new Set<string>()
  return checks.filter((c) => {
    const key = `${c.stage}:${c.checkName}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function humanize(name: string): string {
  return name.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

/** Lines of detail worth showing for a failed check (errors, missing packages, lint problems). */
function detailLines(check: ConsistencyCheck): string[] {
  const d = check.details as Record<string, unknown>
  const lines: string[] = []
  for (const key of ['errors', 'missing', 'problems'] as const) {
    const items = d[key]
    if (!Array.isArray(items)) continue
    for (const item of items.slice(0, 8)) {
      if (typeof item === 'string') lines.push(item)
      else if (item && typeof item === 'object') {
        const i = item as Record<string, unknown>
        const where = [i.file, i.line].filter(Boolean).join(':')
        const what = i.error ?? (i.package ? `missing package ${String(i.package)}` : undefined) ?? i.import
        lines.push([where, what].filter(Boolean).join(' '))
      }
    }
  }
  return lines
}

export function ChecksPanel() {
  const { checks } = useWorkspace()
  const latest = latestChecks(checks)

  if (latest.length === 0) {
    return (
      <div className="flex h-full items-center justify-center gap-3 p-4 text-sm text-muted">
        <ShieldCheck className="size-5 text-subtle" aria-hidden="true" />
        The consistency checker runs after each agent. Results appear here.
      </div>
    )
  }

  const passed = latest.filter((c) => c.passed).length

  return (
    <div className="h-full overflow-y-auto p-4">
      <p className="text-xs text-subtle">
        <span className={cn('font-medium', passed === latest.length ? 'text-green' : 'text-red')}>
          {passed}/{latest.length} passed
        </span>{' '}
        · static checks only, the generated code is never run · last check {formatRelative(latest[0]!.createdAt)}
      </p>
      <ul className="mt-3 grid gap-2" aria-label="Consistency checks">
        {latest.map((check) => {
          const Icon = check.passed ? (check.severity === 'warning' ? CircleAlert : CircleCheck) : CircleX
          const tone = check.passed ? (check.severity === 'warning' ? 'text-yellow' : 'text-green') : 'text-red'
          const lines = check.passed ? [] : detailLines(check)
          return (
            <li key={check.id} className="flex gap-3 rounded-md border border-border bg-base/40 p-3">
              <Icon className={cn('mt-0.5 size-4 shrink-0', tone)} aria-label={check.passed ? 'Passed' : 'Failed'} />
              <div className="min-w-0 flex-1 text-sm">
                <p className="flex flex-wrap items-center gap-x-2">
                  <span className="font-medium">{humanize(check.checkName)}</span>
                  <span className="rounded-full border border-border px-1.5 text-[10px] text-subtle">
                    {STAGE_LABEL[check.stage] ?? check.stage}
                  </span>
                  <span className="text-[11px] text-subtle">{check.durationMs} ms</span>
                </p>
                <p className="mt-0.5 text-muted">{check.message}</p>
                {lines.length > 0 && (
                  <ul className="mt-2 space-y-0.5 font-mono text-xs text-red">
                    {lines.map((l, i) => (
                      <li key={i} className="truncate">
                        {l}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
