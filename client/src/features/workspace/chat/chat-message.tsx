import { motion } from 'framer-motion'
import { Check, FileText, Layers, X } from 'lucide-react'
import { AgentAvatar } from '@/components/agent-badge'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { AGENTS, agentClasses } from '@/lib/agents'
import type { AgentId, ChatMessage } from '@/lib/types'
import { cn, formatTime } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'
import { ChatText } from './chat-text'

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
          {isUser ? message.content : <ChatText text={message.content} />}
        </div>
        {message.proposal && <ProposalCard message={message} />}
      </div>
    </motion.li>
  )
}

/** A spec or stack change the agent proposed. The student decides: apply it or dismiss it. */
function ProposalCard({ message }: { message: ChatMessage }) {
  const { resolveProposal, resolvingMessage, proposalError } = useWorkspace()
  const proposal = message.proposal!
  const status = message.proposalStatus ?? 'pending'
  const busy = resolvingMessage === message.id
  const isSpec = proposal.kind === 'spec'
  const Icon = isSpec ? FileText : Layers
  const c = agentClasses(isSpec ? 'idea' : 'stack')

  return (
    <div className={cn('w-full rounded-lg border bg-panel p-3 text-sm', c.border)}>
      <p className={cn('flex items-center gap-1.5 text-xs font-semibold', c.text)}>
        <Icon className="size-3.5" aria-hidden="true" />
        {isSpec ? 'Proposed change to your spec' : 'Proposed tech stack'}
      </p>
      {proposal.changes.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
          {proposal.changes.map((change, i) => (
            <li key={i}>{change}</li>
          ))}
        </ul>
      )}
      {status === 'pending' ? (
        <>
          <div className="mt-3 flex gap-2">
            <Button size="sm" onClick={() => resolveProposal(message.id, 'apply')} disabled={resolvingMessage !== null}>
              <Check aria-hidden="true" /> {busy ? 'Applying…' : 'Apply'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => resolveProposal(message.id, 'dismiss')} disabled={resolvingMessage !== null}>
              <X aria-hidden="true" /> Dismiss
            </Button>
          </div>
          {proposalError && !resolvingMessage && (
            <p role="alert" className="mt-2 text-xs text-red">
              {proposalError}
            </p>
          )}
          <p className="mt-2 text-[11px] text-subtle">Nothing changes until you apply it. You have the final say.</p>
        </>
      ) : (
        <p className={cn('mt-2 flex items-center gap-1 text-xs', status === 'applied' ? 'text-green' : 'text-subtle')}>
          {status === 'applied' ? <Check className="size-3.5" aria-hidden="true" /> : <X className="size-3.5" aria-hidden="true" />}
          {status === 'applied' ? 'Applied' : 'Dismissed'}
        </p>
      )}
    </div>
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
