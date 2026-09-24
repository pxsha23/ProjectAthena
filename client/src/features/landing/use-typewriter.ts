import { useReducedMotion } from 'framer-motion'
import { useEffect, useState } from 'react'

interface TypewriterOptions {
  typeMs?: number
  deleteMs?: number
  holdMs?: number
  /** Type the first phrase once and stop, instead of cycling. */
  once?: boolean
  enabled?: boolean
}

/**
 * Types each phrase out, holds it, deletes it and moves to the next.
 * With reduced motion it returns the first phrase in full.
 */
export function useTypewriter(
  phrases: string[],
  { typeMs = 45, deleteMs = 20, holdMs = 1800, once = false, enabled = true }: TypewriterOptions = {},
): string {
  const reduced = useReducedMotion()
  const [index, setIndex] = useState(0)
  const [length, setLength] = useState(0)
  const [deleting, setDeleting] = useState(false)

  const phrase = phrases[index % phrases.length] ?? ''
  const animate = enabled && !reduced

  useEffect(() => {
    if (!animate) return
    let delay = deleting ? deleteMs : typeMs
    if (!deleting && length === phrase.length) {
      if (once) return
      delay = holdMs
    }
    const timer = setTimeout(() => {
      if (!deleting && length === phrase.length) setDeleting(true)
      else if (deleting && length === 0) {
        setDeleting(false)
        setIndex((i) => i + 1)
      } else setLength((l) => l + (deleting ? -1 : 1))
    }, delay)
    return () => clearTimeout(timer)
  }, [animate, deleting, length, phrase.length, typeMs, deleteMs, holdMs, once])

  if (!animate) return phrases[0] ?? ''
  return phrase.slice(0, length)
}
