import { ChevronDown, SendHorizontal } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { AgentAvatar } from '@/components/agent-badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { AGENTS, AGENT_LIST, agentClasses, getStage } from '@/lib/agents'
import { useAuth } from '@/lib/auth'
import type { AgentId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'
import { ChatMessageItem, TypingIndicator } from './chat-message'

/** First messages a student can send to each agent, shown until they start talking to it. */
const STARTERS: Record<AgentId, string[]> = {
  idea: ['What features am I missing?', 'Who else could use this app?', 'Is this too big for a first version?'],
  stack: ['Help me choose a stack. Ask me what you need to know.', 'I only know Python. What would suit me?'],
  code: ['Walk me through how the code fits together', 'Where does the app store its data?', 'What should I read first?'],
  deploy: ['Where can I deploy this for free?', 'What environment variables will I need?', 'What if I switch the database?'],
  eva: ['What is the most serious problem you found?', 'How do I fix the failing findings?', 'Help me write my own test scenario'],
}

export function AgentChat() {
  const { messages, typingAgent, sendMessage, view, chatError } = useWorkspace()
  const { user } = useAuth()
  const [draft, setDraft] = useState('')
  // null = follow the agent that owns the current stage.
  const [pickedAgent, setPickedAgent] = useState<AgentId | null>(null)
  const agentId = pickedAgent ?? getStage(view).agentId
  const c = agentClasses(agentId)
  const listRef = useRef<HTMLOListElement>(null)

  // Chips above the input: the latest reply's follow-ups, or starters before the first conversation.
  const last = messages[messages.length - 1]
  const talkedTo = messages.some((m) => m.agentId === agentId)
  const chips =
    last?.role === 'agent' && last.agentId === agentId && last.suggestions?.length
      ? last.suggestions
      : talkedTo
        ? []
        : STARTERS[agentId]

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTo({ top: list.scrollHeight, behavior: 'smooth' })
  }, [messages.length, typingAgent])

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (!draft.trim() || typingAgent) return
    sendMessage(draft, agentId)
    setDraft('')
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) submit(event)
  }

  return (
    <section aria-label="Agent chat" className="flex h-full min-h-0 flex-col bg-panel">
      <div className="flex h-9 shrink-0 items-center justify-between border-b border-border px-3">
        <h2 className="text-[11px] font-semibold tracking-wider text-subtle uppercase">Agents</h2>
        <span className="text-[11px] text-subtle">{messages.length} messages</span>
      </div>

      <ol ref={listRef} className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-3" aria-live="polite">
        {messages.map((message) => (
          <ChatMessageItem key={message.id} message={message} userName={user?.name ?? 'You'} />
        ))}
        {typingAgent && <TypingIndicator agentId={typingAgent} />}
      </ol>

      <form onSubmit={submit} className="shrink-0 border-t border-border p-3">
        {chips.length > 0 && !typingAgent && (
          <ul className="mb-2 flex flex-wrap gap-1.5" aria-label="Suggested messages">
            {chips.map((chip) => (
              <li key={chip}>
                <button
                  type="button"
                  onClick={() => sendMessage(chip, agentId)}
                  className={cn(
                    'cursor-pointer rounded-full border bg-raised px-2.5 py-1 text-left text-xs text-muted transition-colors hover:text-text',
                    c.border,
                  )}
                >
                  {chip}
                </button>
              </li>
            ))}
          </ul>
        )}
        {chatError && (
          <p role="alert" className="mb-2 rounded-md border border-red/30 bg-red/10 px-2.5 py-1.5 text-xs text-red">
            {chatError}
          </p>
        )}
        <div className={cn('rounded-lg border bg-raised transition-colors focus-within:ring-2', c.border, c.ring)}>
          <label htmlFor="chat-input" className="sr-only">
            Message {AGENTS[agentId].name}
          </label>
          <textarea
            id="chat-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            placeholder={`Ask the ${AGENTS[agentId].name}…`}
            className="block w-full resize-none bg-transparent px-3 pt-2.5 text-sm text-text placeholder:text-subtle focus:outline-none"
          />
          <div className="flex items-center justify-between gap-2 px-2 pb-2">
            <DropdownMenu>
              <DropdownMenuTrigger
                className="flex cursor-pointer items-center gap-1.5 rounded-md px-1.5 py-1 text-xs text-muted hover:bg-panel hover:text-text"
                aria-label={`Talking to ${AGENTS[agentId].name}. Change agent`}
              >
                <AgentAvatar agentId={agentId} size="sm" className="size-5 [&_svg]:size-3" />
                <span className={c.text}>{AGENTS[agentId].shortName}</span>
                <ChevronDown className="size-3" aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" side="top">
                <DropdownMenuLabel>Talk to</DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => setPickedAgent(null)}>
                  <span className="text-muted">Auto (current stage)</span>
                </DropdownMenuItem>
                {AGENT_LIST.map((agent) => (
                  <DropdownMenuItem key={agent.id} onSelect={() => setPickedAgent(agent.id)}>
                    <AgentAvatar agentId={agent.id} size="sm" className="size-5 [&_svg]:size-3" />
                    <span className={agentClasses(agent.id).text}>{agent.name}</span>
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button type="submit" size="icon-sm" disabled={!draft.trim() || typingAgent !== null} aria-label="Send message">
              <SendHorizontal aria-hidden="true" />
            </Button>
          </div>
        </div>
        <p className="mt-1.5 text-[11px] text-subtle">Enter to send · Shift+Enter for a new line</p>
      </form>
    </section>
  )
}
