import { motion } from 'framer-motion'
import { AgentAvatar } from '@/components/agent-badge'
import { Avatar } from '@/components/ui/avatar'
import { AGENTS, agentClasses } from '@/lib/agents'
import type { AgentId, ChatMessage } from '@/lib/types'
import { cn, formatTime } from '@/lib/utils'

interface ChatMessageItemProps {
  message: ChatMessage
  userName: string
}

export function ChatMessageItem({ message, userName }: ChatMessageItemProps) {
  const isUser = message.role === 'user'
  const agentId = message.agentId ?? 'idea'
  const c = agentClasses(agentId)

  return (
    <motion.li
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex gap-2.5', isUser && 'flex-row-reverse')}
    >
      {isUser ? <Avatar name={userName} className="size-6 text-[10px]" /> : <AgentAvatar agentId={agentId} size="sm" />}
      <div className={cn('flex min-w-0 max-w-[85%] flex-col gap-1', isUser && 'items-end')}>
        <p className="flex items-baseline gap-2 text-[11px]">
          <span className={cn('font-medium', isUser ? 'text-muted' : c.text)}>
            {isUser ? 'You' : AGENTS[agentId].name}
          </span>
          <time dateTime={message.createdAt} className="text-subtle">
            {formatTime(message.createdAt)}
          </time>
        </p>
        <div
          className={cn(
            'rounded-lg border px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap',
            isUser ? 'border-lavender/30 bg-lavender/10 text-text' : 'border-border bg-raised/50 text-text',
          )}
        >
          {message.content}
        </div>
      </div>
    </motion.li>
  )
}

export function TypingIndicator({ agentId }: { agentId: AgentId }) {
  const c = agentClasses(agentId)
  return (
    <li className="flex items-center gap-2.5" aria-live="polite">
      <AgentAvatar agentId={agentId} size="sm" />
      <span className="sr-only">{AGENTS[agentId].name} is typing</span>
      <span className="flex gap-1 rounded-lg border border-border bg-raised/50 px-3 py-3" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className={cn('size-1.5 rounded-full', c.bg)}
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{ duration: 1, repeat: Infinity, delay: i * 0.15 }}
          />
        ))}
      </span>
    </li>
  )
}
