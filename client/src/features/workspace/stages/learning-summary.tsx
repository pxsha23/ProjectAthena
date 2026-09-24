import { BookOpen, ChevronDown, FlaskConical, ListChecks, Milestone } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import type { LearningTopic } from '@/lib/types'
import { cn } from '@/lib/utils'
import { FileIcon } from '../file-icon'
import { useWorkspace } from '../workspace-context'

/** The Deployment & Summary Agent's detailed write-up of what was built and why. */
export function LearningSummary() {
  const { project } = useWorkspace()
  const learning = project.learning?.topics ?? []
  const overview = project.learning?.overview ?? { summary: [], stats: [], nextSteps: [] }
  // First topic open by default; the rest expand on demand so the page stays scannable.
  const [open, setOpen] = useState<Set<number>>(() => new Set([0]))

  function toggle(index: number) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  const allOpen = open.size === learning.length

  return (
    <section aria-labelledby="learning-heading" className="mt-12">
      <h3 id="learning-heading" className="flex items-center gap-2 text-sm font-semibold text-subtle uppercase">
        <BookOpen className="size-4" aria-hidden="true" /> Learning summary
      </h3>

      {/* Overview */}
      <Card spotlight="var(--color-green)" className="mt-4 p-6">
        <h4 className="text-lg font-semibold">What you built</h4>
        <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted">
          {overview.summary.map((paragraph) => (
            <p key={paragraph.slice(0, 32)}>{paragraph}</p>
          ))}
        </div>
        <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {overview.stats.map((stat) => (
            <div key={stat.label} className="rounded-lg border border-border bg-base/40 p-3">
              <dt className="text-xs text-subtle">{stat.label}</dt>
              <dd className="mt-1 text-xl font-semibold text-green">{stat.value}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {/* Topics */}
      <div className="mt-8 flex items-center justify-between gap-3">
        <h4 className="font-semibold">
          {learning.length} topics <span className="font-normal text-subtle">in reading order</span>
        </h4>
        <button
          type="button"
          onClick={() => setOpen(allOpen ? new Set() : new Set(learning.map((_, i) => i)))}
          className="cursor-pointer rounded-md px-2 py-1 text-xs text-muted transition-colors hover:bg-raised hover:text-text"
        >
          {allOpen ? 'Collapse all' : 'Expand all'}
        </button>
      </div>
      <ol className="mt-3 grid gap-3">
        {learning.map((topic, index) => (
          <li key={topic.title}>
            <TopicCard topic={topic} index={index} open={open.has(index)} onToggle={() => toggle(index)} />
          </li>
        ))}
      </ol>

      {/* Next steps */}
      <Card spotlight="var(--color-green)" className="mt-8 p-6">
        <h4 className="flex items-center gap-2 font-semibold">
          <Milestone className="size-4 text-green" aria-hidden="true" /> Where to go next
        </h4>
        <ol className="mt-4 space-y-3">
          {overview.nextSteps.map((step, i) => (
            <li key={step} className="flex gap-3 text-sm text-muted">
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-green/10 font-mono text-[11px] text-green">
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
      </Card>
    </section>
  )
}

interface TopicCardProps {
  topic: LearningTopic
  index: number
  open: boolean
  onToggle: () => void
}

function TopicCard({ topic, index, open, onToggle }: TopicCardProps) {
  const { fileIndex, openFile } = useWorkspace()
  const panelId = `learning-topic-${index}`

  return (
    <Card spotlight="var(--color-green)" className={cn('transition-colors', open && 'border-green/30')}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full cursor-pointer items-start gap-4 p-5 text-left"
      >
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-green/30 bg-green/10 text-xs font-semibold text-green">
          {index + 1}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{topic.title}</span>
          {!open && <span className="mt-1 line-clamp-1 block text-sm text-muted">{topic.summary[0]}</span>}
        </span>
        <ChevronDown
          className={cn('mt-1 size-4 shrink-0 text-subtle transition-transform', open && 'rotate-180')}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div id={panelId} className="space-y-6 px-5 pb-6 sm:pl-16">
          <div className="space-y-3 text-sm leading-relaxed text-muted">
            {topic.summary.map((paragraph) => (
              <p key={paragraph.slice(0, 32)}>{paragraph}</p>
            ))}
          </div>

          <ul className="flex flex-wrap gap-1.5" aria-label="Key concepts">
            {topic.concepts.map((concept) => (
              <li key={concept}>
                <Badge tone="green">{concept}</Badge>
              </li>
            ))}
          </ul>

          <div>
            <h5 className="flex items-center gap-2 text-xs font-semibold tracking-wide text-subtle uppercase">
              <ListChecks className="size-3.5" aria-hidden="true" /> How it works in your project
            </h5>
            <ol className="mt-3 space-y-2 border-l border-border pl-4">
              {topic.howItWorks.map((step) => (
                <li key={step} className="text-sm text-text">
                  {step}
                </li>
              ))}
            </ol>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h5 className="text-xs font-semibold tracking-wide text-subtle uppercase">Key terms</h5>
              <dl className="mt-3 space-y-2.5 text-sm">
                {topic.keyTerms.map(({ term, meaning }) => (
                  <div key={term}>
                    <dt className="font-medium text-text">{term}</dt>
                    <dd className="text-muted">{meaning}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div>
              <h5 className="text-xs font-semibold tracking-wide text-subtle uppercase">Where to look</h5>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {topic.files.map((path) => {
                  const node = fileIndex.get(path)
                  return (
                    <li key={path}>
                      <button
                        type="button"
                        onClick={() => openFile(path)}
                        disabled={!node}
                        aria-label={`Open ${path} in the editor`}
                        className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-raised px-2 py-1 font-mono text-xs text-muted transition-colors hover:border-subtle hover:text-text disabled:cursor-default"
                      >
                        {node && <FileIcon node={{ type: 'file', name: path, language: node.language }} className="size-3.5" />}
                        {path}
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          </div>

          <div className="flex gap-3 rounded-lg border border-green/25 bg-green/5 p-4">
            <FlaskConical className="mt-0.5 size-4 shrink-0 text-green" aria-hidden="true" />
            <div className="text-sm">
              <p className="font-medium text-green">Try it yourself</p>
              <p className="mt-1 text-muted">{topic.tryIt}</p>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}
