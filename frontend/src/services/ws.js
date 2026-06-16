import { getToken } from './auth'

export function connectQuizSocket(code, channel, onMessage, onOpen) {
  const base = (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace('http', 'ws')
  const token = getToken()
  const qs = token ? `?token=${encodeURIComponent(token)}` : ''
  const ws = new WebSocket(`${base}/ws/quiz/${code}/${channel}${qs}`)

  ws.onopen = () => onOpen?.(ws)
  ws.onmessage = (event) => {
    try {
      onMessage?.(JSON.parse(event.data), ws)
    } catch {
      // ignore malformed payloads
    }
  }

  return ws
}
