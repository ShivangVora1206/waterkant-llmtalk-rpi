import { useEffect, useRef, useState } from 'react'
import { wsClient } from '../api/ws'
import type { PipelineState, SystemHealth, WSEvent } from '../api/types'

export interface WSState {
  state: PipelineState
  connected: boolean
  lastTranscript: string
  lastResponse: string
  audioLevel: number
  health: SystemHealth | null
  lastError: string | null
  events: WSEvent[]
  conversationVersion: number
}

const MAX_EVENTS = 100

export function useWebSocketState(): WSState {
  const [connected, setConnected] = useState(wsClient.connected)
  const [pipelineState, setPipelineState] = useState<PipelineState>('IDLE')
  const [lastTranscript, setLastTranscript] = useState('')
  const [lastResponse, setLastResponse] = useState('')
  const [audioLevel, setAudioLevel] = useState(-60)
  const [health, setHealth] = useState<SystemHealth | null>(null)
  const [lastError, setLastError] = useState<string | null>(null)
  const [events, setEvents] = useState<WSEvent[]>([])
  const [conversationVersion, setConversationVersion] = useState(0)
  const responseBuffer = useRef('')

  useEffect(() => {
    const handler = (evt: WSEvent) => {
      setEvents(prev => [...prev.slice(-MAX_EVENTS + 1), evt])

      switch (evt.type) {
        case 'ws.connected':
          setConnected(true)
          break
        case 'ws.disconnected':
          setConnected(false)
          break
        case 'state.snapshot':
        case 'state.changed': {
          const d = evt.data as { to?: string; state?: string }
          const s = (d.to ?? d.state ?? 'IDLE') as PipelineState
          setPipelineState(s)
          if (s === 'LISTENING') {
            responseBuffer.current = ''
            setLastResponse('')
          }
          break
        }
        case 'stt.final': {
          const d = evt.data as { text: string }
          setLastTranscript(d.text ?? '')
          break
        }
        case 'llm.token': {
          const d = evt.data as { token: string }
          responseBuffer.current += d.token ?? ''
          setLastResponse(responseBuffer.current)
          break
        }
        case 'audio.level': {
          const d = evt.data as { dbfs: number }
          setAudioLevel(d.dbfs ?? -60)
          break
        }
        case 'system.health':
          setHealth(evt.data as SystemHealth)
          break
        case 'conversation.updated':
          setConversationVersion(v => v + 1)
          break
        case 'error': {
          const d = evt.data as { message: string }
          setLastError(d.message ?? 'Unknown error')
          break
        }
      }
    }

    wsClient.on(handler)
    return () => wsClient.off(handler)
  }, [])

  return {
    state: pipelineState,
    connected,
    lastTranscript,
    lastResponse,
    audioLevel,
    health,
    lastError,
    events,
    conversationVersion,
  }
}
