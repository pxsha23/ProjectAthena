import { ChevronRight, Download, Loader2, Upload, UsersRound } from 'lucide-react'
import { GithubIcon } from '@/components/icons'
import { Link } from 'react-router-dom'
import { LogoIcon } from '@/components/logo'
import { ProjectStatusBadge } from '@/components/project-status-badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Tip } from '@/components/ui/tooltip'
import { ThemeToggle } from '@/components/theme-toggle'
import { UserMenu } from '@/components/user-menu'
import { PipelineStepper } from './pipeline-stepper'
import { useWorkspace } from './workspace-context'

export function WorkspaceHeader() {
  const { project, isReached, evaRunning, runEva, setView } = useWorkspace()
  const hasCode = isReached('code')

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-border bg-panel px-2 sm:gap-3 sm:px-3">
      <Tip label="Back to projects" side="bottom">
        <Link to="/dashboard" aria-label="Back to projects" className="rounded-md p-1 hover:bg-raised">
          <LogoIcon size={24} />
        </Link>
      </Tip>

      <div className="flex min-w-0 items-center gap-1.5 text-sm">
        <Link to="/dashboard" className="hidden rounded-sm text-muted hover:text-text md:inline">
          Projects
        </Link>
        <ChevronRight className="hidden size-3.5 text-subtle md:block" aria-hidden="true" />
        <h1 className="truncate font-semibold">{project.name}</h1>
        <span className="hidden xl:inline-flex">
          <ProjectStatusBadge status={project.status} />
        </span>
      </div>

      <PipelineStepper className="mx-auto hidden lg:block" />

      <div className="ml-auto flex shrink-0 items-center gap-1.5 lg:ml-0">
        <Tip label={hasCode ? 'Run EVA virtual users' : 'EVA needs generated code first'} side="bottom">
          <span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void runEva()}
              disabled={!hasCode || evaRunning}
              className="text-peach"
            >
              {evaRunning ? <Loader2 className="animate-spin" aria-hidden="true" /> : <UsersRound aria-hidden="true" />}
              <span className="hidden sm:inline">{evaRunning ? 'Testing…' : 'Run EVA'}</span>
              <span className="sr-only sm:hidden">Run EVA</span>
            </Button>
          </span>
        </Tip>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" disabled={!hasCode} aria-label="Export project">
              <Upload aria-hidden="true" />
              <span className="hidden sm:inline">Export</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setView('export')}>
              <GithubIcon /> Push to GitHub
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => setView('export')}>
              <Download /> Download .zip
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <ThemeToggle className="hidden sm:inline-flex" />
        <UserMenu />
      </div>
    </header>
  )
}
