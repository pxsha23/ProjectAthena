import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { BottomTab } from '../workspace-context'
import { useWorkspace } from '../workspace-context'
import { ChecksPanel, latestChecks } from './checks-panel'
import { EvaReport } from './eva-report'
import { OutputLog } from './output-log'

export function BottomPanel() {
  const { bottomTab, setBottomTab, project, checks } = useWorkspace()
  const evaIssues = project.eva?.findings.filter((f) => f.severity !== 'pass').length ?? 0
  const failedChecks = latestChecks(checks).filter((c) => !c.passed).length

  return (
    <Tabs
      value={bottomTab}
      onValueChange={(v) => setBottomTab(v as BottomTab)}
      className="flex h-full min-h-0 flex-col border-t border-border bg-panel"
    >
      <TabsList className="h-9 shrink-0 rounded-none border-0 border-b border-border bg-transparent px-2">
        <TabsTrigger value="eva" className="h-7 text-xs">
          EVA report
          {evaIssues > 0 && <span className="rounded-full bg-peach/15 px-1.5 text-[10px] text-peach">{evaIssues}</span>}
        </TabsTrigger>
        <TabsTrigger value="checks" className="h-7 text-xs">
          Checks
          {failedChecks > 0 && <span className="rounded-full bg-red/15 px-1.5 text-[10px] text-red">{failedChecks}</span>}
        </TabsTrigger>
        <TabsTrigger value="output" className="h-7 text-xs">
          Output
        </TabsTrigger>
      </TabsList>
      <TabsContent value="eva" className="min-h-0 flex-1">
        <EvaReport />
      </TabsContent>
      <TabsContent value="checks" className="min-h-0 flex-1">
        <ChecksPanel />
      </TabsContent>
      <TabsContent value="output" className="min-h-0 flex-1">
        <OutputLog />
      </TabsContent>
    </Tabs>
  )
}
