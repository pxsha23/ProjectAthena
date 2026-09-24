/**
 * Minimal fetch wrapper for the Athena API.
 * - Requests go to /api on the same origin (Vite proxies them to FastAPI in development),
 *   so the httpOnly auth cookies are sent automatically.
 * - A 401 triggers one silent refresh of the session, then the request is retried.
 */

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  json?: unknown
  /** Skip the refresh-and-retry step (used by the auth endpoints themselves). */
  noRefresh?: boolean
}

type FastApiDetail = string | { msg: string; loc?: (string | number)[] }[] | undefined

function describe(detail: FastApiDetail, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    // Pydantic validation errors: "email: value is not a valid email address"
    return detail
      .map((d) => {
        const field = d.loc?.filter((part) => part !== 'body').join('.')
        return field ? `${field}: ${d.msg}` : d.msg
      })
      .join('; ')
  }
  if (status >= 500) return 'The server had a problem. Please try again.'
  return `Request failed (${status})`
}

let refreshing: Promise<boolean> | null = null

/** Refreshes the session once; concurrent 401s share the same refresh call. */
function refreshSession(): Promise<boolean> {
  refreshing ??= fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin' })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, noRefresh, headers, ...init } = options
  const send = () =>
    fetch(`/api${path}`, {
      credentials: 'same-origin',
      ...init,
      headers: { Accept: 'application/json', ...(json !== undefined && { 'Content-Type': 'application/json' }), ...headers },
      body: json !== undefined ? JSON.stringify(json) : undefined,
    })

  let response: Response
  try {
    response = await send()
    if (response.status === 401 && !noRefresh && (await refreshSession())) {
      response = await send()
    }
  } catch {
    throw new ApiError(0, 'Cannot reach the Athena server. Is it running on port 8000?')
  }

  if (response.status === 204) return undefined as T
  const body = await response.json().catch(() => undefined)
  if (!response.ok) {
    throw new ApiError(response.status, describe(body?.detail, response.status))
  }
  return body as T
}
