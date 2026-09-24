import { Files, Search, Workflow, type LucideIcon } from 'lucide-react'
import { Tip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { SidebarView } from './workspace-context'

const ITEMS: { id: SidebarView; label: string; icon: LucideIcon }[] = [
  { id: 'explorer', label: 'Explorer', icon: Files },
  { id: 'search', label: 'Search code', icon: Search },
  { id: 'pipeline', label: 'Pipeline & agents', icon: Workflow },
]

interface ActivityBarProps {
  active: SidebarView | null
  onSelect: (view: SidebarView) => void
}

/** Icon rail on the far left. Clicking the active item collapses the sidebar. */
export function ActivityBar({ active, onSelect }: ActivityBarProps) {
  return (
    <nav aria-label="Workspace views" className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-border bg-base py-2">
      {ITEMS.map(({ id, label, icon: Icon }) => {
        const selected = active === id
        return (
          <Tip key={id} label={label} side="right">
            <button
              type="button"
              onClick={() => onSelect(id)}
              aria-label={label}
              aria-pressed={selected}
              className={cn(
                'relative flex size-10 cursor-pointer items-center justify-center rounded-md transition-colors',
                selected ? 'text-text' : 'text-subtle hover:text-text',
              )}
            >
              {selected && <span aria-hidden="true" className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-lavender" />}
              <Icon className="size-5" aria-hidden="true" />
            </button>
          </Tip>
        )
      })}
    </nav>
  )
}
