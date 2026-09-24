import { Files, MessagesSquare, PanelBottom, SquareCode } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Group, Panel } from 'react-resizable-panels'
import { useMediaQuery } from '@/lib/use-media-query'
import { cn } from '@/lib/utils'
import { ActivityBar } from './activity-bar'
import { BottomPanel } from './bottom/bottom-panel'
import { AgentChat } from './chat/agent-chat'
import { PipelineStepper } from './pipeline-stepper'
import { ResizeHandle } from './resize-handle'
import { FileExplorer } from './sidebar/file-explorer'
import { RunErrorBanner } from './run-error-banner'
import { PipelineOverview } from './sidebar/pipeline-overview'
import { SearchPanel } from './sidebar/search-panel'
import { StageView } from './stages/stage-view'
import { StatusBar } from './status-bar'
import type { SidebarView } from './workspace-context'
import { WorkspaceHeader } from './workspace-header'

export function WorkspaceLayout() {
  const isDesktop = useMediaQuery('(min-width: 1024px)')
  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-base">
      <WorkspaceHeader />
      <RunErrorBanner />
      {isDesktop ? <DesktopBody /> : <MobileBody />}
      <StatusBar />
    </div>
  )
}

function SidebarContent({ view }: { view: SidebarView }) {
  if (view === 'explorer') return <FileExplorer />
  if (view === 'search') return <SearchPanel />
  return <PipelineOverview />
}

/* ------------------------------------------------------------------ */
/* Desktop: resizable panels                                          */
/* ------------------------------------------------------------------ */

function DesktopBody() {
  const [sidebar, setSidebar] = useState<SidebarView | null>('explorer')

  return (
    <div className="flex min-h-0 flex-1">
      <ActivityBar active={sidebar} onSelect={(v) => setSidebar((current) => (current === v ? null : v))} />
      <Group orientation="horizontal" className="min-w-0 flex-1">
        {sidebar && (
          <>
            <Panel id="sidebar" defaultSize="18" minSize={180} maxSize="35" className="bg-panel">
              <SidebarContent view={sidebar} />
            </Panel>
            <ResizeHandle direction="horizontal" />
          </>
        )}
        <Panel id="main" minSize="30">
          <Group orientation="vertical">
            <Panel id="stage" minSize="30">
              <StageView />
            </Panel>
            <ResizeHandle direction="vertical" />
            <Panel id="bottom" defaultSize="28" minSize={90} collapsible collapsedSize={0}>
              <BottomPanel />
            </Panel>
          </Group>
        </Panel>
        <ResizeHandle direction="horizontal" />
        <Panel id="chat" defaultSize="24" minSize={280} maxSize="40">
          <AgentChat />
        </Panel>
      </Group>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Mobile / tablet: one pane at a time with a bottom tab bar           */
/* ------------------------------------------------------------------ */

type MobilePane = 'files' | 'main' | 'chat' | 'panel'

const MOBILE_TABS: { id: MobilePane; label: string; icon: typeof Files }[] = [
  { id: 'files', label: 'Files', icon: Files },
  { id: 'main', label: 'Stage', icon: SquareCode },
  { id: 'chat', label: 'Agents', icon: MessagesSquare },
  { id: 'panel', label: 'EVA', icon: PanelBottom },
]

function MobileBody() {
  const [pane, setPane] = useState<MobilePane>('main')

  let content: ReactNode
  switch (pane) {
    case 'files':
      content = (
        <div className="grid h-full min-h-0 grid-rows-[auto_1fr] bg-panel">
          <div className="max-h-[45%] overflow-y-auto border-b border-border">
            <PipelineOverview />
          </div>
          <div className="min-h-0">
            <FileExplorer onFileOpened={() => setPane('main')} />
          </div>
        </div>
      )
      break
    case 'chat':
      content = <AgentChat />
      break
    case 'panel':
      content = <BottomPanel />
      break
    default:
      content = <StageView />
  }

  return (
    <>
      <div className="shrink-0 border-b border-border bg-panel px-2 py-1.5">
        <PipelineStepper />
      </div>
      <div className="min-h-0 flex-1">{content}</div>
      <nav aria-label="Workspace panes" className="grid shrink-0 grid-cols-4 border-t border-border bg-panel">
        {MOBILE_TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setPane(id)}
            aria-pressed={pane === id}
            className={cn(
              'flex cursor-pointer flex-col items-center gap-0.5 py-2 text-[11px] transition-colors',
              pane === id ? 'text-lavender' : 'text-subtle hover:text-text',
            )}
          >
            <Icon className="size-5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </nav>
    </>
  )
}
