import { Loader2, Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { AgentChip } from '@/components/agent-badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { FormError } from '@/features/auth/form-error'
import { IDEA_SUGGESTIONS } from '@/lib/landing-content'

interface NewProjectDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  initialIdea?: string
  onCreate: (input: { name: string; idea: string }) => void
  pending?: boolean
  error?: string | null
}

const MIN_IDEA_LENGTH = 15

const ARTICLES = new Set(['a', 'an', 'the', 'my', 'our'])
const CONNECTORS = new Set(['that', 'which', 'where', 'who', 'for', 'to', 'with', 'and', 'from', 'so', 'in', 'on', 'of', 'between'])
const GENERIC = new Set(['app', 'application', 'platform', 'website', 'site', 'tool', 'web'])

const titleCase = (words: string[]) => words.map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')

/**
 * Guess a short project name from the idea.
 * "A recipe app that suggests meals…" → "Recipe App"
 * "An app where university students…" → "University Students App"
 */
function suggestName(idea: string): string {
  const words = idea.toLowerCase().match(/[a-z0-9]+/g) ?? []
  let start = 0
  while (start < words.length && ARTICLES.has(words[start]!)) start++

  const lead: string[] = []
  for (const word of words.slice(start)) {
    if (CONNECTORS.has(word) || lead.length === 3) break
    lead.push(word)
  }
  if (lead.some((w) => !GENERIC.has(w))) return titleCase(lead)

  const content = words.filter((w) => !ARTICLES.has(w) && !CONNECTORS.has(w) && !GENERIC.has(w)).slice(0, 2)
  return content.length ? titleCase([...content, 'app']) : ''
}

export function NewProjectDialog({
  open,
  onOpenChange,
  initialIdea = '',
  onCreate,
  pending = false,
  error = null,
}: NewProjectDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        {/* Keyed by the idea so the form resets each time the dialog opens with a new one. */}
        {open && (
          <NewProjectForm
            key={initialIdea}
            initialIdea={initialIdea}
            onCreate={onCreate}
            onCancel={() => onOpenChange(false)}
            pending={pending}
            error={error}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

interface NewProjectFormProps {
  initialIdea: string
  onCreate: NewProjectDialogProps['onCreate']
  onCancel: () => void
  pending: boolean
  error: string | null
}

function NewProjectForm({ initialIdea, onCreate, onCancel, pending, error }: NewProjectFormProps) {
  const [idea, setIdea] = useState(initialIdea)
  const [name, setName] = useState(initialIdea ? suggestName(initialIdea) : '')
  const [nameTouched, setNameTouched] = useState(false)

  const ideaTooShort = idea.trim().length < MIN_IDEA_LENGTH
  const canSubmit = !ideaTooShort && name.trim().length > 0

  function updateIdea(value: string) {
    setIdea(value)
    if (!nameTouched) setName(suggestName(value))
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (canSubmit && !pending) onCreate({ name: name.trim(), idea: idea.trim() })
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-5">
      <DialogHeader>
        <DialogTitle>New project</DialogTitle>
        <DialogDescription>
          Describe your idea in plain words. The <AgentChip agentId="idea" className="mx-0.5 align-middle" /> will
          turn it into a spec.
        </DialogDescription>
      </DialogHeader>

      <div className="grid gap-1.5">
        <Label htmlFor="project-idea">What do you want to build?</Label>
        <Textarea
          id="project-idea"
          autoFocus
          rows={4}
          value={idea}
          onChange={(e) => updateIdea(e.target.value)}
          placeholder="An app where…"
          aria-describedby="project-idea-hint"
        />
        <p id="project-idea-hint" className="text-xs text-subtle">
          A sentence or two is enough. Mention who it is for and the main thing it should do.
        </p>
      </div>

      <div className="grid gap-2">
        <p className="text-xs text-subtle">Need inspiration?</p>
        <div className="flex flex-wrap gap-2">
          {IDEA_SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => updateIdea(suggestion)}
              className="cursor-pointer rounded-full border border-border px-2.5 py-1 text-left text-xs text-muted transition-colors hover:border-pink/40 hover:text-pink"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="project-name">Project name</Label>
        <Input
          id="project-name"
          value={name}
          onChange={(e) => {
            setNameTouched(true)
            setName(e.target.value)
          }}
          placeholder="My new app"
          maxLength={60}
        />
      </div>

      <FormError message={error} />

      <DialogFooter>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" variant="ai" disabled={!canSubmit || pending}>
          {pending ? <Loader2 className="animate-spin" aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
          Create & start agents
        </Button>
      </DialogFooter>
    </form>
  )
}
