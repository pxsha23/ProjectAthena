import { STAGES, agentClasses, getStage, stageIndex } from '@/lib/agents'
import type { StageId } from '@/lib/types'
import { cn } from '@/lib/utils'

interface StageProgressProps {
  stage: StageId
  className?: string
}

/** Six small segments, one per pipeline stage, coloured by the owning agent once reached. */
export function StageProgress({ stage, className }: StageProgressProps) {
  const current = stageIndex(stage)
  return (
    <div
      className={cn('flex items-center gap-1', className)}
      role="img"
      aria-label={`Stage ${current + 1} of ${STAGES.length}: ${getStage(stage).label}`}
    >
      {STAGES.map((s, index) => (
        <span
          key={s.id}
          className={cn('h-1.5 w-5 rounded-full', index <= current ? agentClasses(s.agentId).bg : 'bg-raised')}
        />
      ))}
    </div>
  )
}
