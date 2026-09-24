import { motion } from 'framer-motion'
import { AlertCircle, CheckCircle2, HelpCircle, Quote, RotateCw, Users } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelative } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'
import { StageShell } from './stage-shell'

/** Stage 1: the idea as the user wrote it, and the spec the Idea Agent wrote from it. */
export function IdeaView() {
  const { project, generateSpec, runningStage, runs, runError } = useWorkspace()
  const ideaFailed = !project.specReady && (runError !== null || runs.some((r) => r.agent === 'idea' && r.status === 'failed'))

  // A brand-new project starts writing its spec as soon as the workspace opens.
  // The ref stops React StrictMode's double effect from starting it twice.
  const started = useRef(false)
  useEffect(() => {
    if (!project.specReady && !runningStage && !ideaFailed && !started.current) {
      started.current = true
      generateSpec()
    }
  }, [project.specReady, runningStage, ideaFailed, generateSpec])

  return (
    <StageShell stage="idea">
      <figure className="rounded-lg border border-pink/30 bg-pink/5 p-6">
        <Quote className="size-5 text-pink" aria-hidden="true" />
        <blockquote className="mt-3 text-lg leading-relaxed text-text">{project.idea}</blockquote>
        <figcaption className="mt-4 text-xs text-subtle">Your idea, submitted {formatRelative(project.createdAt)}</figcaption>
      </figure>

      <div className="mt-10">
        {project.spec ? (
          <SpecDocument />
        ) : ideaFailed && runningStage !== 'idea' ? (
          <SpecFailed onRetry={generateSpec} />
        ) : (
          <SpecWriting />
        )}
      </div>
    </StageShell>
  )
}

function SpecFailed({ onRetry }: { onRetry: () => void }) {
  const { runError, runs } = useWorkspace()
  const message = runError ?? runs.find((r) => r.agent === 'idea' && r.status === 'failed')?.error
  return (
    <div role="alert" className="rounded-lg border border-red/30 bg-red/5 p-5">
      <p className="flex items-center gap-2 font-medium text-red">
        <AlertCircle className="size-4" aria-hidden="true" /> The Idea Agent could not write the spec
      </p>
      {message && <p className="mt-2 text-sm text-muted">{message}</p>}
      <Button variant="secondary" className="mt-4" onClick={onRetry}>
        <RotateCw aria-hidden="true" /> Try again
      </Button>
    </div>
  )
}

function SpecWriting() {
  return (
    <div role="status" aria-live="polite">
      <p className="flex items-center gap-2 text-sm font-medium text-pink">
        <span className="size-2 animate-pulse-soft rounded-full bg-pink" aria-hidden="true" />
        The Idea Agent is writing your spec…
      </p>
      <div className="mt-6 space-y-3" aria-hidden="true">
        {[90, 70, 80, 55, 65].map((w, i) => (
          <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.2 }}>
            <Skeleton className="h-4" style={{ width: `${w}%` }} />
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function SpecDocument() {
  const { project } = useWorkspace()
  const spec = project.spec
  if (!spec) return null

  return (
    <motion.article initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-8" aria-labelledby="spec-heading">
      <h3 id="spec-heading" className="text-lg font-semibold">
        Spec
      </h3>
      <section>
        <h4 className="text-sm font-semibold text-subtle uppercase">Summary</h4>
        <p className="mt-2 leading-relaxed">{spec.summary}</p>
      </section>

      <section>
        <h4 className="flex items-center gap-2 text-sm font-semibold text-subtle uppercase">
          <Users className="size-4" aria-hidden="true" /> Target users
        </h4>
        <ul className="mt-3 flex flex-wrap gap-2">
          {spec.targetUsers.map((user) => (
            <li key={user}>
              <Badge tone="pink">{user}</Badge>
            </li>
          ))}
        </ul>
      </section>

      {spec.sections.map((section) => (
        <section key={section.title}>
          <h4 className="text-sm font-semibold text-subtle uppercase">{section.title}</h4>
          <ul className="mt-3 space-y-2">
            {section.items.map((item) => (
              <li key={item} className="flex items-start gap-2.5 text-sm">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-pink" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </section>
      ))}

      {spec.openQuestions.length > 0 && (
        <section>
          <h4 className="flex items-center gap-2 text-sm font-semibold text-subtle uppercase">
            <HelpCircle className="size-4" aria-hidden="true" /> Open questions
          </h4>
          <p className="mt-2 text-sm text-muted">Assumptions the Idea Agent made. Answer them in the chat.</p>
          <ul className="mt-3 space-y-2">
            {spec.openQuestions.map((question) => (
              <li key={question} className="flex items-start gap-2.5 text-sm">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-pink" aria-hidden="true" />
                {question}
              </li>
            ))}
          </ul>
        </section>
      )}
    </motion.article>
  )
}
