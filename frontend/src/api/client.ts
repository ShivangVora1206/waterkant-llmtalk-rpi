import type { AppConfig, Conversation, LLMModelInfo, STTModelInfo, TTSVoiceInfo, AudioDevice, SystemHealth } from './types'

const BASE = ''

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// Config
export const getConfig = () => request<AppConfig>('/api/config')
export const patchConfig = (patch: Partial<AppConfig>) =>
  request<AppConfig>('/api/config', { method: 'PATCH', body: JSON.stringify(patch) })
export const patchLLMConfig = (patch: object) =>
  request<AppConfig>('/api/config/llm', { method: 'PATCH', body: JSON.stringify(patch) })
export const patchSTTConfig = (patch: object) =>
  request<AppConfig>('/api/config/stt', { method: 'PATCH', body: JSON.stringify(patch) })
export const patchTTSConfig = (patch: object) =>
  request<AppConfig>('/api/config/tts', { method: 'PATCH', body: JSON.stringify(patch) })
export const patchAudioConfig = (patch: object) =>
  request<AppConfig>('/api/config/audio', { method: 'PATCH', body: JSON.stringify(patch) })
export const patchVADConfig = (patch: object) =>
  request<AppConfig>('/api/config/vad', { method: 'PATCH', body: JSON.stringify(patch) })

// Models
export const getLLMModels = () => request<LLMModelInfo[]>('/api/models/llm')
export const deleteLLMModel = (name: string) =>
  request(`/api/models/llm/${encodeURIComponent(name)}`, { method: 'DELETE' })
export const getSTTModels = () => request<STTModelInfo[]>('/api/models/stt')
export const downloadSTTModel = (name: string) =>
  request('/api/models/stt/download', { method: 'POST', body: JSON.stringify({ name }) })
export const getTTSVoices = () => request<TTSVoiceInfo[]>('/api/models/tts')
export const downloadTTSVoice = (name: string) =>
  request('/api/models/tts/download', { method: 'POST', body: JSON.stringify({ name }) })

// LLM model pull (NDJSON stream)
export async function* pullLLMModel(name: string) {
  const res = await fetch('/api/models/llm/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok || !res.body) throw new Error(`Pull failed: ${res.status}`)
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (line.trim()) yield JSON.parse(line)
    }
  }
}

// Audio
export const getAudioDevices = () => request<AudioDevice[]>('/api/audio/devices')
export const testSpeaker = (frequency = 440) =>
  request('/api/audio/test/speaker', { method: 'POST', body: JSON.stringify({ frequency }) })
export const testSpeakerVoice = (text: string, voice?: string) =>
  request('/api/audio/test/speaker/voice', { method: 'POST', body: JSON.stringify({ text, voice }) })
export const testMic = () => request<{ rms_dbfs: number }>('/api/audio/test/mic', { method: 'POST' })

// Control
export const pttStart = () => request('/api/control/ptt/start', { method: 'POST' })
export const pttStop = () => request('/api/control/ptt/stop', { method: 'POST' })
export const pause = () => request('/api/control/pause', { method: 'POST' })
export const resume = () => request('/api/control/resume', { method: 'POST' })
export const newConversation = () => request<{ id: string }>('/api/control/new_conversation', { method: 'POST' })

// Conversations
export const listConversations = (limit = 50) =>
  request<Conversation[]>(`/api/conversations?limit=${limit}`)
export const getConversation = (id: string) =>
  request<Conversation>(`/api/conversations/${id}`)
export const deleteConversation = (id: string) =>
  request(`/api/conversations/${id}`, { method: 'DELETE' })
export const exportConversation = (id: string) =>
  fetch(`/api/conversations/${id}/export`, { method: 'POST' })

// System
export const getSystemHealth = () => request<SystemHealth>('/api/system/health')
