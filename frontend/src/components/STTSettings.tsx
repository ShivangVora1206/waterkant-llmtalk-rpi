import { useEffect, useState } from 'react'
import { downloadSTTModel, getSTTModels, patchSTTConfig } from '../api/client'
import type { STTConfig, STTModelInfo } from '../api/types'

interface Props {
  config: STTConfig
  onConfigChange: () => void
}

const COMPUTE_TYPES = ['int8', 'float16', 'float32']
const LANGUAGES = ['en', 'auto', 'de', 'fr', 'es', 'it', 'zh', 'ja']

export function STTSettings({ config, onConfigChange }: Props) {
  const [models, setModels] = useState<STTModelInfo[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [local, setLocal] = useState<STTConfig>(config)

  useEffect(() => { setLocal(config) }, [config])
  useEffect(() => { getSTTModels().then(setModels).catch(console.error) }, [])

  const patch = async (key: keyof STTConfig, value: unknown) => {
    try {
      await patchSTTConfig({ [key]: value })
      onConfigChange()
    } catch (e) { console.error(e) }
  }

  const handleDownload = async (name: string) => {
    setDownloading(name)
    try {
      await downloadSTTModel(name)
      getSTTModels().then(setModels)
    } finally { setDownloading(null) }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Speech-to-Text</h3>

      <div>
        <label className="label">Whisper Model</label>
        <div className="space-y-1">
          {models.map(m => (
            <div key={m.name} className="flex items-center justify-between rounded-lg bg-slate-800 px-3 py-2 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="stt-model" checked={local.model === m.name}
                  onChange={() => { setLocal(l => ({ ...l, model: m.name })); patch('model', m.name) }} />
                <span>{m.name}</span>
                {m.downloaded && <span className="text-[10px] text-green-400">✓</span>}
              </label>
              {!m.downloaded && (
                <button className="btn-secondary text-xs py-0.5"
                  onClick={() => handleDownload(m.name)} disabled={downloading === m.name}>
                  {downloading === m.name ? '…' : '↓'}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div>
        <label className="label">Language</label>
        <select className="input" value={local.language}
          onChange={e => { setLocal(l => ({ ...l, language: e.target.value })); patch('language', e.target.value) }}>
          {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
      </div>

      <div>
        <label className="label">Compute Type</label>
        <select className="input" value={local.compute_type}
          onChange={e => { setLocal(l => ({ ...l, compute_type: e.target.value })); patch('compute_type', e.target.value) }}>
          {COMPUTE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div>
        <div className="flex justify-between mb-1">
          <label className="label">Beam Size</label>
          <span className="text-xs text-slate-300">{local.beam_size}</span>
        </div>
        <input type="range" className="w-full accent-blue-500" min={1} max={5} step={1} value={local.beam_size}
          onChange={e => setLocal(l => ({ ...l, beam_size: Number(e.target.value) }))}
          onMouseUp={e => patch('beam_size', Number((e.target as HTMLInputElement).value))} />
      </div>
    </div>
  )
}
