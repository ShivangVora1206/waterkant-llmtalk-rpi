import { useEffect, useState } from 'react'
import { getConfig } from '../api/client'
import type { AppConfig } from '../api/types'
import { AudioSettings } from '../components/AudioSettings'
import { LLMSettings } from '../components/LLMSettings'
import { STTSettings } from '../components/STTSettings'
import { TTSSettings } from '../components/TTSSettings'

type Tab = 'llm' | 'stt' | 'tts' | 'audio'

export function Settings() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [tab, setTab] = useState<Tab>('llm')

  const refresh = () => getConfig().then(setConfig).catch(console.error)
  useEffect(() => { refresh() }, [])

  if (!config) return <div className="text-slate-400 text-sm">Loading settings…</div>

  const tabs: { key: Tab; label: string }[] = [
    { key: 'llm', label: 'LLM' },
    { key: 'stt', label: 'STT' },
    { key: 'tts', label: 'TTS' },
    { key: 'audio', label: 'Audio & VAD' },
  ]

  return (
    <div className="space-y-4">
      <div className="flex gap-1 rounded-xl bg-panel border border-border p-1">
        {tabs.map(t => (
          <button key={t.key}
            className={`flex-1 py-1.5 text-sm rounded-lg font-medium transition-colors ${
              tab === t.key ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="rounded-xl bg-panel border border-border p-5">
        {tab === 'llm' && <LLMSettings config={config.llm} onConfigChange={refresh} />}
        {tab === 'stt' && <STTSettings config={config.stt} onConfigChange={refresh} />}
        {tab === 'tts' && <TTSSettings config={config.tts} onConfigChange={refresh} />}
        {tab === 'audio' && <AudioSettings config={config} onConfigChange={refresh} />}
      </div>
    </div>
  )
}
