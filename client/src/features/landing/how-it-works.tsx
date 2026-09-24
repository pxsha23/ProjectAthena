import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useState } from 'react'
import { AgentAvatar } from '@/components/agent-badge'
import { Spotlight } from '@/components/spotlight'
import { AGENTS, STAGES, agentClasses } from '@/lib/agents'
import type { StageId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { SectionHeading } from './section-heading'
import { StepPreview } from './step-previews'

const STEP_DETAILS: Record<StageId, string> = {
  idea: 'Describe your app in plain words. The Idea Agent asks what it needs and writes a clear spec.',
  stack: 'Frameworks, database and hosting chosen to fit the spec, each with a short reason.',
  code: 'Every file is written into the built-in editor, ready to read and change. EVA then tests it with virtual users.',
  export: 'Push to a new GitHub repository or download everything as a zip.',
  deploy: 'Dockerfile, CI workflow and hosting config, plus a summary of what you learned.',
}

const PREVIEW_PATH: Record<StageId, string> = {
  idea: 'spec.md',
  stack: 'stack.md',
  code: 'backend/main.py',
  export: 'export',
  deploy: 'deploy.log',
}

export function HowItWorks() {
  const reduced = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const stage = STAGES[index]!
  const c = agentClasses(stage.agentId)

  const next = () => setIndex((i) => (i + 1) % STAGES.length)

  return (
    <section id="how-it-works" aria-labelledby="how-heading" className="scroll-mt-20 py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          id="how-heading"
          eyebrow="How it works"
          title="Five steps from sentence to shipped"
          description="Each step is owned by an agent. You can read, edit and question the result before moving on."
        />

        <div
          className="mt-14 grid gap-6 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] lg:gap-10"
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          onFocusCapture={() => setPaused(true)}
          onBlurCapture={() => setPaused(false)}
        >
          <ol className="flex flex-col gap-2">
            {STAGES.map((s, i) => {
              const active = i === index
              const sc = agentClasses(s.agentId)
              return (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => setIndex(i)}
                    aria-current={active ? 'step' : undefined}
                    className={cn(
                      'relative w-full cursor-pointer overflow-hidden rounded-xl border p-4 text-left transition-colors duration-300',
                      active ? cn('bg-panel', sc.border) : 'border-transparent hover:bg-panel/60',
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={cn(
                          'flex size-7 shrink-0 items-center justify-center rounded-full border font-mono text-xs transition-colors',
                          active ? cn(sc.border, sc.text, sc.bgSoft) : 'border-border text-subtle',
                        )}
                      >
                        {i + 1}
                      </span>
                      <span className={cn('font-medium', active ? 'text-text' : 'text-muted')}>{s.label}</span>
                      <span className={cn('ml-auto text-xs', active ? sc.text : 'text-subtle')}>
                        {AGENTS[s.agentId].shortName}
                      </span>
                    </div>
                    <AnimatePresence initial={false}>
                      {active && (
                        <motion.p
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.3 }}
                          className="overflow-hidden pl-10 text-sm text-muted"
                        >
                          <span className="block pt-2">{STEP_DETAILS[s.id]}</span>
                        </motion.p>
                      )}
                    </AnimatePresence>
                    {active && (
                      <span aria-hidden="true" className="absolute inset-x-0 bottom-0 h-0.5 bg-raised">
                        <span
                          key={index}
                          onAnimationEnd={reduced ? undefined : next}
                          className={cn(
                            'block h-full origin-left',
                            sc.bg,
                            reduced ? 'scale-x-100' : 'animate-progress',
                            paused && '[animation-play-state:paused]',
                          )}
                        />
                      </span>
                    )}
                  </button>
                </li>
              )
            })}
          </ol>

          {/* Preview window */}
          <Spotlight
            color={c.cssVar}
            className={cn('rounded-2xl border bg-panel shadow-2xl transition-colors duration-500', c.border, c.glow)}
          >
            <div className="flex h-10 items-center gap-2 border-b border-border px-4">
              <span className="size-2.5 rounded-full bg-red/70" aria-hidden="true" />
              <span className="size-2.5 rounded-full bg-yellow/70" aria-hidden="true" />
              <span className="size-2.5 rounded-full bg-green/70" aria-hidden="true" />
              <span className="ml-3 truncate font-mono text-xs text-subtle">studysync / {PREVIEW_PATH[stage.id]}</span>
              <span className={cn('ml-auto flex items-center gap-2 text-xs', c.text)}>
                <AgentAvatar agentId={stage.agentId} size="sm" className="size-5 [&_svg]:size-3" />
                <span className="hidden sm:inline">{AGENTS[stage.agentId].name}</span>
              </span>
            </div>
            <div className="relative h-[380px] overflow-hidden">
              <AnimatePresence mode="wait">
                <motion.div
                  key={stage.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -12 }}
                  transition={{ duration: 0.3 }}
                  className="h-full"
                >
                  <StepPreview stage={stage.id} />
                </motion.div>
              </AnimatePresence>
            </div>
          </Spotlight>
        </div>
      </div>
    </section>
  )
}
