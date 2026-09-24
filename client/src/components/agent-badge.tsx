import { CodeXml, Layers, Lightbulb, Rocket, UsersRound, type LucideIcon } from 'lucide-react'
import { AGENTS, agentClasses } from '@/lib/agents'
import type { AgentId } from '@/lib/types'
import { cn } from '@/lib/utils'

export const AGENT_ICONS: Record<AgentId, LucideIcon> = {
  idea: Lightbulb,
  stack: Layers,
  code: CodeXml,
  deploy: Rocket,
  eva: UsersRound,
}

interface AgentAvatarProps {
  agentId: AgentId
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const AVATAR_SIZES = {
  sm: 'size-6 [&_svg]:size-3.5',
  md: 'size-8 [&_svg]:size-4',
  lg: 'size-11 [&_svg]:size-5',
} as const

/** Rounded square with the agent's icon in its colour. */
export function AgentAvatar({ agentId, size = 'md', className }: AgentAvatarProps) {
  const Icon = AGENT_ICONS[agentId]
  const c = agentClasses(agentId)
  return (
    <span
      aria-hidden="true"
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-md border',
        c.bgSoft,
        c.border,
        c.text,
        AVATAR_SIZES[size],
        className,
      )}
    >
      <Icon />
    </span>
  )
}

interface AgentChipProps {
  agentId: AgentId
  short?: boolean
  className?: string
}

/** Inline pill label: ● Code Agent */
export function AgentChip({ agentId, short = false, className }: AgentChipProps) {
  const agent = AGENTS[agentId]
  const c = agentClasses(agentId)
  const Icon = AGENT_ICONS[agentId]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        c.bgSoft,
        c.border,
        c.text,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {short ? agent.shortName : agent.name}
    </span>
  )
}
