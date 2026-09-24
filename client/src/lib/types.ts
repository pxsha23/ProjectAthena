/**
 * Shared types. Everything under "API" mirrors the FastAPI schemas in server/app/schemas
 * (camelCase JSON). Keep them in sync when the backend changes.
 */

/* ------------------------------------------------------------------ */
/* Agents and stages (client constants)                                */
/* ------------------------------------------------------------------ */

export type AgentId = 'idea' | 'stack' | 'code' | 'deploy' | 'eva'

export type AccentColor = 'lavender' | 'mauve' | 'green' | 'peach' | 'red' | 'sky' | 'yellow' | 'pink'

export interface Agent {
  id: AgentId
  name: string
  shortName: string
  color: AccentColor
  role: string
  description: string
}

/** Five pipeline stages. The Idea Agent writes the spec as part of the first stage. */
export type StageId = 'idea' | 'stack' | 'code' | 'export' | 'deploy'

/** Anything that can be run on the server: the five stages plus EVA. */
export type RunnableStage = 'idea' | 'stack' | 'code' | 'eva' | 'export' | 'deploy'

export interface Stage {
  id: StageId
  label: string
  agentId: AgentId
  description: string
}

export type StageStatus = 'done' | 'active' | 'pending'

/* ------------------------------------------------------------------ */
/* API: auth                                                           */
/* ------------------------------------------------------------------ */

export interface User {
  id: string
  name: string
  email: string | null
  githubUsername: string | null
  hasGithubToken: boolean
}

/* ------------------------------------------------------------------ */
/* API: projects                                                       */
/* ------------------------------------------------------------------ */

export type ProjectStatus = 'draft' | 'in-progress' | 'ready' | 'deployed'

export interface Project {
  id: string
  name: string
  description: string
  idea: string
  /** The furthest stage the pipeline has reached. */
  stage: StageId
  status: ProjectStatus
  /** False until the Idea Agent has written the spec (the first half of stage 1). */
  specReady: boolean
  /** Set while an agent is working on this project. */
  runningStage: RunnableStage | null
  starred: boolean
  /** Short technology names, e.g. ["React + Vite", "FastAPI (Python)"]. */
  stack: string[]
  createdAt: string
  updatedAt: string
}

export interface ProjectDetail extends Project {
  spec: ProjectSpec | null
  stackPlan: StackPlan | null
  eva: EvaReport | null
  deployment: DeploymentBundle | null
  learning: LearningSummary | null
}

export type FileLanguage =
  | 'typescript'
  | 'javascript'
  | 'python'
  | 'json'
  | 'markdown'
  | 'css'
  | 'html'
  | 'yaml'
  | 'toml'
  | 'dockerfile'
  | 'plaintext'

export interface ProjectFile {
  path: string
  language: FileLanguage
  content: string
  /** Who wrote the current content: an agent ("code", "deploy") or "user". */
  source: string
  updatedAt: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'agent'
  agentId: AgentId | null
  content: string
  createdAt: string
}

/* ------------------------------------------------------------------ */
/* API: agent outputs                                                  */
/* ------------------------------------------------------------------ */

export interface SpecSection {
  title: string
  items: string[]
}

export interface ProjectSpec {
  summary: string
  targetUsers: string[]
  sections: SpecSection[]
  openQuestions: string[]
}

export type StackLayer = 'frontend' | 'backend' | 'database' | 'auth' | 'hosting' | 'other'

export interface StackChoice {
  layer: StackLayer
  name: string
  reason: string
  alternatives: string[]
}

export interface StackPlan {
  choices: StackChoice[]
  backendLanguage: string
  frontendFramework: string
  backendFramework: string
  database: string
}

export type EvaSeverity = 'pass' | 'warn' | 'fail'

export interface EvaPersona {
  id: string
  name: string
  archetype: string
  goal: string
}

export interface EvaFinding {
  id: string
  personaId: string
  severity: EvaSeverity
  title: string
  detail: string
}

export interface EvaReport {
  score: number
  personas: EvaPersona[]
  findings: EvaFinding[]
}

export interface DeploymentTarget {
  id: string
  name: string
  description: string
  files: string[]
}

export interface StackDetection {
  backendLanguage: 'python' | 'node' | 'none'
  backendFramework: string | null
  backendDir: string | null
  pythonEntryModule: string | null
  frontendFramework: string | null
  frontendDir: string | null
  database: string
  evidence: string[]
}

export interface DeploymentBundle {
  detection: StackDetection
  targets: DeploymentTarget[]
  files: { path: string; language: FileLanguage; content: string; purpose: string }[]
}

export interface LearningTerm {
  term: string
  meaning: string
}

export interface LearningTopic {
  title: string
  summary: string[]
  concepts: string[]
  howItWorks: string[]
  files: string[]
  keyTerms: LearningTerm[]
  tryIt: string
}

export interface LearningOverview {
  summary: string[]
  stats: { label: string; value: string }[]
  nextSteps: string[]
}

export interface LearningSummary {
  overview: LearningOverview
  topics: LearningTopic[]
}

/* ------------------------------------------------------------------ */
/* API: measurements                                                   */
/* ------------------------------------------------------------------ */

export interface AgentRun {
  id: string
  agent: string
  stage: string | null
  provider: string
  model: string | null
  status: 'running' | 'succeeded' | 'failed'
  startedAt: string
  durationMs: number | null
  inputTokens: number
  outputTokens: number
  retries: number
  validationErrors: { attempt: number; error: string }[]
  error: string | null
}

export interface ConsistencyCheck {
  id: string
  stage: string
  checkName: string
  passed: boolean
  severity: 'info' | 'warning' | 'error'
  message: string
  details: Record<string, unknown>
  durationMs: number
  createdAt: string
}

export interface SearchHit {
  filePath: string
  startLine: number
  endLine: number
  content: string
  score: number
}

export interface GithubExportResult {
  repoUrl: string
  fullName: string
  commitSha: string
}

/* ------------------------------------------------------------------ */
/* API: real-time progress (WebSocket)                                 */
/* ------------------------------------------------------------------ */

export type ProgressEvent =
  | { type: 'subscribed'; projectId: string }
  | { type: 'stage_started'; stage: RunnableStage; at: string }
  | { type: 'agent_started'; agent: string; stage: RunnableStage; at: string }
  | { type: 'agent_succeeded'; agent: string; runId: string; durationMs: number; retries: number; at: string }
  | { type: 'checks_completed'; stage: string; passed: number; total: number; failed: string[]; at: string }
  | { type: 'index_updated'; chunks: number; at: string }
  | { type: 'stage_completed'; stage: RunnableStage; projectStage: StageId; status: ProjectStatus; at: string }
  | { type: 'stage_failed'; stage: RunnableStage; agent?: string; runId?: string; error: string; at: string }

/* ------------------------------------------------------------------ */
/* Client-only                                                         */
/* ------------------------------------------------------------------ */

/** Explorer tree node, built from the flat file list. */
export interface FileNode {
  id: string
  name: string
  path: string
  type: 'file' | 'folder'
  language?: FileLanguage
  children?: FileNode[]
}

/** A line in the workspace Output tab (built from agent runs and live events). */
export interface OutputLine {
  id: string
  time: string
  source: 'system' | string
  text: string
  tone?: 'default' | 'success' | 'error'
}

export type CodeTokenTone = 'plain' | 'keyword' | 'string' | 'fn' | 'type' | 'comment' | 'number' | 'punct'

export interface CodeToken {
  text: string
  tone?: CodeTokenTone
}

export interface LandingShowcase {
  idea: string
  specItems: string[]
  stack: { layer: string; name: string; why: string }[]
  codeFile: string
  codeLines: CodeToken[][]
  eva: { personas: number; score: number }
  repo: string
  fileCount: number
  deployLog: string[]
  liveUrl: string
  learned: string[]
}
