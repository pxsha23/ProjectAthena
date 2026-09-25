import { motion } from 'framer-motion'
import { Lock, MessageSquare, Play } from 'lucide-react'
import { AgentAvatar } from '@/components/agent-badge'
import { Button } from '@/components/ui/button'
import { AGENTS, agentClasses, getStage } from '@/lib/agents'
import type { StageId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'

const WORKING_STEPS: Record<StageId, string[]> = {
  idea: ['Reading your idea', 'Identifying target users', 'Listing core features', 'Writing the spec'],
  stack: ['Reviewing the spec', 'Comparing frameworks', 'Choosing a database', 'Planning hosting'],
  code: ['Scaffolding folders', 'Writing the backend API', 'Building the frontend', 'Type-checking'],
  export: ['Packaging files', 'Writing README', 'Preparing repository'],
  deploy: ['Writing Dockerfile', 'Configuring CI/CD', 'Summarising what you learned'],
}

/** Shown for stages the pipeline hasn't reached yet — or while an agent is working on it. */
export function StageLocked({ stage }: { stage: StageId }) {
  const { nextStage, runNextStage, runningStage, canAdvance, sendMessage, typingAgent, messages } = useWorkspace()
  const meta = getStage(stage)
  const agent = AGENTS[meta.agentId]
  const c = agentClasses(meta.agentId)
  const isNext = nextStage === stage
  const running = runningStage === stage

  return (
    <div className="flex h-full items-center justify-center overflow-y-auto bg-panel px-6 py-10">
      <div className="flex max-w-md flex-col items-center text-center" aria-live="polite">
        <div className="relative">
          <AgentAvatar agentId={meta.agentId} size="lg" className="size-16 [&_svg]:size-7" />
          {running && (
            <motion.span
              aria-hidden="true"
              className={cn('absolute -inset-2 rounded-xl border-2', c.border)}
              animate={{ opacity: [0.2, 1, 0.2], scale: [0.96, 1.04, 0.96] }}
              transition={{ duration: 1.6, repeat: Infinity }}
            />
          )}
        </div>

        <h2 className="mt-6 text-xl font-semibold">
          {running ? `${agent.name} is working…` : `${meta.label} not started`}
        </h2>
        <p className="mt-2 text-sm text-muted">{running ? meta.description : agent.description}</p>

        {running ? (
          <ol className="mt-6 w-full space-y-2 text-left text-sm">
            {WORKING_STEPS[stage].map((step, i) => (
              <motion.li
                key={step}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.45 }}
                className="flex items-center gap-2 text-muted"
              >
                <span className={cn('size-1.5 rounded-full', c.bg)} aria-hidden="true" />
                {step}
              </motion.li>
            ))}
          </ol>
        ) : isNext && canAdvance && stage === 'stack' ? (
          <StackConsultation
            talked={messages.some((m) => m.agentId === 'stack')}
            busy={typingAgent !== null}
            onTalk={() => sendMessage('Help me choose a stack. Ask me what you need to know.', 'stack')}
            onRecommend={() => void runNextStage()}
          />
        ) : isNext && canAdvance ? (
          <Button variant="ai" className="mt-6" onClick={() => void runNextStage()}>
            <Play aria-hidden="true" /> Run {agent.name}
          </Button>
        ) : (
          <p className="mt-6 inline-flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs text-subtle">
            <Lock className="size-3.5" aria-hidden="true" /> Finish the earlier stages first
          </p>
        )}
      </div>
    </div>
  )
}

interface StackConsultationProps {
  talked: boolean
  busy: boolean
  onTalk: () => void
  onRecommend: () => void
}

/** Like a doctor with a treatment plan: the agent learns about the student before recommending. */
function StackConsultation({ talked, busy, onTalk, onRecommend }: StackConsultationProps) {
  return (
    <div className="mt-6 w-full space-y-4 text-left">
      <p className="rounded-lg border border-sky/30 bg-sky/5 p-4 text-sm text-muted">
        Every developer works with different tools. Tell the Tech Stack Agent about yourself in the chat: the languages
        you know, what you want to learn and where you want to host. It recommends one plan built around you, explains
        why, and you have the final say.
      </p>
      <div className="flex flex-wrap justify-center gap-2">
        {!talked && (
          <Button variant="secondary" onClick={onTalk} disabled={busy}>
            <MessageSquare aria-hidden="true" /> Start the conversation
          </Button>
        )}
        <Button variant="ai" onClick={onRecommend}>
          <Play aria-hidden="true" /> {talked ? 'Recommend my stack' : 'Skip and recommend a stack'}
        </Button>
      </div>
    </div>
  )
}
