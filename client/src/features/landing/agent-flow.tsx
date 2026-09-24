import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Globe, type LucideIcon } from 'lucide-react'
import { Fragment, useEffect, useState } from 'react'
import { AGENT_ICONS } from '@/components/agent-badge'
import { ACCENT_CLASSES, AGENTS } from '@/lib/agents'
import type { AccentColor, AgentId } from '@/lib/types'
import { useMediaQuery } from '@/lib/use-media-query'
import { cn } from '@/lib/utils'

interface FlowNode {
  id: string
  label: string
  icon: LucideIcon
  color: AccentColor
  /** Shown under the diagram while this node is the latest one lit. */
  caption?: string
}

const agentNode = (id: AgentId, caption: string, label = AGENTS[id].shortName): FlowNode => ({
  id,
  label,
  icon: AGENT_ICONS[id],
  color: AGENTS[id].color,
  caption,
})

/** The order work flows through Athena: EVA checks the code before it ships. */
const NODES: FlowNode[] = [
  agentNode('idea', 'Brainstorm with the Idea Agent, then it writes the spec: users, features and scope.', 'Brainstorm idea'),
  agentNode('stack', 'The Tech Stack Agent picks tools and explains why.'),
  agentNode('code', 'The Code Agent generates every file in the editor.'),
  agentNode('eva', 'EVA sends virtual users through the app and reports issues.'),
  agentNode('deploy', 'Deployment files and a learning summary are written.'),
  { id: 'live', label: 'Live app', icon: Globe, color: 'green' },
]

const STEP_MS = 1100
const HOLD_STEPS = 3 // pause on the finished flow before restarting

export function AgentFlow() {
  const reduced = useReducedMotion()
  const horizontal = useMediaQuery('(min-width: 768px)')
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (reduced) return
    const timer = setInterval(() => setTick((t) => (t + 1) % (NODES.length + HOLD_STEPS)), STEP_MS)
    return () => clearInterval(timer)
  }, [reduced])

  // Index of the furthest lit node. With reduced motion everything is shown lit.
  const active = reduced ? NODES.length - 1 : Math.min(tick, NODES.length - 1)
  // Nodes without a caption keep showing the previous one.
  const caption = NODES.slice(0, active + 1).reverse().find((n) => n.caption)?.caption ?? ''

  return (
    <figure className="w-full" aria-label="How an idea flows through Athena's agents">
      <ol className="flex flex-col items-center md:flex-row md:items-start">
        {NODES.map((node, i) => {
          const lit = i <= active
          const c = ACCENT_CLASSES[node.color]
          const Icon = node.icon
          return (
            <Fragment key={node.id}>
              {i > 0 && <Connector color={node.color} flowing={!reduced && tick === i} lit={lit} horizontal={horizontal} />}
              <li className="flex shrink-0 flex-col items-center gap-2 md:w-24">
                <motion.span
                  animate={{ scale: lit && i === active && !reduced ? [1, 1.08, 1] : 1 }}
                  transition={{ duration: 0.5 }}
                  className={cn(
                    'relative flex size-12 items-center justify-center rounded-xl border bg-panel transition-all duration-500 md:size-14',
                    lit ? cn(c.border, c.text, c.bgSoft, 'shadow-lg', c.glow) : 'border-border text-subtle',
                  )}
                >
                  <Icon className="size-5 md:size-6" aria-hidden="true" />
                  {lit && i === active && !reduced && (
                    <motion.span
                      aria-hidden="true"
                      className={cn('absolute inset-0 rounded-xl border', c.border)}
                      initial={{ opacity: 0.8, scale: 1 }}
                      animate={{ opacity: 0, scale: 1.5 }}
                      transition={{ duration: 0.9, ease: 'easeOut' }}
                    />
                  )}
                </motion.span>
                <span className={cn('text-center text-xs font-medium transition-colors duration-500', lit ? 'text-text' : 'text-subtle')}>
                  {node.label}
                </span>
              </li>
            </Fragment>
          )
        })}
      </ol>
      <figcaption className="mt-6 h-5 text-center text-sm text-muted" aria-live="off">
        <AnimatePresence mode="wait">
          <motion.span
            key={caption}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.25 }}
            className="inline-block"
          >
            {caption}
          </motion.span>
        </AnimatePresence>
      </figcaption>
    </figure>
  )
}

interface ConnectorProps {
  color: AccentColor
  flowing: boolean
  lit: boolean
  horizontal: boolean
}

/** Line between two nodes. A bright pulse travels along it when the next node is reached. */
function Connector({ color, flowing, lit, horizontal }: ConnectorProps) {
  const c = ACCENT_CLASSES[color]
  return (
    <li
      aria-hidden="true"
      className={cn('relative overflow-hidden', horizontal ? 'mt-[27px] h-0.5 min-w-6 flex-1' : 'my-1 h-8 w-0.5')}
    >
      <span
        className={cn(
          'absolute rounded-full transition-colors duration-500',
          horizontal ? 'inset-x-0 top-1/2 h-px -translate-y-1/2' : 'inset-y-0 left-1/2 w-px -translate-x-1/2',
          lit ? cn(c.bg, 'opacity-50') : 'bg-border',
        )}
      />
      {flowing && (
        <motion.span
          className={cn(
            'absolute rounded-full',
            horizontal
              ? cn('inset-y-0 w-1/2 bg-linear-to-r from-transparent to-transparent', c.via)
              : cn('inset-x-0 h-1/2 bg-linear-to-b from-transparent to-transparent', c.via),
          )}
          initial={horizontal ? { x: '-100%' } : { y: '-100%' }}
          animate={horizontal ? { x: '200%' } : { y: '200%' }}
          transition={{ duration: STEP_MS / 1000, ease: 'easeInOut' }}
        />
      )}
    </li>
  )
}
