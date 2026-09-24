import type { AccentColor, Agent, AgentId, Stage, StageId } from './types'

export const AGENTS: Record<AgentId, Agent> = {
  idea: {
    id: 'idea',
    name: 'Idea Agent',
    shortName: 'Idea',
    color: 'pink',
    role: 'Product thinker',
    description: 'Turns a rough idea into a clear problem statement, feature list and written spec.',
  },
  stack: {
    id: 'stack',
    name: 'Tech Stack Agent',
    shortName: 'Stack',
    color: 'sky',
    role: 'Architect',
    description: 'Picks frameworks, database and hosting that fit the spec, and explains every choice.',
  },
  code: {
    id: 'code',
    name: 'Code Agent',
    shortName: 'Code',
    color: 'mauve',
    role: 'Engineer',
    description: 'Generates the project files and edits them with you inside the built-in editor.',
  },
  deploy: {
    id: 'deploy',
    name: 'Deployment & Summary Agent',
    shortName: 'Deploy',
    color: 'green',
    role: 'DevOps & mentor',
    description: 'Writes deployment configs and a learning summary of everything that was built.',
  },
  eva: {
    id: 'eva',
    name: 'EVA',
    shortName: 'EVA',
    color: 'peach',
    role: 'Virtual users',
    description: 'Simulates realistic users who walk through your app and report what breaks.',
  },
}

export const AGENT_LIST: Agent[] = Object.values(AGENTS)

export const STAGES: Stage[] = [
  { id: 'idea', label: 'Idea & Spec', agentId: 'idea', description: 'Your idea, turned into a written spec.' },
  { id: 'stack', label: 'Tech Stack', agentId: 'stack', description: 'Frameworks, data and hosting.' },
  { id: 'code', label: 'Code', agentId: 'code', description: 'Generated source in the editor.' },
  { id: 'export', label: 'Export', agentId: 'code', description: 'Push to GitHub or download a zip.' },
  { id: 'deploy', label: 'Deploy', agentId: 'deploy', description: 'Deployment files & learning summary.' },
]

export function stageIndex(id: StageId): number {
  return STAGES.findIndex((stage) => stage.id === id)
}

export function getStage(id: StageId): Stage {
  return STAGES[stageIndex(id)]!
}

export interface AccentClassSet {
  text: string
  bg: string
  bgSoft: string
  border: string
  ring: string
  /** Coloured drop shadow, combine with a shadow size (e.g. shadow-lg). */
  glow: string
  /** Gradient middle stop, combine with bg-linear-to-r from-transparent to-transparent. */
  via: string
  /** CSS custom property reference for inline styles (e.g. radial gradients). */
  cssVar: string
}

/**
 * Static class maps so Tailwind can detect every class at build time.
 * Always go through these instead of building class names from strings.
 */
export const ACCENT_CLASSES: Record<AccentColor, AccentClassSet> = {
  lavender: {
    text: 'text-lavender',
    bg: 'bg-lavender',
    bgSoft: 'bg-lavender/10',
    border: 'border-lavender/30',
    ring: 'ring-lavender/40',
    glow: 'shadow-lavender/25',
    via: 'via-lavender',
    cssVar: 'var(--color-lavender)',
  },
  mauve: {
    text: 'text-mauve',
    bg: 'bg-mauve',
    bgSoft: 'bg-mauve/10',
    border: 'border-mauve/30',
    ring: 'ring-mauve/40',
    glow: 'shadow-mauve/25',
    via: 'via-mauve',
    cssVar: 'var(--color-mauve)',
  },
  green: {
    text: 'text-green',
    bg: 'bg-green',
    bgSoft: 'bg-green/10',
    border: 'border-green/30',
    ring: 'ring-green/40',
    glow: 'shadow-green/25',
    via: 'via-green',
    cssVar: 'var(--color-green)',
  },
  peach: {
    text: 'text-peach',
    bg: 'bg-peach',
    bgSoft: 'bg-peach/10',
    border: 'border-peach/30',
    ring: 'ring-peach/40',
    glow: 'shadow-peach/25',
    via: 'via-peach',
    cssVar: 'var(--color-peach)',
  },
  red: {
    text: 'text-red',
    bg: 'bg-red',
    bgSoft: 'bg-red/10',
    border: 'border-red/30',
    ring: 'ring-red/40',
    glow: 'shadow-red/25',
    via: 'via-red',
    cssVar: 'var(--color-red)',
  },
  sky: {
    text: 'text-sky',
    bg: 'bg-sky',
    bgSoft: 'bg-sky/10',
    border: 'border-sky/30',
    ring: 'ring-sky/40',
    glow: 'shadow-sky/25',
    via: 'via-sky',
    cssVar: 'var(--color-sky)',
  },
  yellow: {
    text: 'text-yellow',
    bg: 'bg-yellow',
    bgSoft: 'bg-yellow/10',
    border: 'border-yellow/30',
    ring: 'ring-yellow/40',
    glow: 'shadow-yellow/25',
    via: 'via-yellow',
    cssVar: 'var(--color-yellow)',
  },
  pink: {
    text: 'text-pink',
    bg: 'bg-pink',
    bgSoft: 'bg-pink/10',
    border: 'border-pink/30',
    ring: 'ring-pink/40',
    glow: 'shadow-pink/25',
    via: 'via-pink',
    cssVar: 'var(--color-pink)',
  },
}

export function agentClasses(id: AgentId): AccentClassSet {
  return ACCENT_CLASSES[AGENTS[id].color]
}
