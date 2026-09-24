import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FormError } from '@/features/auth/form-error'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { Project } from '@/lib/types'

interface DeleteProjectDialogProps {
  project: Project | null
  onCancel: () => void
  onConfirm: (project: Project) => void
  pending?: boolean
  error?: string | null
}

export function DeleteProjectDialog({ project, onCancel, onConfirm, pending, error }: DeleteProjectDialogProps) {
  return (
    <Dialog open={project !== null} onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete project?</DialogTitle>
          <DialogDescription>
            <span className="font-medium text-text">{project?.name}</span> and all its generated files will be
            permanently deleted. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <FormError message={error ?? null} />
        <DialogFooter>
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="destructive" disabled={pending} onClick={() => project && onConfirm(project)}>
            {pending && <Loader2 className="animate-spin" aria-hidden="true" />}
            Delete project
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
