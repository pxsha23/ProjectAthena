import { Radar, Rocket } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { FileIcon } from '../file-icon'
import { useWorkspace } from '../workspace-context'
import { LearningSummary } from './learning-summary'
import { StageShell } from './stage-shell'

export function DeployView() {
  const { project, fileIndex, openFile } = useWorkspace()
  const deployment = project.deployment

  return (
    <StageShell stage="deploy">
      <section aria-labelledby="deploy-files-heading">
        <h3 id="deploy-files-heading" className="flex items-center gap-2 text-sm font-semibold text-subtle uppercase">
          <Rocket className="size-4" aria-hidden="true" /> Deployment files
        </h3>
        <ul className="mt-3 grid gap-3 sm:grid-cols-3">
          {(deployment?.targets ?? []).map((target) => (
            <li key={target.id}>
              <Card spotlight="var(--color-green)" className="h-full">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base text-green">{target.name}</CardTitle>
                  <CardDescription>{target.description}</CardDescription>
                </CardHeader>
                <CardContent className="flex flex-wrap gap-1.5">
                  {target.files.map((path) => {
                    const node = fileIndex.get(path)
                    return (
                      <button
                        key={path}
                        type="button"
                        onClick={() => openFile(path)}
                        disabled={!node}
                        className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-raised px-2 py-1 font-mono text-xs text-muted transition-colors hover:border-subtle hover:text-text disabled:cursor-default"
                        aria-label={`Open ${path} in the editor`}
                      >
                        {node && <FileIcon node={{ type: 'file', name: path, language: node.language }} className="size-3.5" />}
                        {path.split('/').pop()}
                      </button>
                    )
                  })}
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      {deployment && deployment.detection.evidence.length > 0 && (
        <details className="group mt-6 rounded-lg border border-border bg-panel p-4 text-sm">
          <summary className="flex cursor-pointer list-none items-center gap-2 font-medium text-muted hover:text-text">
            <Radar className="size-4 text-green" aria-hidden="true" /> How your stack was detected
          </summary>
          <ul className="mt-3 space-y-1.5 pl-6 font-mono text-xs text-muted">
            {deployment.detection.evidence.map((item) => (
              <li key={item} className="list-disc">
                {item}
              </li>
            ))}
          </ul>
        </details>
      )}

      {project.learning ? (
        <LearningSummary />
      ) : (
        <p className="mt-12 rounded-lg border border-border bg-panel p-5 text-sm text-muted">
          The learning summary is not ready yet. It is written after the deployment files, in the same stage.
        </p>
      )}
    </StageShell>
  )
}
