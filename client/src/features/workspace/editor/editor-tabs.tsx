import { X } from 'lucide-react'
import { type KeyboardEvent } from 'react'
import { cn } from '@/lib/utils'
import { FileIcon } from '../file-icon'
import { useWorkspace } from '../workspace-context'

export function EditorTabs() {
  const { openTabs, activeFile, openFile, closeFile, fileIndex, dirty } = useWorkspace()

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    const index = activeFile ? openTabs.indexOf(activeFile) : -1
    const delta = event.key === 'ArrowRight' ? 1 : -1
    const next = openTabs[(index + delta + openTabs.length) % openTabs.length]
    if (next) {
      openFile(next)
      document.getElementById(`tab-${next}`)?.focus()
    }
  }

  return (
    <div
      role="tablist"
      aria-label="Open files"
      onKeyDown={handleKeyDown}
      className="flex h-9 shrink-0 items-stretch overflow-x-auto border-b border-border bg-base"
    >
      {openTabs.map((path) => {
        const file = fileIndex.get(path)
        if (!file) return null
        const node = { type: 'file' as const, name: path.split('/').pop()!, language: file.language }
        const active = path === activeFile
        const isDirty = dirty.has(path)
        return (
          <div
            key={path}
            className={cn(
              'group relative flex shrink-0 items-center border-r border-border text-sm',
              active ? 'bg-panel text-text' : 'text-subtle hover:bg-panel/60 hover:text-muted',
            )}
            onAuxClick={(e) => e.button === 1 && closeFile(path)}
          >
            {active && <span aria-hidden="true" className="absolute inset-x-0 top-0 h-0.5 bg-lavender" />}
            <button
              id={`tab-${path}`}
              type="button"
              role="tab"
              aria-selected={active}
              tabIndex={active ? 0 : -1}
              title={path}
              onClick={() => openFile(path)}
              className="flex h-full cursor-pointer items-center gap-2 pr-1 pl-3"
            >
              <FileIcon node={node} />
              {node.name}
            </button>
            <button
              type="button"
              onClick={() => closeFile(path)}
              aria-label={`Close ${node.name}${isDirty ? ' (unsaved changes)' : ''}`}
              className="group/close mr-1.5 flex size-5 cursor-pointer items-center justify-center rounded-sm hover:bg-raised"
            >
              {isDirty ? (
                <>
                  <span className="size-2 rounded-full bg-peach group-hover/close:hidden" aria-hidden="true" />
                  <X className="hidden size-3.5 group-hover/close:block" aria-hidden="true" />
                </>
              ) : (
                <X className={cn('size-3.5', !active && 'opacity-0 group-hover:opacity-100 focus-visible:opacity-100')} aria-hidden="true" />
              )}
            </button>
          </div>
        )
      })}
    </div>
  )
}
