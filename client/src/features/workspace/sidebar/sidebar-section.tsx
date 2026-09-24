import type { ReactNode } from 'react'

interface SidebarSectionProps {
  title: string
  meta?: string
  children: ReactNode
}

export function SidebarSection({ title, meta, children }: SidebarSectionProps) {
  return (
    <section aria-label={title} className="flex h-full min-h-0 flex-col">
      <div className="flex h-9 shrink-0 items-center justify-between px-3">
        <h2 className="text-[11px] font-semibold tracking-wider text-subtle uppercase">{title}</h2>
        {meta && <span className="text-[11px] text-subtle">{meta}</span>}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </section>
  )
}
