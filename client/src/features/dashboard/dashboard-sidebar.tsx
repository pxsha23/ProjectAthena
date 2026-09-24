import { Avatar } from '@/components/ui/avatar'
import type { Project, User } from '@/lib/types'
import { cn } from '@/lib/utils'
import { FILTERS, matchesFilter, type ProjectFilter } from './project-filters'

interface DashboardSidebarProps {
  user: User
  projects: Project[]
  filter: ProjectFilter
  onFilterChange: (filter: ProjectFilter) => void
}

export function DashboardSidebar({ user, projects, filter, onFilterChange }: DashboardSidebarProps) {
  return (
    <aside className="flex min-w-0 flex-col gap-6">
      <div className="hidden items-center gap-3 lg:flex">
        <Avatar name={user.name} className="size-12 text-base" />
        <div className="min-w-0">
          <p className="truncate font-semibold">{user.name}</p>
          <p className="truncate text-sm text-subtle">{user.githubUsername ?? user.email}</p>
        </div>
      </div>

      <nav aria-label="Project filters">
        <ul className="flex gap-1 overflow-x-auto lg:flex-col">
          {FILTERS.map((f) => {
            const count = projects.filter((p) => matchesFilter(p, f.id)).length
            const active = filter === f.id
            return (
              <li key={f.id} className="shrink-0">
                <button
                  type="button"
                  onClick={() => onFilterChange(f.id)}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'flex w-full cursor-pointer items-center justify-between gap-3 rounded-md px-3 py-1.5 text-sm transition-colors',
                    active ? 'bg-raised font-medium text-text' : 'text-muted hover:bg-raised/60 hover:text-text',
                  )}
                >
                  <span className="flex items-center gap-2">
                    {active && <span className="hidden h-4 w-0.5 rounded-full bg-lavender lg:block" aria-hidden="true" />}
                    {f.label}
                  </span>
                  <span className="rounded-full bg-base px-1.5 text-xs text-subtle">{count}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </nav>
    </aside>
  )
}
