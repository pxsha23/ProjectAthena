/** Session state from the API. The session lives in httpOnly cookies set by the server. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/client'
import { api } from '@/lib/api/endpoints'
import { keys } from '@/lib/api/queries'
import type { User } from '@/lib/types'

async function fetchMe(): Promise<User | null> {
  try {
    return await api.auth.me()
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}

export function useAuth() {
  const qc = useQueryClient()
  const me = useQuery({ queryKey: keys.me, queryFn: fetchMe, staleTime: 5 * 60_000 })

  const signedIn = (user: User) => {
    qc.setQueryData(keys.me, user)
    void qc.invalidateQueries({ queryKey: keys.projects })
  }

  const login = useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) => api.auth.login(email, password),
    onSuccess: signedIn,
  })
  const signup = useMutation({
    mutationFn: ({ name, email, password }: { name: string; email: string; password: string }) =>
      api.auth.register(name, email, password),
    onSuccess: signedIn,
  })
  const logout = useMutation({
    mutationFn: api.auth.logout,
    onSettled: () => {
      qc.clear()
      qc.setQueryData(keys.me, null)
    },
  })

  return {
    user: me.data ?? null,
    /** True until we know whether there is a session. */
    isLoading: me.isPending,
    error: me.error,
    login,
    signup,
    logout,
    loginWithGithub: () => window.location.assign(api.auth.githubLoginUrl),
  }
}

export function useAuthProviders() {
  return useQuery({ queryKey: keys.providers, queryFn: api.auth.providers, staleTime: Infinity })
}
