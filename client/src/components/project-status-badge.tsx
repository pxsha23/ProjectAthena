import { Badge, type BadgeProps } from '@/components/ui/badge'
import type { ProjectStatus } from '@/lib/types'

const STATUS: Record<ProjectStatus, { label: string; tone: NonNullable<BadgeProps['tone']> }> = {
  draft: { label: 'Draft', tone: 'neutral' },
  'in-progress': { label: 'In progress', tone: 'yellow' },
  ready: { label: 'Ready to deploy', tone: 'sky' },
  deployed: { label: 'Deployed', tone: 'green' },
}

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  const { label, tone } = STATUS[status]
  return <Badge tone={tone}>{label}</Badge>
}
