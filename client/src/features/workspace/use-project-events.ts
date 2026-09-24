import { useEffect, useRef } from 'react'
import { api } from '@/lib/api/endpoints'
import type { ProgressEvent } from '@/lib/types'

/**
 * Subscribes to a project's live progress events over WebSocket.
 * Reconnects with backoff if the connection drops (e.g. the server restarts).
 */
export function useProjectEvents(projectId: string, onEvent: (event: ProgressEvent) => void): void {
  const handler = useRef(onEvent)
  useEffect(() => {
    handler.current = onEvent
  })

  useEffect(() => {
    let socket: WebSocket | null = null
    let retry: ReturnType<typeof setTimeout> | undefined
    let attempt = 0
    let closed = false

    const connect = () => {
      socket = new WebSocket(api.eventsUrl(projectId))
      socket.onopen = () => {
        attempt = 0
      }
      socket.onmessage = (message) => {
        try {
          handler.current(JSON.parse(message.data) as ProgressEvent)
        } catch {
          /* ignore malformed events */
        }
      }
      socket.onclose = (event) => {
        // 1008 = the server rejected us (signed out or not our project): do not retry.
        if (closed || event.code === 1008) return
        attempt += 1
        retry = setTimeout(connect, Math.min(10_000, 500 * 2 ** attempt))
      }
    }

    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      socket?.close()
    }
  }, [projectId])
}
