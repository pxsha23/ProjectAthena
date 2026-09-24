import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion'
import { ChevronRight, Files, FileCode, Folder, Workflow } from 'lucide-react'
import { useRef } from 'react'
import { AgentAvatar } from '@/components/agent-badge'
import { Spotlight } from '@/components/spotlight'
import { AGENTS, STAGES, agentClasses } from '@/lib/agents'
import { LANDING_SHOWCASE as S } from '@/lib/landing-content'
import type { AgentId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { SectionHeading } from './section-heading'

const FEATURES = [
  { title: 'Built-in code editor', body: 'A full code editor with syntax colours, search and Ctrl+S to save.' },
  { title: 'Agents beside your code', body: 'Ask any agent a question without leaving the file you are reading.' },
  { title: 'Always know where you are', body: 'The five-step pipeline sits in the header. Jump back to any stage.' },
]

const CHAT: { agentId: AgentId; text: string }[] = [
  { agentId: 'code', text: 'Generated 11 files. Start with backend/main.py.' },
  { agentId: 'eva', text: '3 virtual users tested the app. Score 82/100.' },
  { agentId: 'deploy', text: 'Deployment files and your learning summary are ready.' },
]

export function WorkspaceShowcase() {
  const ref = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start end', 'center center'] })
  const rotateX = useTransform(scrollYProgress, [0, 1], [24, 0])
  const scale = useTransform(scrollYProgress, [0, 1], [0.88, 1])
  const opacity = useTransform(scrollYProgress, [0, 0.4], [0.3, 1])

  return (
    <section id="workspace" aria-labelledby="workspace-heading" className="scroll-mt-20 overflow-hidden border-t border-border py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <SectionHeading
          id="workspace-heading"
          eyebrow="The workspace"
          title="A clean workspace for every project"
          description="Every project opens in one clean workspace: files on the left, code in the middle, agents on the right."
        />

        <div ref={ref} className="mt-14 [perspective:1400px]">
          <motion.div
            style={reduced ? undefined : { rotateX, scale, opacity }}
            className="origin-top overflow-hidden rounded-2xl border border-border bg-panel shadow-2xl shadow-lavender/10"
          >
            <Spotlight border={false} size={600}>
              <MockWorkspace />
            </Spotlight>
          </motion.div>
        </div>

        <ul className="mt-12 grid gap-6 sm:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.li
              key={f.title}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="border-l border-border pl-4"
            >
              <h3 className="font-medium">{f.title}</h3>
              <p className="mt-1 text-sm text-muted">{f.body}</p>
            </motion.li>
          ))}
        </ul>
      </div>
    </section>
  )
}

/** Static, decorative imitation of the real workspace. */
function MockWorkspace() {
  return (
    <div aria-hidden="true" className="text-left">
      {/* Header with pipeline */}
      <div className="flex h-11 items-center gap-3 border-b border-border px-4">
        <span className="text-sm font-semibold">StudySync</span>
        <div className="mx-auto hidden items-center gap-1 md:flex">
          {STAGES.map((stage, i) => (
            <span key={stage.id} className="flex items-center gap-1">
              {i > 0 && <span className={cn('h-px w-4', agentClasses(stage.agentId).bg)} />}
              <span
                className={cn(
                  'rounded-md px-2 py-0.5 text-[11px]',
                  stage.id === 'code' ? cn('bg-raised', agentClasses('code').text) : 'text-muted',
                )}
              >
                {stage.label}
              </span>
            </span>
          ))}
        </div>
        <span className="ml-auto rounded-md bg-lavender px-2.5 py-1 text-[11px] font-medium text-on-accent md:ml-0">Export</span>
      </div>

      <div className="grid h-[340px] grid-cols-[40px_minmax(0,1fr)] md:grid-cols-[40px_180px_minmax(0,1fr)_240px]">
        {/* Activity bar */}
        <div className="flex flex-col items-center gap-3 border-r border-border bg-base py-3 text-subtle">
          <Files className="size-4 text-text" />
          <Workflow className="size-4" />
        </div>

        {/* Explorer */}
        <div className="hidden border-r border-border py-2 text-xs md:block">
          <p className="px-3 pb-2 text-[10px] font-semibold tracking-wider text-subtle uppercase">Explorer</p>
          {[
            { name: 'backend', folder: true, depth: 0 },
            { name: 'main.py', depth: 1, active: true },
            { name: 'models.py', depth: 1 },
            { name: 'frontend', folder: true, depth: 0 },
            { name: 'App.tsx', depth: 1 },
            { name: 'Dockerfile', depth: 0 },
            { name: 'README.md', depth: 0 },
          ].map((f) => (
            <div
              key={f.name}
              style={{ paddingLeft: `${f.depth * 12 + 12}px` }}
              className={cn('flex items-center gap-1.5 py-1', f.active ? 'bg-lavender/10 text-text' : 'text-muted')}
            >
              {f.folder ? (
                <>
                  <ChevronRight className="size-3 rotate-90 text-subtle" />
                  <Folder className="size-3.5 text-lavender" />
                </>
              ) : (
                <FileCode className="ml-4 size-3.5 text-yellow" />
              )}
              {f.name}
            </div>
          ))}
        </div>

        {/* Editor */}
        <div className="min-w-0 border-r border-border">
          <div className="flex h-8 items-center border-b border-border bg-base text-xs">
            <span className="relative flex h-full items-center border-r border-border bg-panel px-3 text-text">
              <span className="absolute inset-x-0 top-0 h-0.5 bg-lavender" />
              main.py
            </span>
            <span className="px-3 text-subtle">App.tsx</span>
          </div>
          <div className="py-2 font-mono text-[11px] leading-5">
            {S.codeLines.map((line, i) => (
              <div key={i} className="flex whitespace-pre">
                <span className="w-9 shrink-0 pr-3 text-right text-subtle/70">{i + 1}</span>
                <span className="truncate">
                  {line.map((token, j) => (
                    <span
                      key={j}
                      className={cn(
                        token.tone === 'keyword' && 'text-mauve',
                        token.tone === 'string' && 'text-green',
                        token.tone === 'fn' && 'text-lavender',
                        token.tone === 'type' && 'text-yellow',
                        token.tone === 'comment' && 'text-subtle',
                        token.tone === 'number' && 'text-peach',
                        (!token.tone || token.tone === 'punct') && 'text-text',
                      )}
                    >
                      {token.text}
                    </span>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Agent chat */}
        <div className="hidden flex-col gap-3 p-3 md:flex">
          <p className="text-[10px] font-semibold tracking-wider text-subtle uppercase">Agents</p>
          {CHAT.map((m) => (
            <div key={m.agentId} className="flex gap-2">
              <AgentAvatar agentId={m.agentId} size="sm" />
              <div className="min-w-0">
                <p className={cn('text-[10px] font-medium', agentClasses(m.agentId).text)}>{AGENTS[m.agentId].name}</p>
                <p className="mt-0.5 rounded-md border border-border bg-raised/50 px-2 py-1.5 text-[11px] text-text">
                  {m.text}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
