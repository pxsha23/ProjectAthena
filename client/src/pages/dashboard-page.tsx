import { AnimatePresence } from 'framer-motion'
import { AlertCircle, ArrowDownUp, Check, Plus, RotateCw, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { SiteFooter } from '@/components/site-footer'
import { SiteHeader } from '@/components/site-header'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Spotlight } from '@/components/spotlight'
import { Skeleton } from '@/components/ui/skeleton'
import { Input } from '@/components/ui/input'
import { DashboardSidebar } from '@/features/dashboard/dashboard-sidebar'
import { DeleteProjectDialog } from '@/features/dashboard/delete-project-dialog'
import { EmptyProjects } from '@/features/dashboard/empty-projects'
import { NewProjectDialog } from '@/features/dashboard/new-project-dialog'
import {
  FILTERS,
  SORTS,
  matchesFilter,
  searchProjects,
  sortProjects,
  type ProjectFilter,
  type ProjectSort,
} from '@/features/dashboard/project-filters'
import { ProjectListItem } from '@/features/dashboard/project-list-item'
import { useCreateProject, useDeleteProject, useProjectsQuery, useUpdateProject } from '@/lib/api/queries'
import { useAuth } from '@/lib/auth'
import type { Project } from '@/lib/types'

export default function DashboardPage() {
  const { user } = useAuth()
  const projectsQuery = useProjectsQuery()
  const createProject = useCreateProject()
  const updateProject = useUpdateProject()
  const deleteProject = useDeleteProject()
  const projects = useMemo(() => projectsQuery.data ?? [], [projectsQuery.data])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // An idea typed on the landing page arrives as ?idea=… and opens the dialog.
  const ideaParam = searchParams.get('idea') ?? ''
  const [dialogOpen, setDialogOpen] = useState(ideaParam !== '')
  const [filter, setFilter] = useState<ProjectFilter>('all')
  const [sort, setSort] = useState<ProjectSort>('updated')
  const [query, setQuery] = useState('')
  const [pendingDelete, setPendingDelete] = useState<Project | null>(null)

  const visible = useMemo(
    () => sortProjects(searchProjects(projects.filter((p) => matchesFilter(p, filter)), query), sort),
    [projects, filter, query, sort],
  )

  if (!user) return null

  function handleDialogChange(open: boolean) {
    setDialogOpen(open)
    if (!open) {
      createProject.reset()
      if (ideaParam) setSearchParams({}, { replace: true })
    }
  }

  function handleCreate(input: { name: string; idea: string }) {
    createProject.mutate(input, { onSuccess: (project) => navigate(`/project/${project.id}`) })
  }

  const toggleStar = (id: string) => {
    const project = projects.find((p) => p.id === id)
    if (project) updateProject.mutate({ id, patch: { starred: !project.starred } })
  }

  const filterLabel = FILTERS.find((f) => f.id === filter)?.label ?? 'Projects'
  const sortLabel = SORTS.find((s) => s.id === sort)?.label

  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader variant="app" />

      <main className="mx-auto grid w-full max-w-6xl flex-1 grid-cols-[minmax(0,1fr)] content-start gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-10">
        <DashboardSidebar user={user} projects={projects} filter={filter} onFilterChange={setFilter} />

        <section aria-labelledby="projects-heading" className="min-w-0">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <h1 id="projects-heading" className="text-xl font-semibold">
              {filterLabel}
            </h1>
            <div className="flex flex-1 items-center gap-2 sm:justify-end">
              <div className="relative flex-1 sm:max-w-xs">
                <Search
                  className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
                  aria-hidden="true"
                />
                <Input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Find a project…"
                  aria-label="Search projects"
                  className="pl-9"
                />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="secondary" aria-label={`Sort by: ${sortLabel}`}>
                    <ArrowDownUp aria-hidden="true" />
                    <span className="hidden md:inline">{sortLabel}</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Sort by</DropdownMenuLabel>
                  {SORTS.map((s) => (
                    <DropdownMenuItem key={s.id} onSelect={() => setSort(s.id)}>
                      <Check className={sort === s.id ? 'opacity-100' : 'opacity-0'} aria-hidden="true" />
                      {s.label}
                      {sort === s.id && <span className="sr-only">(selected)</span>}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button onClick={() => setDialogOpen(true)}>
                <Plus aria-hidden="true" />
                <span className="hidden sm:inline">New project</span>
                <span className="sr-only sm:hidden">New project</span>
              </Button>
            </div>
          </div>

          <Spotlight size={520} className="mt-5 rounded-lg border border-border bg-panel">
            {projectsQuery.isPending ? (
              <ProjectListSkeleton />
            ) : projectsQuery.isError ? (
              <div role="alert" className="flex flex-col items-center gap-3 px-4 py-14 text-center">
                <AlertCircle className="size-8 text-red" aria-hidden="true" />
                <p className="font-medium">Could not load your projects</p>
                <p className="max-w-sm text-sm text-muted">{projectsQuery.error.message}</p>
                <Button variant="secondary" onClick={() => void projectsQuery.refetch()}>
                  <RotateCw aria-hidden="true" /> Try again
                </Button>
              </div>
            ) : visible.length === 0 ? (
              <EmptyProjects
                hasQuery={query !== '' || filter !== 'all'}
                onCreate={() => setDialogOpen(true)}
                onClear={() => {
                  setQuery('')
                  setFilter('all')
                }}
              />
            ) : (
              <ul aria-label="Projects">
                <AnimatePresence initial={false}>
                  {visible.map((project) => (
                    <ProjectListItem
                      key={project.id}
                      project={project}
                      onToggleStar={toggleStar}
                      onDelete={setPendingDelete}
                    />
                  ))}
                </AnimatePresence>
              </ul>
            )}
          </Spotlight>
        </section>
      </main>

      <SiteFooter />

      <NewProjectDialog
        open={dialogOpen}
        onOpenChange={handleDialogChange}
        initialIdea={ideaParam}
        onCreate={handleCreate}
        pending={createProject.isPending}
        error={createProject.error?.message ?? null}
      />
      <DeleteProjectDialog
        project={pendingDelete}
        pending={deleteProject.isPending}
        error={deleteProject.error?.message ?? null}
        onCancel={() => {
          deleteProject.reset()
          setPendingDelete(null)
        }}
        onConfirm={(project) => deleteProject.mutate(project.id, { onSuccess: () => setPendingDelete(null) })}
      />
    </div>
  )
}

function ProjectListSkeleton() {
  return (
    <ul aria-label="Loading projects" aria-busy="true">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex flex-col gap-3 border-b border-border px-4 py-5 last:border-b-0">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </li>
      ))}
    </ul>
  )
}
