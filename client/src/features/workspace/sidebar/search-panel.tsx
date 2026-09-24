import { useQuery } from '@tanstack/react-query'
import { Loader2, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api/endpoints'
import { FileIcon } from '../file-icon'
import { useWorkspace } from '../workspace-context'
import { SidebarSection } from './sidebar-section'

/** Semantic code search over the project (pgvector on the server). */
export function SearchPanel({ onResultOpened }: { onResultOpened?: () => void }) {
  const { project, files, fileIndex, openFile } = useWorkspace()
  const [text, setText] = useState('')
  const [query, setQuery] = useState('')

  // Search as you type, after a short pause.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(text.trim()), 300)
    return () => clearTimeout(timer)
  }, [text])

  const results = useQuery({
    queryKey: ['project', project.id, 'search', query],
    queryFn: () => api.search(project.id, query),
    enabled: query.length >= 2,
    staleTime: 30_000,
  })

  return (
    <SidebarSection title="Search">
      <div className="px-3 pb-3">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-subtle" aria-hidden="true" />
          <Input
            type="search"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe what you are looking for"
            aria-label="Search the code by meaning"
            className="h-8 pl-8 text-xs"
            disabled={files.length === 0}
          />
        </div>
        <p className="mt-1.5 text-[11px] text-subtle">Finds code by meaning, e.g. "where users join a session".</p>
      </div>

      {files.length === 0 ? (
        <p className="px-3 text-xs text-subtle">Search becomes available once the project has code.</p>
      ) : results.isFetching ? (
        <p role="status" className="flex items-center gap-2 px-3 text-xs text-subtle">
          <Loader2 className="size-3 animate-spin" aria-hidden="true" /> Searching…
        </p>
      ) : results.isError ? (
        <p role="alert" className="px-3 text-xs text-red">{results.error.message}</p>
      ) : results.data && results.data.length === 0 ? (
        <p className="px-3 text-xs text-subtle">No matches.</p>
      ) : (
        <ul className="pb-2" aria-label="Search results">
          {results.data?.map((hit) => {
            const file = fileIndex.get(hit.filePath)
            return (
              <li key={`${hit.filePath}:${hit.startLine}`}>
                <button
                  type="button"
                  onClick={() => {
                    openFile(hit.filePath, hit.startLine)
                    onResultOpened?.()
                  }}
                  className="w-full cursor-pointer px-3 py-2 text-left transition-colors hover:bg-hover"
                >
                  <span className="flex items-center gap-1.5 text-xs">
                    <FileIcon node={{ type: 'file', name: hit.filePath, language: file?.language }} className="size-3.5" />
                    <span className="truncate text-text">{hit.filePath}</span>
                    <span className="ml-auto shrink-0 text-subtle">
                      {hit.startLine}-{hit.endLine}
                    </span>
                  </span>
                  <code className="mt-1 line-clamp-2 block font-mono text-[11px] whitespace-pre-wrap text-muted">
                    {hit.content.trim().split('\n').slice(0, 3).join('\n')}
                  </code>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </SidebarSection>
  )
}
