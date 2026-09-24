import { Card } from '@/components/ui/card'
import { useWorkspace } from '../workspace-context'
import { StageShell } from './stage-shell'

export function StackView() {
  const { project } = useWorkspace()
  const choices = project.stackPlan?.choices ?? []
  return (
    <StageShell stage="stack">
      <ul className="grid gap-3">
        {choices.map((choice) => (
          <li key={`${choice.layer}-${choice.name}`}>
            <Card spotlight="var(--color-sky)" className="grid gap-3 p-5 sm:grid-cols-[120px_1fr]">
              <p className="text-xs font-semibold tracking-wide text-sky uppercase">{choice.layer}</p>
              <div>
                <h3 className="font-semibold">{choice.name}</h3>
                <p className="mt-1 text-sm text-muted">{choice.reason}</p>
                {choice.alternatives.length > 0 && (
                <p className="mt-3 text-xs text-subtle">
                  Alternatives:{' '}
                  {choice.alternatives.map((alt, i) => (
                    <span key={alt}>
                      <span className="font-mono text-muted">{alt}</span>
                      {i < choice.alternatives.length - 1 && ', '}
                    </span>
                  ))}
                </p>
                )}
              </div>
            </Card>
          </li>
        ))}
      </ul>
    </StageShell>
  )
}
