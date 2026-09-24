import Editor, { type OnMount } from '@monaco-editor/react'
import { useEffect, useMemo, useRef } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { useTheme } from '@/lib/theme'
import { useMediaQuery } from '@/lib/use-media-query'
import type { FileLanguage } from '@/lib/types'
import { defineAthenaTheme, monaco } from './monaco-setup'

interface CodeEditorProps {
  path: string
  language: FileLanguage | undefined
  value: string
  onChange: (value: string) => void
  onSave: () => void
  onCursorChange: (line: number, column: number) => void
  /** Scroll to and select this line; a new nonce repeats the jump. */
  reveal?: { line: number; nonce: number } | null
}

export function CodeEditor({ path, language, value, onChange, onSave, onCursorChange, reveal }: CodeEditorProps) {
  const compact = !useMediaQuery('(min-width: 768px)')
  const { theme } = useTheme()
  // ThemeProvider applies data-theme before re-rendering, so the CSS variables are already current here.
  const monacoTheme = useMemo(() => defineAthenaTheme(theme), [theme])
  // Keep the latest callbacks in refs so the Monaco command registered on mount never goes stale.
  const onSaveRef = useRef(onSave)
  const onCursorRef = useRef(onCursorChange)
  useEffect(() => {
    onSaveRef.current = onSave
    onCursorRef.current = onCursorChange
  })

  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)
  useEffect(() => {
    const editor = editorRef.current
    if (!editor || !reveal) return
    editor.revealLineInCenter(reveal.line)
    editor.setPosition({ lineNumber: reveal.line, column: 1 })
    editor.focus()
  }, [reveal, path])

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor
    if (reveal) {
      editor.revealLineInCenter(reveal.line)
      editor.setPosition({ lineNumber: reveal.line, column: 1 })
    }
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => onSaveRef.current())
    editor.onDidChangeCursorPosition((e) => onCursorRef.current(e.position.lineNumber, e.position.column))
    editor.focus()
  }

  return (
    <Editor
      // `path` gives each file its own model, so undo history and scroll position survive tab switches.
      path={path}
      language={language ?? 'plaintext'}
      value={value}
      theme={monacoTheme}
      onChange={(next) => onChange(next ?? '')}
      onMount={handleMount}
      loading={<EditorSkeleton />}
      options={{
        fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
        fontSize: 13,
        lineHeight: 20,
        fontLigatures: true,
        minimap: { enabled: !compact, scale: 1, renderCharacters: false },
        lineNumbersMinChars: compact ? 3 : 5,
        folding: !compact,
        scrollBeyondLastLine: false,
        smoothScrolling: true,
        cursorSmoothCaretAnimation: 'on',
        cursorBlinking: 'smooth',
        renderLineHighlight: 'all',
        bracketPairColorization: { enabled: true },
        guides: { bracketPairs: 'active', indentation: true },
        padding: { top: 12, bottom: 12 },
        tabSize: 2,
        automaticLayout: true,
        ariaLabel: `Code editor: ${path}`,
      }}
    />
  )
}

function EditorSkeleton() {
  return (
    <div className="flex h-full w-full flex-col gap-2 bg-panel p-4" aria-hidden="true">
      {[70, 45, 60, 30, 80, 50, 40].map((w, i) => (
        <Skeleton key={i} className="h-3.5" style={{ width: `${w}%` }} />
      ))}
    </div>
  )
}
