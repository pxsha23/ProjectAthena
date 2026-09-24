import { ChevronRight, FileCode } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AgentChip } from '@/components/agent-badge'
import type { FileNode } from '@/lib/types'
import { cn } from '@/lib/utils'
import { FileIcon } from '../file-icon'
import { parentPaths } from '../files'
import { useWorkspace } from '../workspace-context'
import { SidebarSection } from './sidebar-section'

interface FileExplorerProps {
  /** Called after a file is opened, e.g. so the mobile layout can switch to the editor. */
  onFileOpened?: () => void
}

export function FileExplorer({ onFileOpened }: FileExplorerProps) {
  const { files, fileTree, filesLoading, activeFile } = useWorkspace()
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(['backend', 'frontend', 'frontend/src']))

  // Reveal the active file (e.g. opened from search or a learning-summary link).
  useEffect(() => {
    if (!activeFile) return
    setExpanded((prev) => {
      const missing = parentPaths(activeFile).filter((p) => !prev.has(p))
      return missing.length ? new Set([...prev, ...missing]) : prev
    })
  }, [activeFile])

  function toggle(path: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  if (filesLoading) {
    return (
      <SidebarSection title="Explorer">
        <p role="status" className="px-3 py-4 text-sm text-subtle">
          Loading files…
        </p>
      </SidebarSection>
    )
  }

  if (files.length === 0) {
    return (
      <SidebarSection title="Explorer">
        <div className="flex flex-col items-center gap-3 px-4 py-10 text-center text-sm text-muted">
          <FileCode className="size-8 text-subtle" aria-hidden="true" />
          <p>
            No files yet. They appear once the <AgentChip agentId="code" className="align-middle" /> has run.
          </p>
        </div>
      </SidebarSection>
    )
  }

  return (
    <SidebarSection title="Explorer" meta={`${files.length} files`}>
      <ul role="tree" aria-label="Project files" className="py-1 text-sm">
        {fileTree.map((node) => (
          <TreeNode key={node.id} node={node} depth={0} expanded={expanded} onToggle={toggle} onFileOpened={onFileOpened} />
        ))}
      </ul>
    </SidebarSection>
  )
}

interface TreeNodeProps {
  node: FileNode
  depth: number
  expanded: Set<string>
  onToggle: (path: string) => void
  onFileOpened?: () => void
}

function TreeNode({ node, depth, expanded, onToggle, onFileOpened }: TreeNodeProps) {
  const { activeFile, openFile, dirty } = useWorkspace()
  const isFolder = node.type === 'folder'
  const isOpen = expanded.has(node.path)
  const isActive = activeFile === node.path

  return (
    <li role="treeitem" aria-expanded={isFolder ? isOpen : undefined} aria-selected={isActive}>
      <button
        type="button"
        onClick={() => {
          if (isFolder) return onToggle(node.path)
          openFile(node.path)
          onFileOpened?.()
        }}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        className={cn(
          'flex w-full cursor-pointer items-center gap-1.5 py-1 pr-2 text-left transition-colors',
          isActive ? 'bg-lavender/10 text-text' : 'text-muted hover:bg-raised/60 hover:text-text',
        )}
      >
        <ChevronRight
          aria-hidden="true"
          className={cn('size-3.5 shrink-0 text-subtle transition-transform', isOpen && 'rotate-90', !isFolder && 'invisible')}
        />
        <FileIcon node={node} open={isOpen} />
        <span className="truncate">{node.name}</span>
        {dirty.has(node.path) && (
          <span className="ml-auto size-2 shrink-0 rounded-full bg-peach" aria-label="Unsaved changes" />
        )}
      </button>
      {isFolder && isOpen && node.children && (
        <ul role="group">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              expanded={expanded}
              onToggle={onToggle}
              onFileOpened={onFileOpened}
            />
          ))}
        </ul>
      )}
    </li>
  )
}
