import { EditorArea } from '../editor/editor-area'
import { useWorkspace } from '../workspace-context'
import { DeployView } from './deploy-view'
import { ExportView } from './export-view'
import { IdeaView } from './idea-view'
import { StackView } from './stack-view'
import { StageLocked } from './stage-locked'

/** The main centre area: the editor for "code", a document view for every other stage. */
export function StageView() {
  const { view, isReached } = useWorkspace()

  // Export has no agent: it opens as soon as there is code, and exporting marks it reached.
  const open = isReached(view) || (view === 'export' && isReached('code'))
  if (!open) return <StageLocked stage={view} />

  switch (view) {
    case 'idea':
      return <IdeaView />
    case 'stack':
      return <StackView />
    case 'code':
      return <EditorArea />
    case 'export':
      return <ExportView />
    case 'deploy':
      return <DeployView />
  }
}
