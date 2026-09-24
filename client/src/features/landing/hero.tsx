import { motion, type Variants } from 'framer-motion'
import { ArrowRight, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Spotlight } from '@/components/spotlight'
import { Button } from '@/components/ui/button'
import { IDEA_SUGGESTIONS } from '@/lib/landing-content'
import { AgentFlow } from './agent-flow'
import { Aurora } from './aurora'
import { useTypewriter } from './use-typewriter'

const HEADLINE = ['Turn', 'an', 'idea', 'into', 'a']

const word: Variants = {
  hidden: { opacity: 0, y: 18, filter: 'blur(8px)' },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    filter: 'blur(0px)',
    transition: { delay: 0.1 + i * 0.07, duration: 0.5, ease: 'easeOut' },
  }),
}

const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: (delay: number) => ({ opacity: 1, y: 0, transition: { delay, duration: 0.5, ease: 'easeOut' } }),
}

export function Hero() {
  const [idea, setIdea] = useState('')
  const [focused, setFocused] = useState(false)
  const navigate = useNavigate()
  const typed = useTypewriter(IDEA_SUGGESTIONS, { enabled: !focused && idea === '' })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = idea.trim()
    // RequireAuth sends signed-out users to /login and brings them back here afterwards.
    navigate(trimmed ? `/dashboard?idea=${encodeURIComponent(trimmed)}` : '/dashboard')
  }

  return (
    <section className="relative isolate overflow-hidden">
      <Aurora />

      <div className="relative mx-auto flex max-w-6xl flex-col items-center px-4 pt-20 pb-20 text-center sm:px-6 sm:pt-28">
        <motion.span
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={0}
          className="relative mb-8 inline-flex items-center gap-2 overflow-hidden rounded-full border border-border bg-panel/80 px-3.5 py-1.5 text-xs font-medium text-muted backdrop-blur"
        >
          <Sparkles className="size-3.5 text-mauve" aria-hidden="true" />
          Five AI agents. One pipeline.
          <span
            aria-hidden="true"
            className="absolute inset-0 animate-shimmer bg-linear-to-r from-transparent via-text/10 to-transparent bg-[length:200%_100%]"
          />
        </motion.span>

        <h1 className="max-w-4xl text-4xl leading-[1.08] font-semibold tracking-tight text-balance sm:text-6xl lg:text-7xl">
          <span className="sr-only">Turn an idea into a deployed app.</span>
          <span aria-hidden="true">
            {HEADLINE.map((w, i) => (
              <motion.span key={w + i} variants={word} initial="hidden" animate="show" custom={i} className="mr-[0.25em] inline-block">
                {w}
              </motion.span>
            ))}
            <motion.span
              variants={word}
              initial="hidden"
              animate="show"
              custom={HEADLINE.length}
              className="inline-block animate-gradient-x bg-linear-to-r from-lavender via-mauve to-pink bg-[length:200%_auto] bg-clip-text pb-1 text-transparent"
            >
              deployed app.
            </motion.span>
          </span>
        </h1>

        <motion.p
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={0.55}
          className="mt-6 max-w-2xl text-base text-muted text-pretty sm:text-lg"
        >
          Athena's agents write the spec, choose the stack, generate the code in a built-in editor, test it with
          virtual users and hand you deployment files, explaining every step along the way.
        </motion.p>

        <motion.form
          onSubmit={handleSubmit}
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={0.7}
          className="relative mt-10 w-full max-w-2xl"
        >
          {/* Rotating gradient border, plus a blurred copy behind it for the glow. */}
          <div aria-hidden="true" className="glow-border absolute -inset-px rounded-2xl opacity-60 blur-lg" />
          <div className="glow-border relative rounded-2xl p-px">
            <div className="flex flex-col gap-2 rounded-[15px] bg-panel p-2 sm:flex-row">
              <label htmlFor="hero-idea" className="sr-only">
                Describe your app idea
              </label>
              <input
                id="hero-idea"
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder={focused ? 'Describe your app idea…' : typed}
                autoComplete="off"
                className="h-12 min-w-0 flex-1 bg-transparent px-3 text-text placeholder:text-subtle focus:outline-none"
              />
              <Button type="submit" size="lg" className="group">
                Start building
                <ArrowRight className="transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
              </Button>
            </div>
          </div>
        </motion.form>

        <motion.div
          variants={fadeUp}
          initial="hidden"
          animate="show"
          custom={0.9}
          className="mt-20 w-full max-w-5xl rounded-2xl border border-border bg-panel/60 backdrop-blur"
        >
          <Spotlight className="rounded-2xl px-4 py-8 sm:px-8">
            <AgentFlow />
          </Spotlight>
        </motion.div>
      </div>
    </section>
  )
}
