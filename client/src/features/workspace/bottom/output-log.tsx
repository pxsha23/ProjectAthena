import { useEffect, useRef } from 'react'
import { agentClasses } from '@/lib/agents'
import { cn, formatTime } from '@/lib/utils'
import { uiAgent, useWorkspace } from '../workspace-context'

/** Sources that are not agents get a neutral colour. */
const NEUTRAL_SOURCES = new Set(['athena', 'checker', 'search', 'system'])

const TONE = { default: 'text-muted', success: 'text-green', error: 'text-red' } as const

export function OutputLog() {
  const { output } = useWorkspace()
  const ref = useRef<HTMLOListElement>(null)

  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight })
  }, [output.length])

  if (output.length === 0) {
    return <p className="p-4 text-sm text-subtle">Agent activity appears here: every run, its model, time and tokens.</p>
  }

  return (
    <ol ref={ref} className="h-full overflow-y-auto p-3 font-mono text-xs leading-6" aria-label="Agent output log">
      {output.map((line) => (
        <li key={line.id} className="flex gap-3">
          <time dateTime={line.time} className="shrink-0 text-subtle">
            {formatTime(line.time)}
          </time>
          <span
            className={cn(
              'w-16 shrink-0 truncate',
              NEUTRAL_SOURCES.has(line.source) ? 'text-subtle' : agentClasses(uiAgent(line.source)).text,
            )}
          >
            [{line.source}]
          </span>
          <span className={cn('min-w-0 break-words', TONE[line.tone ?? 'default'])}>{line.text}</span>
        </li>
      ))}
    </ol>
  )
}
