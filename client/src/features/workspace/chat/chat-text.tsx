import { Fragment, type ReactNode } from 'react'

/**
 * Renders the small Markdown subset agents use in chat: paragraphs, bullet and numbered lists,
 * fenced code blocks, `inline code` and **bold**. Built from React nodes, never raw HTML.
 */
export function ChatText({ text }: { text: string }) {
  return <div className="space-y-2">{blocks(text)}</div>
}

function blocks(text: string): ReactNode[] {
  const out: ReactNode[] = []
  const parts = text.split(/^```[^\n]*\n?/m)
  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      out.push(
        <pre key={`code-${i}`} className="overflow-x-auto rounded-md border border-border bg-base p-2.5 font-mono text-xs leading-relaxed">
          <code>{part.replace(/\n$/, '')}</code>
        </pre>,
      )
    } else {
      out.push(...proseBlocks(part, `p-${i}`))
    }
  })
  return out
}

function proseBlocks(text: string, keyPrefix: string): ReactNode[] {
  const out: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let paragraph: string[] = []

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(<p key={`${keyPrefix}-${out.length}`}>{inline(paragraph.join(' '))}</p>)
      paragraph = []
    }
  }
  const flushList = () => {
    if (list) {
      const Tag = list.ordered ? 'ol' : 'ul'
      out.push(
        <Tag key={`${keyPrefix}-${out.length}`} className={list.ordered ? 'list-decimal space-y-1 pl-5' : 'list-disc space-y-1 pl-5'}>
          {list.items.map((item, i) => (
            <li key={i}>{inline(item)}</li>
          ))}
        </Tag>,
      )
      list = null
    }
  }

  for (const raw of text.split('\n')) {
    const line = raw.trim()
    const bullet = /^[-*]\s+(.*)$/.exec(line)
    const numbered = /^\d+[.)]\s+(.*)$/.exec(line)
    if (bullet || numbered) {
      flushParagraph()
      const ordered = Boolean(numbered)
      if (list && list.ordered !== ordered) flushList()
      list ??= { ordered, items: [] }
      list.items.push((bullet ?? numbered)![1]!)
    } else if (!line) {
      flushParagraph()
      flushList()
    } else {
      flushList()
      paragraph.push(line.replace(/^#{1,6}\s+/, ''))
    }
  }
  flushParagraph()
  flushList()
  return out
}

function inline(text: string): ReactNode {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((piece, i) => {
    if (piece.startsWith('`') && piece.endsWith('`') && piece.length > 2) {
      return (
        <code key={i} className="rounded bg-base px-1 py-0.5 font-mono text-[0.85em]">
          {piece.slice(1, -1)}
        </code>
      )
    }
    if (piece.startsWith('**') && piece.endsWith('**') && piece.length > 4) {
      return <strong key={i}>{piece.slice(2, -2)}</strong>
    }
    return <Fragment key={i}>{piece}</Fragment>
  })
}
