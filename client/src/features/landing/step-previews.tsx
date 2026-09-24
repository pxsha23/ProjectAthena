/**
 * Animated mini-previews for the landing page's "How it works" section,
 * one per pipeline stage. Content comes from LANDING_SHOWCASE in landing-content.
 */
import { motion, type Variants } from 'framer-motion'
import { Check, CheckCircle2, Download, FileArchive, Loader2, UsersRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AgentAvatar } from '@/components/agent-badge'
import { GithubIcon } from '@/components/icons'
import { LANDING_SHOWCASE as S } from '@/lib/landing-content'
import type { CodeTokenTone, StageId } from '@/lib/types'
import { cn } from '@/lib/utils'
import { useTypewriter } from './use-typewriter'

const list: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.12, delayChildren: 0.15 } } }
const item: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: 'easeOut' } },
}

/** Flips to true after `ms`, used to sequence steps inside a preview. */
function useAfter(ms: number): boolean {
  const [done, setDone] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => setDone(true), ms)
    return () => clearTimeout(timer)
  }, [ms])
  return done
}

export function StepPreview({ stage }: { stage: StageId }) {
  switch (stage) {
    case 'idea':
      return <IdeaPreview />
    case 'stack':
      return <StackPreview />
    case 'code':
      return <CodePreview />
    case 'export':
      return <ExportPreview />
    case 'deploy':
      return <DeployPreview />
  }
}

/* ---------------- 1. Idea & Spec ---------------- */

function IdeaPreview() {
  const typed = useTypewriter([S.idea], { once: true, typeMs: 22 })
  const specShown = useAfter(S.idea.length * 22 + 400)

  return (
    <div className="flex h-full flex-col gap-4 p-5">
      <div className="ml-auto max-w-[85%] rounded-lg border border-lavender/30 bg-lavender/10 px-3 py-2 text-sm">
        {typed}
        {!specShown && <span className="ml-0.5 inline-block h-4 w-px translate-y-0.5 animate-blink bg-text" />}
      </div>
      {specShown && (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex gap-3">
          <AgentAvatar agentId="idea" size="sm" />
          <div className="min-w-0 flex-1 rounded-lg border border-border bg-raised/40 p-3">
            <p className="text-xs font-medium text-pink">Spec ready</p>
            <motion.ul variants={list} initial="hidden" animate="show" className="mt-2 space-y-1.5">
              {S.specItems.map((spec) => (
                <motion.li key={spec} variants={item} className="flex items-start gap-2 text-sm">
                  <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-pink" aria-hidden="true" />
                  {spec}
                </motion.li>
              ))}
            </motion.ul>
          </div>
        </motion.div>
      )}
    </div>
  )
}

/* ---------------- 2. Tech Stack ---------------- */

function StackPreview() {
  return (
    <motion.ul variants={list} initial="hidden" animate="show" className="grid h-full content-center gap-3 p-5 sm:grid-cols-2">
      {S.stack.map((choice) => (
        <motion.li
          key={choice.layer}
          variants={{
            hidden: { opacity: 0, scale: 0.92 },
            show: { opacity: 1, scale: 1, transition: { type: 'spring', stiffness: 260, damping: 20 } },
          }}
          className="rounded-lg border border-sky/25 bg-sky/5 p-4"
        >
          <p className="font-mono text-[10px] tracking-widest text-sky uppercase">{choice.layer}</p>
          <p className="mt-1 font-semibold">{choice.name}</p>
          <p className="mt-1 text-xs text-muted">{choice.why}</p>
        </motion.li>
      ))}
    </motion.ul>
  )
}

/* ---------------- 3. Code (+ EVA) ---------------- */

const TONE: Record<CodeTokenTone, string> = {
  plain: 'text-text',
  keyword: 'text-mauve',
  string: 'text-green',
  fn: 'text-lavender',
  type: 'text-yellow',
  comment: 'text-subtle italic',
  number: 'text-peach',
  punct: 'text-muted',
}

function CodePreview() {
  const evaShown = useAfter(S.codeLines.length * 90 + 500)
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-8 shrink-0 items-center gap-4 border-b border-border px-4 font-mono text-xs">
        <span className="text-text">{S.codeFile.split('/').pop()}</span>
        <span className="text-subtle">App.tsx</span>
        <span className="text-subtle">models.py</span>
      </div>
      <motion.ol
        initial="hidden"
        animate="show"
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.09 } } }}
        className="min-h-0 flex-1 overflow-hidden py-3 font-mono text-[12px] leading-5"
      >
        {S.codeLines.map((line, i) => (
          <motion.li
            key={i}
            variants={{ hidden: { opacity: 0, x: -6 }, show: { opacity: 1, x: 0 } }}
            className="flex whitespace-pre"
          >
            <span className="w-10 shrink-0 pr-4 text-right text-subtle/70 select-none">{i + 1}</span>
            <span>
              {line.map((token, j) => (
                <span key={j} className={TONE[token.tone ?? 'plain']}>
                  {token.text}
                </span>
              ))}
            </span>
          </motion.li>
        ))}
      </motion.ol>
      <div className="flex shrink-0 items-center gap-3 border-t border-border bg-raised/30 px-4 py-2.5 text-xs">
        <UsersRound className="size-4 text-peach" aria-hidden="true" />
        {evaShown ? (
          <>
            <span className="text-muted">
              EVA ran <span className="text-text">{S.eva.personas} virtual users</span>
            </span>
            <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-raised">
              <motion.span
                className="absolute inset-y-0 left-0 rounded-full bg-peach"
                initial={{ width: 0 }}
                animate={{ width: `${S.eva.score}%` }}
                transition={{ duration: 1, ease: 'easeOut' }}
              />
            </span>
            <span className="font-mono text-peach">{S.eva.score}/100</span>
          </>
        ) : (
          <span className="flex items-center gap-2 text-subtle">
            <Loader2 className="size-3 animate-spin" aria-hidden="true" /> Waiting for code…
          </span>
        )}
      </div>
    </div>
  )
}

/* ---------------- 4. Export ---------------- */

function ExportPreview() {
  const pushed = useAfter(1900)
  return (
    <div className="flex h-full flex-col justify-center gap-4 p-5">
      <div className="rounded-lg border border-border bg-raised/30 p-4">
        <div className="flex items-center gap-3">
          <GithubIcon className="size-5 text-text" aria-hidden="true" />
          <span className="font-mono text-sm">{S.repo}</span>
          <span className="ml-auto rounded-full border border-border px-2 py-0.5 text-[10px] text-subtle">Private</span>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-raised">
          <motion.div
            className="h-full rounded-full bg-mauve"
            initial={{ width: '0%' }}
            animate={{ width: '100%' }}
            transition={{ duration: 1.8, ease: 'easeInOut' }}
          />
        </div>
        <p className="mt-2 flex items-center gap-1.5 text-xs">
          {pushed ? (
            <>
              <Check className="size-3.5 text-green" aria-hidden="true" />
              <span className="text-green">Pushed {S.fileCount} files to main</span>
            </>
          ) : (
            <span className="text-muted">Pushing {S.fileCount} files…</span>
          )}
        </p>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
        className="flex items-center gap-3 rounded-lg border border-border bg-raised/30 p-4"
      >
        <FileArchive className="size-5 text-mauve" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-sm">studysync.zip</p>
          <p className="text-xs text-subtle">{S.fileCount} files, ready to download</p>
        </div>
        <Download className="size-4 text-muted" aria-hidden="true" />
      </motion.div>
    </div>
  )
}

/* ---------------- 5. Deploy ---------------- */

function DeployPreview() {
  const [shown, setShown] = useState(0)
  useEffect(() => {
    if (shown > S.deployLog.length) return
    const timer = setTimeout(() => setShown((n) => n + 1), 450)
    return () => clearTimeout(timer)
  }, [shown])
  const live = shown > S.deployLog.length

  return (
    <div className="flex h-full flex-col gap-4 p-5">
      <ol className="space-y-1.5 rounded-lg border border-border bg-base/60 p-4 font-mono text-xs">
        {S.deployLog.slice(0, shown).map((line, i) => (
          <motion.li key={line} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2">
            <span className="text-subtle">{String(i + 1).padStart(2, '0')}</span>
            <Check className="size-3 text-green" aria-hidden="true" />
            <span className="text-muted">{line}</span>
          </motion.li>
        ))}
        {live && (
          <motion.li initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 pt-1 text-green">
            <span className="relative flex size-2">
              <span className="absolute inset-0 animate-ping rounded-full bg-green/70" />
              <span className="relative size-2 rounded-full bg-green" />
            </span>
            Live at {S.liveUrl}
          </motion.li>
        )}
      </ol>
      <div className={cn('transition-opacity duration-500', live ? 'opacity-100' : 'opacity-0')}>
        <p className="text-xs text-subtle">Learning summary</p>
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {S.learned.map((topic) => (
            <li key={topic} className="rounded-full border border-green/30 bg-green/10 px-2.5 py-0.5 text-xs text-green">
              {topic}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
