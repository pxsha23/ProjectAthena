/** TanStack Query keys and hooks for server state. */
import { QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AgentId, ChatMessage, Project, ProjectDetail, ProjectFile, RunnableStage } from '@/lib/types'
import { ApiError } from './client'
import { api } from './endpoints'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      // Do not hammer the server on auth or not-found errors.
      retry: (failures, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failures < 2,
      refetchOnWindowFocus: false,
    },
  },
})

export const keys = {
  me: ['me'] as const,
  providers: ['auth-providers'] as const,
  projects: ['projects'] as const,
  project: (id: string) => ['project', id] as const,
  files: (id: string) => ['project', id, 'files'] as const,
  messages: (id: string) => ['project', id, 'messages'] as const,
  runs: (id: string) => ['project', id, 'runs'] as const,
  checks: (id: string) => ['project', id, 'checks'] as const,
}

/* ---------------- projects ---------------- */

export function useProjectsQuery() {
  return useQuery({ queryKey: keys.projects, queryFn: api.projects.list })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ name, idea }: { name: string; idea: string }) => api.projects.create(name, idea),
    onSuccess: (project) => {
      qc.setQueryData(keys.project(project.id), project)
      void qc.invalidateQueries({ queryKey: keys.projects })
    },
  })
}

export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: { name?: string; starred?: boolean } }) =>
      api.projects.update(id, patch),
    // Optimistic star toggle so the dashboard feels instant.
    onMutate: async ({ id, patch }) => {
      await qc.cancelQueries({ queryKey: keys.projects })
      const previous = qc.getQueryData<Project[]>(keys.projects)
      qc.setQueryData<Project[]>(keys.projects, (list) => list?.map((p) => (p.id === id ? { ...p, ...patch } : p)))
      return { previous }
    },
    onError: (_error, _vars, context) => qc.setQueryData(keys.projects, context?.previous),
    onSettled: (project) => {
      void qc.invalidateQueries({ queryKey: keys.projects })
      if (project) qc.setQueryData(keys.project(project.id), project)
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.projects.remove(id),
    onSuccess: (_data, id) => {
      qc.setQueryData<Project[]>(keys.projects, (list) => list?.filter((p) => p.id !== id))
      qc.removeQueries({ queryKey: keys.project(id) })
    },
  })
}

/* ---------------- workspace ---------------- */

/** Project detail. Polls while an agent is running, as a fallback if the WebSocket drops. */
export function useProjectQuery(id: string) {
  return useQuery({
    queryKey: keys.project(id),
    queryFn: () => api.projects.get(id),
    refetchInterval: (query) => ((query.state.data as ProjectDetail | undefined)?.runningStage ? 3000 : false),
  })
}

export function useFilesQuery(id: string, enabled = true) {
  return useQuery({ queryKey: keys.files(id), queryFn: () => api.files.list(id), enabled })
}

export function useMessagesQuery(id: string) {
  return useQuery({ queryKey: keys.messages(id), queryFn: () => api.chat.list(id) })
}

export function useRunsQuery(id: string) {
  return useQuery({ queryKey: keys.runs(id), queryFn: () => api.pipeline.runs(id) })
}

export function useChecksQuery(id: string) {
  return useQuery({ queryKey: keys.checks(id), queryFn: () => api.pipeline.checks(id) })
}

export function useRunStage(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (stage: RunnableStage) => api.pipeline.run(projectId, stage),
    onSuccess: (_data, stage) => {
      qc.setQueryData<ProjectDetail>(keys.project(projectId), (p) => (p ? { ...p, runningStage: stage } : p))
    },
  })
}

export function useSaveFile(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ path, content }: { path: string; content: string }) => api.files.save(projectId, path, content),
    onSuccess: (saved) => {
      qc.setQueryData<ProjectFile[]>(keys.files(projectId), (files) => {
        if (!files) return [saved]
        const exists = files.some((f) => f.path === saved.path)
        return exists ? files.map((f) => (f.path === saved.path ? saved : f)) : [...files, saved]
      })
    },
  })
}

export function useSendMessage(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ content, agentId }: { content: string; agentId: AgentId }) =>
      api.chat.send(projectId, content, agentId),
    // Show the user's message immediately while the agent thinks.
    onMutate: async ({ content }) => {
      await qc.cancelQueries({ queryKey: keys.messages(projectId) })
      const previous = qc.getQueryData<ChatMessage[]>(keys.messages(projectId))
      const pending: ChatMessage = {
        id: `pending-${Date.now()}`,
        role: 'user',
        agentId: null,
        content,
        createdAt: new Date().toISOString(),
      }
      qc.setQueryData<ChatMessage[]>(keys.messages(projectId), (list) => [...(list ?? []), pending])
      return { previous }
    },
    onError: (_error, _vars, context) => qc.setQueryData(keys.messages(projectId), context?.previous),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: keys.messages(projectId) })
      void qc.invalidateQueries({ queryKey: keys.runs(projectId) })
    },
  })
}
