/**
 * State for one open project workspace, backed by the Athena API:
 * - server state (project, files, chat, runs, checks) comes from TanStack Query,
 * - stages run on the server and report progress over the project WebSocket,
 * - editor edits stay local until saved (Ctrl+S) and are then written with PUT.
 */
import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  keys,
  useChecksQuery,
  useFilesQuery,
  useMessagesQuery,
  useRunStage,
  useRunsQuery,
  useSaveFile,
  useSendMessage,
} from '@/lib/api/queries'
import { STAGES, stageIndex } from '@/lib/agents'
import type {
  AgentId,
  AgentRun,
  ChatMessage,
  ConsistencyCheck,
  FileNode,
  OutputLine,
  ProgressEvent,
  ProjectDetail,
  ProjectFile,
  RunnableStage,
  StageId,
  StageStatus,
} from '@/lib/types'
import { buildFileTree, defaultFile } from './files'
import { useProjectEvents } from './use-project-events'

export type SidebarView = 'explorer' | 'search' | 'pipeline'
export type BottomTab = 'eva' | 'checks' | 'output'

export interface CursorPosition {
  line: number
  column: number
}

/** Maps a server agent/stage name to the UI agent that owns it (colours, icons). */
export function uiAgent(name: string | null | undefined): AgentId {
  switch (name) {
    case 'stack':
    case 'code':
    case 'eva':
    case 'deploy':
      return name
    case 'summary':
      return 'deploy'
    case 'export':
      return 'code'
    default:
      return 'idea'
  }
}

interface WorkspaceContextValue {
  project: ProjectDetail

  /* Pipeline */
  view: StageId
  setView: (stage: StageId) => void
  stageStatus: (stage: StageId) => StageStatus
  isReached: (stage: StageId) => boolean
  nextStage: StageId | null
  /** True when the current stage is finished and the next one can start. */
  canAdvance: boolean
  runningStage: RunnableStage | null
  runningAgent: AgentId | null
  runNextStage: () => void
  /** First half of stage 1: the Idea Agent turns the idea into a spec. */
  generateSpec: () => void
  /** Last failure reported by the server for a stage, until dismissed. */
  runError: string | null
  dismissRunError: () => void

  /* Files & editor */
  files: ProjectFile[]
  filesLoading: boolean
  fileTree: FileNode[]
  fileIndex: Map<string, ProjectFile>
  openTabs: string[]
  activeFile: string | null
  openFile: (path: string, line?: number) => void
  closeFile: (path: string) => void
  getContent: (path: string) => string
  updateContent: (path: string, value: string) => void
  dirty: ReadonlySet<string>
  saving: ReadonlySet<string>
  saveFile: (path: string) => void
  saveError: string | null
  /** A line to scroll to in the active file (set by search results), consumed by the editor. */
  reveal: { path: string; line: number; nonce: number } | null
  cursor: CursorPosition
  setCursor: (cursor: CursorPosition) => void

  /* Chat */
  messages: ChatMessage[]
  typingAgent: AgentId | null
  sendMessage: (content: string, agentId: AgentId) => void
  chatError: string | null

  /* EVA, checks, output */
  evaRunning: boolean
  runEva: () => void
  runs: AgentRun[]
  checks: ConsistencyCheck[]
  output: OutputLine[]
  bottomTab: BottomTab
  setBottomTab: (tab: BottomTab) => void
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

const STAGE_TO_VIEW: Record<RunnableStage, StageId> = {
  idea: 'idea',
  stack: 'stack',
  code: 'code',
  eva: 'code',
  export: 'export',
  deploy: 'deploy',
}

let lineCounter = 0
const line = (source: string, text: string, tone: OutputLine['tone'] = 'default', time?: string): OutputLine => ({
  id: `line-${++lineCounter}`,
  time: time ?? new Date().toISOString(),
  source,
  text,
  tone,
})

function describeRun(run: AgentRun): OutputLine {
  const tokens = run.inputTokens || run.outputTokens ? ` · ${run.inputTokens} in / ${run.outputTokens} out tokens` : ''
  const retries = run.retries ? ` · ${run.retries} ${run.retries === 1 ? 'retry' : 'retries'}` : ''
  const where = run.model ? ` (${run.provider}: ${run.model})` : ` (${run.provider})`
  if (run.status === 'failed') {
    return line(run.agent, `failed${where}: ${run.error ?? 'unknown error'}`, 'error', run.startedAt)
  }
  if (run.status === 'running') return line(run.agent, `running${where}`, 'default', run.startedAt)
  return line(run.agent, `succeeded in ${run.durationMs ?? 0} ms${where}${tokens}${retries}`, 'success', run.startedAt)
}

export function WorkspaceProvider({ project, children }: { project: ProjectDetail; children: ReactNode }) {
  const qc = useQueryClient()
  const id = project.id
  const reached = stageIndex(project.stage)
  const codeReached = reached >= stageIndex('code')

  const filesQuery = useFilesQuery(id)
  const messagesQuery = useMessagesQuery(id)
  const runsQuery = useRunsQuery(id)
  const checksQuery = useChecksQuery(id)
  const runStage = useRunStage(id)
  const saveMutation = useSaveFile(id)
  const sendMutation = useSendMessage(id)

  const files = useMemo(() => filesQuery.data ?? [], [filesQuery.data])
  const fileIndex = useMemo(() => new Map(files.map((f) => [f.path, f])), [files])
  const fileTree = useMemo(() => buildFileTree(files), [files])

  /* ---------------- Pipeline ---------------- */

  const [view, setView] = useState<StageId>(() => (codeReached ? 'code' : project.stage))
  const [runError, setRunError] = useState<string | null>(null)
  const [liveAgent, setLiveAgent] = useState<AgentId | null>(null)
  const [liveLines, setLiveLines] = useState<OutputLine[]>([])
  const [bottomTab, setBottomTab] = useState<BottomTab>('eva')

  const runningStage = project.runningStage
  const runningAgent = runningStage ? (liveAgent ?? uiAgent(runningStage)) : null
  const nextStage = reached < STAGES.length - 1 ? STAGES[reached + 1]!.id : null
  const canAdvance = nextStage !== null && project.specReady && runningStage === null

  const isReached = useCallback((stage: StageId) => stageIndex(stage) <= reached, [reached])
  const stageStatus = useCallback(
    (stage: StageId): StageStatus => {
      const i = stageIndex(stage)
      if (i < reached) return 'done'
      if (i === reached) return project.stage === 'deploy' && project.learning ? 'done' : 'active'
      return 'pending'
    },
    [reached, project.stage, project.learning],
  )

  const start = useCallback(
    (stage: RunnableStage) => {
      if (runningStage || runStage.isPending) return
      setRunError(null)
      setView(STAGE_TO_VIEW[stage])
      if (stage === 'eva') setBottomTab('eva')
      runStage.mutate(stage, { onError: (error) => setRunError(error.message) })
    },
    [runningStage, runStage],
  )

  const runNextStage = useCallback(() => {
    if (nextStage && canAdvance) start(nextStage)
  }, [nextStage, canAdvance, start])
  const generateSpec = useCallback(() => start('idea'), [start])
  const runEva = useCallback(() => start('eva'), [start])

  /* ---------------- Live progress ---------------- */

  const refreshAll = useCallback(() => {
    for (const key of [keys.project(id), keys.files(id), keys.messages(id), keys.runs(id), keys.checks(id)]) {
      void qc.invalidateQueries({ queryKey: key })
    }
    void qc.invalidateQueries({ queryKey: keys.projects })
  }, [qc, id])

  // When a stage finishes, reload everything. The WebSocket also triggers this, but when it cannot
  // connect (some hosts do not proxy WebSockets) polling notices the stage ending and this catches it.
  const previousRunning = useRef(runningStage)
  useEffect(() => {
    if (previousRunning.current && !runningStage) refreshAll()
    previousRunning.current = runningStage
  }, [runningStage, refreshAll])

  const addLine = useCallback((l: OutputLine) => setLiveLines((prev) => [...prev.slice(-200), l]), [])

  useProjectEvents(id, (event: ProgressEvent) => {
    switch (event.type) {
      case 'stage_started':
        qc.setQueryData<ProjectDetail>(keys.project(id), (p) => (p ? { ...p, runningStage: event.stage } : p))
        addLine(line('athena', `Stage "${event.stage}" started`, 'default', event.at))
        break
      case 'agent_started':
        setLiveAgent(uiAgent(event.agent))
        addLine(line(event.agent, 'working…', 'default', event.at))
        break
      case 'agent_succeeded':
        void qc.invalidateQueries({ queryKey: keys.runs(id) })
        break
      case 'checks_completed':
        void qc.invalidateQueries({ queryKey: keys.checks(id) })
        addLine(
          line(
            'checker',
            `${event.passed}/${event.total} consistency checks passed${event.failed.length ? `: failed ${event.failed.join(', ')}` : ''}`,
            event.failed.length ? 'error' : 'success',
            event.at,
          ),
        )
        break
      case 'index_updated':
        addLine(line('search', `Code search index updated (${event.chunks} chunks)`, 'default', event.at))
        break
      case 'stage_completed':
        setLiveAgent(null)
        addLine(line('athena', `Stage "${event.stage}" completed`, 'success', event.at))
        refreshAll()
        break
      case 'stage_failed':
        setLiveAgent(null)
        setRunError(event.error)
        addLine(line(event.agent ?? 'athena', `Stage "${event.stage}" failed: ${event.error}`, 'error', event.at))
        refreshAll()
        break
    }
  })

  /* ---------------- Files & editor ---------------- */

  const [openTabs, setOpenTabs] = useState<string[]>([])
  const [activeFile, setActiveFile] = useState<string | null>(null)
  const [edits, setEdits] = useState<Record<string, string>>({})
  // Mirror of `edits` that is updated synchronously, so a save right after a keystroke
  // (Ctrl+S while typing) always sends the latest text rather than the last rendered one.
  const editsRef = useRef<Record<string, string>>({})
  const savingRef = useRef<Set<string>>(new Set())
  const [saving, setSaving] = useState<ReadonlySet<string>>(new Set())
  const [saveError, setSaveError] = useState<string | null>(null)
  const [reveal, setReveal] = useState<WorkspaceContextValue['reveal']>(null)
  const [cursor, setCursor] = useState<CursorPosition>({ line: 1, column: 1 })

  // Open a sensible first file once code exists, and drop tabs for files that no longer exist.
  const autoOpened = useRef(false)
  useEffect(() => {
    if (!files.length) return
    setOpenTabs((tabs) => tabs.filter((t) => fileIndex.has(t)))
    setActiveFile((current) => (current && fileIndex.has(current) ? current : null))
    if (!autoOpened.current) {
      autoOpened.current = true
      const first = defaultFile(files)
      if (first) {
        setOpenTabs([first])
        setActiveFile(first)
      }
    }
  }, [files, fileIndex])

  const openFile = useCallback((path: string, lineNumber?: number) => {
    setOpenTabs((prev) => (prev.includes(path) ? prev : [...prev, path]))
    setActiveFile(path)
    setView('code')
    if (lineNumber) setReveal({ path, line: lineNumber, nonce: Date.now() })
  }, [])

  const closeFile = useCallback(
    (path: string) => {
      const index = openTabs.indexOf(path)
      const next = openTabs.filter((p) => p !== path)
      setOpenTabs(next)
      if (activeFile === path) setActiveFile(next[Math.max(0, index - 1)] ?? null)
    },
    [openTabs, activeFile],
  )

  const getContent = useCallback(
    (path: string) => edits[path] ?? fileIndex.get(path)?.content ?? '',
    [edits, fileIndex],
  )
  const updateContent = useCallback((path: string, value: string) => {
    editsRef.current = { ...editsRef.current, [path]: value }
    setEdits(editsRef.current)
  }, [])

  const dirty = useMemo(() => {
    const set = new Set<string>()
    for (const [path, value] of Object.entries(edits)) {
      if (value !== (fileIndex.get(path)?.content ?? '')) set.add(path)
    }
    return set
  }, [edits, fileIndex])

  const saveFile = useCallback(
    (path: string) => {
      const content = editsRef.current[path]
      if (content === undefined || savingRef.current.has(path)) return
      setSaveError(null)
      savingRef.current.add(path)
      setSaving(new Set(savingRef.current))
      saveMutation.mutate(
        { path, content },
        {
          onSuccess: () => {
            addLine(line('athena', `Saved ${path}`, 'success'))
            // Keep newer keystrokes typed while the save was in flight.
            if (editsRef.current[path] === content) {
              const { [path]: _saved, ...rest } = editsRef.current
              editsRef.current = rest
              setEdits(rest)
            }
          },
          onError: (error) => setSaveError(`Could not save ${path}: ${error.message}`),
          onSettled: () => {
            savingRef.current.delete(path)
            setSaving(new Set(savingRef.current))
          },
        },
      )
    },
    [saveMutation, addLine],
  )

  /* ---------------- Output ---------------- */

  const runs = useMemo(() => runsQuery.data ?? [], [runsQuery.data])
  const checks = useMemo(() => checksQuery.data ?? [], [checksQuery.data])
  const output = useMemo(() => {
    const history = [...runs].reverse().map(describeRun)
    return [...history, ...liveLines].sort((a, b) => a.time.localeCompare(b.time))
  }, [runs, liveLines])

  /* ---------------- Chat ---------------- */

  const sendMessage = useCallback(
    (content: string, agentId: AgentId) => {
      if (!content.trim() || sendMutation.isPending) return
      sendMutation.mutate({ content: content.trim(), agentId })
    },
    [sendMutation],
  )

  const value: WorkspaceContextValue = {
    project,
    view,
    setView,
    stageStatus,
    isReached,
    nextStage,
    canAdvance,
    runningStage,
    runningAgent,
    runNextStage,
    generateSpec,
    runError,
    dismissRunError: () => setRunError(null),
    files,
    filesLoading: filesQuery.isPending,
    fileTree,
    fileIndex,
    openTabs,
    activeFile,
    openFile,
    closeFile,
    getContent,
    updateContent,
    dirty,
    saving,
    saveFile,
    saveError,
    reveal,
    cursor,
    setCursor,
    messages: messagesQuery.data ?? [],
    typingAgent: sendMutation.isPending ? (sendMutation.variables?.agentId ?? null) : null,
    sendMessage,
    chatError: sendMutation.error?.message ?? null,
    evaRunning: runningStage === 'eva',
    runEva,
    runs,
    checks,
    output,
    bottomTab,
    setBottomTab,
  }

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used inside <WorkspaceProvider>')
  return ctx
}
