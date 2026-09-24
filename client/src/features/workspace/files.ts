import type { FileNode, ProjectFile } from '@/lib/types'

/** Builds the explorer tree (folders first, then files, alphabetically) from the flat file list. */
export function buildFileTree(files: ProjectFile[]): FileNode[] {
  const root: FileNode[] = []
  const folders = new Map<string, FileNode>()

  const childrenOf = (folderPath: string): FileNode[] => {
    if (!folderPath) return root
    let folder = folders.get(folderPath)
    if (!folder) {
      const parent = folderPath.includes('/') ? folderPath.slice(0, folderPath.lastIndexOf('/')) : ''
      folder = { id: folderPath, name: folderPath.split('/').pop()!, path: folderPath, type: 'folder', children: [] }
      folders.set(folderPath, folder)
      childrenOf(parent).push(folder)
    }
    return folder.children!
  }

  for (const file of files) {
    const dir = file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/')) : ''
    childrenOf(dir).push({
      id: file.path,
      name: file.path.split('/').pop()!,
      path: file.path,
      type: 'file',
      language: file.language,
    })
  }

  const sort = (nodes: FileNode[]) => {
    nodes.sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === 'folder' ? -1 : 1))
    nodes.forEach((n) => n.children && sort(n.children))
  }
  sort(root)
  return root
}

/** All ancestor folder paths of a file, e.g. a/b/c.ts -> [a, a/b]. */
export function parentPaths(path: string): string[] {
  const parts = path.split('/')
  return parts.slice(0, -1).map((_, i) => parts.slice(0, i + 1).join('/'))
}

/** Picks the file to open first after code is generated. */
export function defaultFile(files: ProjectFile[]): string | null {
  const preferred = ['backend/main.py', 'main.py', 'src/App.tsx', 'frontend/src/App.tsx', 'app.py', 'server.js']
  return preferred.find((p) => files.some((f) => f.path === p)) ?? files.find((f) => !f.path.endsWith('.md'))?.path ?? files[0]?.path ?? null
}
