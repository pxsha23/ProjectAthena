import { motion } from 'framer-motion'
import { Clock, Ellipsis, Star, Trash2, FolderOpen } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { AgentChip } from '@/components/agent-badge'
import { ProjectStatusBadge } from '@/components/project-status-badge'
import { StageProgress } from '@/components/stage-progress'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tip } from '@/components/ui/tooltip'
import { getStage } from '@/lib/agents'
import type { Project } from '@/lib/types'
import { cn, formatRelative } from '@/lib/utils'

interface ProjectListItemProps {
  project: Project
  onToggleStar: (id: string) => void
  onDelete: (project: Project) => void
}

export function ProjectListItem({ project, onToggleStar, onDelete }: ProjectListItemProps) {
  const navigate = useNavigate()
  const stage = getStage(project.stage)

  return (
    <motion.li
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex flex-col gap-3 border-b border-border px-4 py-5 last:border-b-0 sm:flex-row sm:items-start sm:gap-6"
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/project/${project.id}`}
            className="truncate rounded-sm text-base font-semibold text-lavender hover:underline"
          >
            {project.name}
          </Link>
          <ProjectStatusBadge status={project.status} />
        </div>
        <p className="mt-1 line-clamp-2 text-sm text-muted">{project.description}</p>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-subtle">
          <AgentChip agentId={stage.agentId} short />
          <span>
            Stage: <span className="text-muted">{stage.label}</span>
          </span>
          {project.stack.length > 0 && <span className="font-mono">{project.stack.join(' · ')}</span>}
          <span className="inline-flex items-center gap-1">
            <Clock className="size-3" aria-hidden="true" />
            Updated {formatRelative(project.updatedAt)}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 sm:flex-col sm:items-end">
        <div className="flex items-center gap-1">
          <Tip label={project.starred ? 'Unstar' : 'Star'}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onToggleStar(project.id)}
              aria-pressed={project.starred}
              aria-label={project.starred ? `Unstar ${project.name}` : `Star ${project.name}`}
            >
              <Star className={cn(project.starred && 'fill-yellow text-yellow')} aria-hidden="true" />
              <span className="hidden sm:inline">{project.starred ? 'Starred' : 'Star'}</span>
            </Button>
          </Tip>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label={`More actions for ${project.name}`}>
                <Ellipsis aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => navigate(`/project/${project.id}`)}>
                <FolderOpen /> Open workspace
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={() => onDelete(project)}>
                <Trash2 /> Delete project
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <StageProgress stage={project.stage} className="ml-auto sm:ml-0" />
      </div>
    </motion.li>
  )
}
