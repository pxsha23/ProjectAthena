import { motion } from 'framer-motion'
import { CircleAlert, CircleCheck, CircleX } from 'lucide-react'
import type { ReactNode } from 'react'
import { AgentAvatar } from '@/components/agent-badge'
import { Spotlight } from '@/components/spotlight'
import { AGENTS, agentClasses } from '@/lib/agents'
import { LANDING_SHOWCASE as S } from '@/lib/landing-content'
import type { AgentId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { SectionHeading } from './section-heading'

interface BentoItem {
  agentId: AgentId
  className: string
  visual: ReactNode
}

const ITEMS: BentoItem[] = [
  { agentId: 'idea', className: 'lg:col-span-2', visual: <SpecVisual /> },
  { agentId: 'stack', className: '', visual: <StackVisual /> },
  { agentId: 'code', className: '', visual: <CodeVisual /> },
  { agentId: 'eva', className: '', visual: <EvaVisual /> },
  { agentId: 'deploy', className: '', visual: <DeployVisual /> },
]

export function AgentsBento() {
  return (
    <section id="agents" aria-labelledby="agents-heading" className="scroll-mt-20 border-t border-border py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          id="agents-heading"
          eyebrow="The agents"
          title="A small team, each with one job"
          description="Every agent has its own colour across Athena, so you always know who is talking and who did what."
        />

        <ul className="mt-14 grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ITEMS.map(({ agentId, className, visual }, i) => {
            const agent = AGENTS[agentId]
            const c = agentClasses(agentId)
            return (
              <motion.li
                key={agentId}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ delay: i * 0.08, duration: 0.5, ease: 'easeOut' }}
                className={cn('min-w-0', className, agentId === 'idea' && 'sm:col-span-2')}
              >
                <Spotlight
                  color={c.cssVar}
                  className="flex h-full flex-col rounded-2xl border border-border bg-panel transition-colors duration-300 hover:border-subtle/60"
                >
                  <div className="flex h-full flex-col p-6">
                    <div className="flex items-center gap-3">
                      <AgentAvatar agentId={agentId} size="lg" />
                      <div>
                        <h3 className={cn('font-semibold', c.text)}>{agent.name}</h3>
                        <p className="text-xs text-subtle">{agent.role}</p>
                      </div>
                    </div>
                    <p className="mt-4 text-sm text-muted">{agent.description}</p>
                    <div className="mt-6 flex-1" aria-hidden="true">
                      {visual}
                    </div>
                  </div>
                </Spotlight>
              </motion.li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}

/* ---------------- Card visuals (decorative) ---------------- */

function SpecVisual() {
  return (
    <div className="grid gap-2 rounded-lg border border-border bg-base/50 p-4 sm:grid-cols-2">
      {S.specItems.map((spec, i) => (
        <motion.div
          key={spec}
          initial={{ opacity: 0, x: -8 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 + i * 0.1 }}
          className="flex items-center gap-2 text-xs text-muted"
        >
          <CircleCheck className="size-3.5 shrink-0 text-pink" />
          <span className="truncate">{spec}</span>
        </motion.div>
      ))}
    </div>
  )
}

function StackVisual() {
  return (
    <div className="flex flex-wrap gap-2">
      {S.stack.map((choice, i) => (
        <motion.span
          key={choice.layer}
          animate={{ y: [0, -3, 0] }}
          transition={{ duration: 3, repeat: Infinity, delay: i * 0.4, ease: 'easeInOut' }}
          className="rounded-md border border-sky/25 bg-sky/5 px-2.5 py-1 font-mono text-xs text-sky"
        >
          {choice.name}
        </motion.span>
      ))}
    </div>
  )
}

function CodeVisual() {
  return (
    <div className="rounded-lg border border-border bg-base/50 p-3 font-mono text-[11px] leading-5">
      {S.codeLines.slice(4, 8).map((line, i) => (
        <div key={i} className="truncate whitespace-pre">
          {line.map((token, j) => (
            <span
              key={j}
              className={cn(
                token.tone === 'keyword' && 'text-mauve',
                token.tone === 'string' && 'text-green',
                token.tone === 'fn' && 'text-lavender',
                token.tone === 'type' && 'text-yellow',
                token.tone === 'comment' && 'text-subtle',
                !token.tone && 'text-text',
              )}
            >
              {token.text}
            </span>
          ))}
        </div>
      ))}
    </div>
  )
}

function EvaVisual() {
  const personas = [
    { name: 'Alpha', icon: CircleCheck, tone: 'text-green' },
    { name: 'Bravo', icon: CircleAlert, tone: 'text-yellow' },
    { name: 'Charlie', icon: CircleX, tone: 'text-red' },
  ]
  return (
    <div className="space-y-2">
      {personas.map(({ name, icon: Icon, tone }) => (
        <div key={name} className="flex items-center gap-2 rounded-md border border-border bg-base/50 px-3 py-1.5 text-xs">
          <span className="flex size-5 items-center justify-center rounded-full bg-peach/15 text-[10px] font-semibold text-peach">
            {name[0]}
          </span>
          <span className="text-muted">{name}</span>
          <Icon className={cn('ml-auto size-3.5', tone)} />
        </div>
      ))}
    </div>
  )
}

function DeployVisual() {
  return (
    <div className="rounded-lg border border-border bg-base/50 p-3 font-mono text-xs">
      <p className="flex items-center gap-2 text-green">
        <span className="relative flex size-2">
          <span className="absolute inset-0 animate-ping rounded-full bg-green/70" />
          <span className="relative size-2 rounded-full bg-green" />
        </span>
        Live
      </p>
      <p className="mt-1 truncate text-muted">{S.liveUrl}</p>
      <p className="mt-2 text-subtle">Dockerfile, render.yaml, deploy.yml</p>
    </div>
  )
}
