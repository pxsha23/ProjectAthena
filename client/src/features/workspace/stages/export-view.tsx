import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Download, ExternalLink, Globe, Loader2, Lock } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { GithubIcon } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { FormError } from '@/features/auth/form-error'
import { api } from '@/lib/api/endpoints'
import { keys } from '@/lib/api/queries'
import { useAuth, useAuthProviders } from '@/lib/auth'
import { cn, slugify } from '@/lib/utils'
import { useWorkspace } from '../workspace-context'
import { StageShell } from './stage-shell'

type Visibility = 'private' | 'public'

export function ExportView() {
  return (
    <StageShell stage="export">
      <div className="grid gap-4">
        <GithubExportCard />
        <ZipExportCard />
      </div>
    </StageShell>
  )
}

function GithubExportCard() {
  const { project } = useWorkspace()
  const { user, loginWithGithub } = useAuth()
  const providers = useAuthProviders()
  const qc = useQueryClient()
  const [repo, setRepo] = useState(() => slugify(project.name))
  const [visibility, setVisibility] = useState<Visibility>('private')

  const push = useMutation({
    mutationFn: () => api.exports.github(project.id, repo, visibility === 'private'),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: keys.project(project.id) })
      void qc.invalidateQueries({ queryKey: keys.projects })
    },
  })

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (repo) push.mutate()
  }

  let body: ReactNode
  if (push.isSuccess) {
    body = (
      <div role="status" className="flex flex-wrap items-center gap-3 rounded-md border border-green/30 bg-green/10 p-4 text-sm text-green">
        <Check className="size-4" aria-hidden="true" />
        <span className="flex-1">
          Pushed to <span className="font-mono">{push.data.fullName}</span>
        </span>
        <Button variant="secondary" size="sm" asChild>
          <a href={push.data.repoUrl} target="_blank" rel="noreferrer">
            <ExternalLink aria-hidden="true" /> Open on GitHub
          </a>
        </Button>
      </div>
    )
  } else if (!user?.hasGithubToken) {
    body = providers.data?.github ? (
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-sm text-muted">Connect your GitHub account so Athena can create the repository for you.</p>
        <Button variant="secondary" onClick={loginWithGithub}>
          <GithubIcon aria-hidden="true" /> Connect GitHub
        </Button>
      </div>
    ) : (
      <p className="text-sm text-muted">GitHub is not set up on this Athena server yet. Download the zip instead.</p>
    )
  } else {
    body = (
      <form onSubmit={handleSubmit} className="grid gap-4">
        <div className="grid gap-1.5">
          <Label htmlFor="repo-name">Repository name</Label>
          <div className="flex items-center rounded-md border border-border bg-raised focus-within:border-lavender focus-within:ring-2 focus-within:ring-lavender/30">
            <span className="truncate pl-3 font-mono text-sm text-subtle">{user.githubUsername}/</span>
            <Input
              id="repo-name"
              value={repo}
              onChange={(e) => setRepo(e.target.value.toLowerCase().replace(/[^a-z0-9._-]+/g, '-'))}
              required
              maxLength={100}
              className="border-0 bg-transparent pl-0.5 font-mono focus-visible:ring-0"
            />
          </div>
        </div>

        <fieldset className="grid gap-2">
          <legend className="mb-1.5 text-sm font-medium">Visibility</legend>
          <div className="grid gap-2 sm:grid-cols-2">
            <VisibilityOption value="private" current={visibility} onChange={setVisibility}
              icon={<Lock className="size-4" aria-hidden="true" />} label="Private" hint="Only you can see it" />
            <VisibilityOption value="public" current={visibility} onChange={setVisibility}
              icon={<Globe className="size-4" aria-hidden="true" />} label="Public" hint="Great for your portfolio" />
          </div>
        </fieldset>

        <FormError message={push.error?.message ?? null} />
        <Button type="submit" className="justify-self-start" disabled={!repo || push.isPending}>
          {push.isPending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <GithubIcon aria-hidden="true" />}
          {push.isPending ? 'Pushing…' : 'Create repository'}
        </Button>
      </form>
    )
  }

  return (
    <Card spotlight>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GithubIcon className="size-5" aria-hidden="true" /> Push to GitHub
        </CardTitle>
        <CardDescription>Create a new repository with all project files in one commit.</CardDescription>
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  )
}

interface VisibilityOptionProps {
  value: Visibility
  current: Visibility
  onChange: (value: Visibility) => void
  icon: ReactNode
  label: string
  hint: string
}

function VisibilityOption({ value, current, onChange, icon, label, hint }: VisibilityOptionProps) {
  const checked = value === current
  return (
    <label
      className={cn(
        'flex cursor-pointer items-start gap-3 rounded-md border p-3 transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-lavender',
        checked ? 'border-lavender/50 bg-lavender/10' : 'border-border hover:border-border-strong',
      )}
    >
      <input type="radio" name="visibility" value={value} checked={checked} onChange={() => onChange(value)} className="sr-only" />
      <span className={checked ? 'text-lavender' : 'text-subtle'}>{icon}</span>
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-subtle">{hint}</span>
      </span>
    </label>
  )
}

function ZipExportCard() {
  const { project, files, dirty } = useWorkspace()
  const qc = useQueryClient()
  const [started, setStarted] = useState(false)
  const filename = `${slugify(project.name) || 'project'}.zip`

  return (
    <Card spotlight>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="size-5" aria-hidden="true" /> Download as .zip
        </CardTitle>
        <CardDescription>
          All {files.length} saved files in a single archive.
          {dirty.size > 0 && ` ${dirty.size} unsaved ${dirty.size === 1 ? 'edit is' : 'edits are'} not included: save first.`}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap items-center gap-3">
        <Button variant="secondary" asChild>
          <a
            href={api.exports.zipUrl(project.id)}
            download={filename}
            onClick={() => {
              setStarted(true)
              // The download marks the project as exported on the server.
              setTimeout(() => void qc.invalidateQueries({ queryKey: keys.project(project.id) }), 1500)
            }}
          >
            <Download aria-hidden="true" /> Download {filename}
          </a>
        </Button>
        {started && (
          <span role="status" className="inline-flex items-center gap-1.5 text-sm text-green">
            <Check className="size-4" aria-hidden="true" /> Download started
          </span>
        )}
      </CardContent>
    </Card>
  )
}
