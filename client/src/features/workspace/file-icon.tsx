import { Braces, FileCode, FileText, FileType, Folder, FolderOpen, Settings2, Container } from 'lucide-react'
import type { FileNode } from '@/lib/types'
import { cn } from '@/lib/utils'

interface FileIconProps {
  node: Pick<FileNode, 'type' | 'language' | 'name'>
  open?: boolean
  className?: string
}

/** Small language-coloured icon for the explorer and editor tabs. */
export function FileIcon({ node, open, className }: FileIconProps) {
  const base = cn('size-4 shrink-0', className)
  if (node.type === 'folder') {
    const Icon = open ? FolderOpen : Folder
    return <Icon className={cn(base, 'text-lavender')} aria-hidden="true" />
  }
  switch (node.language) {
    case 'typescript':
    case 'javascript':
      return <FileCode className={cn(base, 'text-sky')} aria-hidden="true" />
    case 'python':
      return <FileCode className={cn(base, 'text-yellow')} aria-hidden="true" />
    case 'json':
      return <Braces className={cn(base, 'text-peach')} aria-hidden="true" />
    case 'yaml':
      return <Settings2 className={cn(base, 'text-pink')} aria-hidden="true" />
    case 'dockerfile':
      return <Container className={cn(base, 'text-sky')} aria-hidden="true" />
    case 'markdown':
      return <FileText className={cn(base, 'text-lavender')} aria-hidden="true" />
    case 'css':
    case 'html':
      return <FileType className={cn(base, 'text-mauve')} aria-hidden="true" />
    default:
      return <FileText className={cn(base, 'text-subtle')} aria-hidden="true" />
  }
}
