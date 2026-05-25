export type PipelineState =
  | 'IDLE'
  | 'LISTENING'
  | 'TRANSCRIBING'
  | 'THINKING'
  | 'SPEAKING'
  | 'PAUSED'
  | 'ERROR'

export interface AudioConfig {
  input_device: string | number | null
  output_device: string | number | null
  sample_rate: number
  channels: number
}

export interface VADConfig {
  enabled: boolean
  threshold: number
  min_speech_ms: number
  silence_timeout_ms: number
}

export interface STTConfig {
  backend: string
  model: string
  compute_type: string
  language: string
  beam_size: number
}

export interface LLMConfig {
  backend: string
  base_url: string
  model: string
  temperature: number
  top_p: number
  top_k: number
  num_ctx: number
  num_predict: number
  repeat_penalty: number
  system_prompt: string
  keep_alive: string
}

export interface TTSConfig {
  backend: string
  voice: string
  speed: number
  noise_scale: number
  length_scale: number
}

export interface ConversationConfig {
  history_turns: number
  store_to_disk: boolean
}

export interface ServerConfig {
  host: string
  port: number
}

export interface AppConfig {
  mode: 'continuous' | 'push_to_talk'
  audio: AudioConfig
  vad: VADConfig
  stt: STTConfig
  llm: LLMConfig
  tts: TTSConfig
  conversation: ConversationConfig
  server: ServerConfig
}

export interface LLMModelInfo {
  name: string
  size_bytes: number
  family: string
  quantisation: string
  modified_at: string
}

export interface STTModelInfo {
  name: string
  downloaded: boolean
}

export interface TTSVoiceInfo {
  name: string
  language: string
  sample_rate: number
  size_mb: number
  downloaded: boolean
}

export interface AudioDevice {
  index: number
  name: string
  max_input_channels: number
  max_output_channels: number
  default_samplerate: number
  hostapi: string
}

export interface Turn {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  text: string
  created_at: number
  stt_latency_ms: number
  llm_latency_ms: number
  tts_latency_ms: number
}

export interface Conversation {
  id: string
  created_at: number
  updated_at: number
  turns?: Turn[]
}

export interface SystemHealth {
  cpu_percent: number
  ram_total_mb: number
  ram_used_mb: number
  ram_free_mb: number
  temp_c: number | null
  throttled: boolean
}

// WebSocket event payloads
export interface WSEvent {
  type: string
  data: unknown
}
