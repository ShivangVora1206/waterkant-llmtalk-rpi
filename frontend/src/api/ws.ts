import type { WSEvent } from './types'

export type WSHandler = (event: WSEvent) => void

export class WSClient {
  private ws: WebSocket | null = null
  private handlers: WSHandler[] = []
  private reconnectDelay = 1000
  private maxDelay = 30000
  private _connected = false
  private stopped = false

  get connected() { return this._connected }

  connect(url: string) {
    if (this.stopped) return
    try {
      this.ws = new WebSocket(url)
    } catch {
      this._scheduleReconnect(url)
      return
    }

    this.ws.onopen = () => {
      this._connected = true
      this.reconnectDelay = 1000
      this._emit({ type: 'ws.connected', data: {} })
    }

    this.ws.onmessage = (e) => {
      try {
        const evt: WSEvent = JSON.parse(e.data)
        this._emit(evt)
      } catch { /* ignore malformed */ }
    }

    this.ws.onclose = () => {
      this._connected = false
      this._emit({ type: 'ws.disconnected', data: {} })
      this._scheduleReconnect(url)
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  private _scheduleReconnect(url: string) {
    if (this.stopped) return
    setTimeout(() => this.connect(url), this.reconnectDelay)
    this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxDelay)
  }

  private _emit(evt: WSEvent) {
    for (const h of this.handlers) {
      try { h(evt) } catch { /* ignore */ }
    }
  }

  on(handler: WSHandler) { this.handlers.push(handler) }
  off(handler: WSHandler) { this.handlers = this.handlers.filter(h => h !== handler) }

  disconnect() {
    this.stopped = true
    this.ws?.close()
  }
}

const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/state`
export const wsClient = new WSClient()
wsClient.connect(WS_URL)
