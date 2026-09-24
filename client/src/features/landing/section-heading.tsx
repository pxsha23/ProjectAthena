import { motion } from 'framer-motion'
import type { ReactNode } from 'react'

interface SectionHeadingProps {
  id?: string
  eyebrow: string
  title: ReactNode
  description?: ReactNode
}

export function SectionHeading({ id, eyebrow, title, description }: SectionHeadingProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className="mx-auto max-w-2xl text-center"
    >
      <p className="font-mono text-xs tracking-widest text-lavender uppercase">{eyebrow}</p>
      <h2 id={id} className="mt-3 text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
        {title}
      </h2>
      {description && <p className="mt-4 text-muted text-pretty">{description}</p>}
    </motion.div>
  )
}
