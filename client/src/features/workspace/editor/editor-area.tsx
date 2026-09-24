import { AlertCircle, ChevronRight, Loader2, Save } from 'lucide-react'
import { LogoIcon } from '@/components/logo'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { useWorkspace } from '../workspace-context'
import { CodeEditor } from './code-editor'
import { EditorTabs } from './editor-tabs'

export function EditorArea() {
  const { activeFile, fileIndex, getContent, updateContent, saveFile, dirty, saving, saveError, reveal, setCursor } =
    useWorkspace()
  const node = activeFile ? fileIndex.get(activeFile) : undefined

  if (!node || !activeFile) return <EditorEmpty />

  return (
    <div className="flex h-full min-h-0 flex-col bg-panel">
      <EditorTabs />
      <div className="flex h-7 shrink-0 items-center gap-1 border-b border-border px-3 text-xs text-subtle">
        <span className="flex min-w-0 items-center gap-1 truncate" aria-label={`Path: ${activeFile}`}>
          {activeFile.split('/').map((part, i, parts) => (
            <span key={i} className="flex items-center gap-1">
              <span className={i === parts.length - 1 ? 'text-muted' : undefined}>{part}</span>
              {i < parts.length - 1 && <ChevronRight className="size-3" aria-hidden="true" />}
            </span>
          ))}
        </span>
        {saving.has(activeFile) ? (
          <span role="status" className="ml-auto flex items-center gap-1.5 text-subtle">
            <Loader2 className="size-3 animate-spin" aria-hidden="true" /> Saving…
          </span>
        ) : dirty.has(activeFile) ? (
          <Tip label="Save (Ctrl+S)">
            <Button variant="ghost" size="sm" className="ml-auto h-6 px-2 text-xs text-peach" onClick={() => saveFile(activeFile)}>
              <Save aria-hidden="true" /> Save
            </Button>
          </Tip>
        ) : (
          node.source === 'user' && <span className="ml-auto text-subtle">Edited by you</span>
        )}
      </div>
      {saveError && (
        <p role="alert" className="flex items-center gap-2 border-b border-red/30 bg-red/10 px-3 py-1.5 text-xs text-red">
          <AlertCircle className="size-3.5" aria-hidden="true" /> {saveError}
        </p>
      )}
      <div className="min-h-0 flex-1">
        <CodeEditor
          path={activeFile}
          language={node.language}
          value={getContent(activeFile)}
          onChange={(value) => updateContent(activeFile, value)}
          onSave={() => saveFile(activeFile)}
          onCursorChange={(line, column) => setCursor({ line, column })}
          reveal={reveal?.path === activeFile ? reveal : null}
        />
      </div>
    </div>
  )
}

function EditorEmpty() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-panel px-6 text-center">
      <LogoIcon size={64} className="text-raised" />
      <div>
        <p className="font-medium text-muted">No file open</p>
        <p className="mt-1 text-sm text-subtle">Pick a file from the explorer to start editing.</p>
      </div>
      <dl className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-xs text-subtle">
        <dt>Save file</dt>
        <dd>
          <kbd className="rounded border border-border bg-raised px-1.5 py-0.5 font-mono">Ctrl S</kbd>
        </dd>
        <dt>Find</dt>
        <dd>
          <kbd className="rounded border border-border bg-raised px-1.5 py-0.5 font-mono">Ctrl F</kbd>
        </dd>
      </dl>
    </div>
  )
}
