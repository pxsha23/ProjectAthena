import type { Project } from '@/lib/types'

export type ProjectFilter = 'all' | 'starred' | 'active' | 'deployed'
export type ProjectSort = 'updated' | 'created' | 'name'

export const FILTERS: { id: ProjectFilter; label: string }[] = [
  { id: 'all', label: 'All projects' },
  { id: 'starred', label: 'Starred' },
  { id: 'active', label: 'In progress' },
  { id: 'deployed', label: 'Deployed' },
]

export const SORTS: { id: ProjectSort; label: string }[] = [
  { id: 'updated', label: 'Last updated' },
  { id: 'created', label: 'Newest' },
  { id: 'name', label: 'Name' },
]

export function matchesFilter(project: Project, filter: ProjectFilter): boolean {
  switch (filter) {
    case 'starred':
      return project.starred
    case 'active':
      return project.status === 'draft' || project.status === 'in-progress'
    case 'deployed':
      return project.status === 'deployed' || project.status === 'ready'
    default:
      return true
  }
}

export function sortProjects(projects: Project[], sort: ProjectSort): Project[] {
  const copy = [...projects]
  switch (sort) {
    case 'name':
      return copy.sort((a, b) => a.name.localeCompare(b.name))
    case 'created':
      return copy.sort((a, b) => b.createdAt.localeCompare(a.createdAt))
    default:
      return copy.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
  }
}

export function searchProjects(projects: Project[], query: string): Project[] {
  const q = query.trim().toLowerCase()
  if (!q) return projects
  return projects.filter(
    (p) =>
      p.name.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q) ||
      p.stack.some((tech) => tech.toLowerCase().includes(q)),
  )
}
