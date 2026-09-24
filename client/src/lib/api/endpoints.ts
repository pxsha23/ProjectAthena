/** Typed functions for every Athena API endpoint. */
import type {
  AgentId,
  AgentRun,
  ChatMessage,
  ConsistencyCheck,
  GithubExportResult,
  Project,
  ProjectDetail,
  ProjectFile,
  RunnableStage,
  SearchHit,
  User,
} from '@/lib/types'
import { request } from './client'

const enc = encodeURIComponent
/** Encodes each path segment but keeps the slashes: "backend/main.py". */
const filePath = (path: string) => path.split('/').map(enc).join('/')

export const api = {
  auth: {
    me: () => request<User>('/auth/me'),
    providers: () => request<{ github: boolean }>('/auth/providers', { noRefresh: true }),
    login: (email: string, password: string) =>
      request<User>('/auth/login', { method: 'POST', json: { email, password }, noRefresh: true }),
    register: (name: string, email: string, password: string) =>
      request<User>('/auth/register', { method: 'POST', json: { name, email, password }, noRefresh: true }),
    logout: () => request<void>('/auth/logout', { method: 'POST', noRefresh: true }),
    /** Full-page navigation: GitHub redirects back to /dashboard. */
    githubLoginUrl: '/api/auth/github/login',
  },

  projects: {
    list: () => request<Project[]>('/projects'),
    get: (id: string) => request<ProjectDetail>(`/projects/${enc(id)}`),
    create: (name: string, idea: string) => request<ProjectDetail>('/projects', { method: 'POST', json: { name, idea } }),
    update: (id: string, patch: { name?: string; starred?: boolean }) =>
      request<ProjectDetail>(`/projects/${enc(id)}`, { method: 'PATCH', json: patch }),
    remove: (id: string) => request<void>(`/projects/${enc(id)}`, { method: 'DELETE' }),
  },

  files: {
    list: (projectId: string) => request<ProjectFile[]>(`/projects/${enc(projectId)}/files`),
    save: (projectId: string, path: string, content: string) =>
      request<ProjectFile>(`/projects/${enc(projectId)}/files/${filePath(path)}`, { method: 'PUT', json: { content } }),
    remove: (projectId: string, path: string) =>
      request<void>(`/projects/${enc(projectId)}/files/${filePath(path)}`, { method: 'DELETE' }),
  },

  chat: {
    list: (projectId: string) => request<ChatMessage[]>(`/projects/${enc(projectId)}/messages`),
    send: (projectId: string, content: string, agentId: AgentId) =>
      request<[ChatMessage, ChatMessage]>(`/projects/${enc(projectId)}/messages`, {
        method: 'POST',
        json: { content, agentId },
      }),
  },

  pipeline: {
    run: (projectId: string, stage: RunnableStage) =>
      request<{ projectId: string; stage: RunnableStage; status: 'started' }>(
        `/projects/${enc(projectId)}/stages/${stage}/run`,
        { method: 'POST' },
      ),
    runs: (projectId: string) => request<AgentRun[]>(`/projects/${enc(projectId)}/runs`),
    checks: (projectId: string) => request<ConsistencyCheck[]>(`/projects/${enc(projectId)}/checks`),
  },

  exports: {
    /** Plain link: the browser downloads the zip with the session cookie. */
    zipUrl: (projectId: string) => `/api/projects/${enc(projectId)}/export/zip`,
    github: (projectId: string, repoName: string, isPrivate: boolean) =>
      request<GithubExportResult>(`/projects/${enc(projectId)}/export/github`, {
        method: 'POST',
        json: { repoName, private: isPrivate },
      }),
  },

  search: (projectId: string, q: string) =>
    request<SearchHit[]>(`/projects/${enc(projectId)}/search?q=${enc(q)}&limit=12`),

  /** WebSocket URL for live progress. Goes through the Vite proxy in development. */
  eventsUrl: (projectId: string) =>
    `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws/projects/${enc(projectId)}`,
}
