import { useEffect, useState } from 'react'
import { downloadTTSVoice, getTTSVoices, patchTTSConfig, testSpeakerVoice } from '../api/client'
import type { TTSConfig, TTSVoiceInfo } from '../api/types'

interface Props {
  config: TTSConfig
  onConfigChange: () => void
}

export function TTSSettings({ config, onConfigChange }: Props) {
  const [voices, setVoices] = useState<TTSVoiceInfo[]>([])
  const [downloading, setDownloading] = useState<string | null>(null)
  const [local, setLocal] = useState<TTSConfig>(config)

  useEffect(() => { setLocal(config) }, [config])
  useEffect(() => { getTTSVoices().then(setVoices).catch(console.error) }, [])

  const patch = async (key: keyof TTSConfig, value: unknown) => {
    try { await patchTTSConfig({ [key]: value }); onConfigChange() } catch (e) { console.error(e) }
  }

  const handleDownload = async (name: string) => {
    setDownloading(name)
    try { await downloadTTSVoice(name); getTTSVoices().then(setVoices) } finally { setDownloading(null) }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Text-to-Speech</h3>

      <div>
        <label className="label">Voice</label>
        <div className="space-y-1">
          {voices.map(v => (
            <div key={v.name} className="flex items-center justify-between rounded-lg bg-slate-800 px-3 py-2 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="tts-voice" checked={local.voice === v.name}
                  onChange={() => { setLocal(l => ({ ...l, voice: v.name })); patch('voice', v.name) }} />
                <span>{v.name}</span>
                <span className="text-slate-500 text-[10px]">{v.size_mb}MB</span>
                {v.downloaded && <span className="text-[10px] text-green-400">✓</span>}
              </label>
              <div className="flex gap-1">
                {v.downloaded && (
                  <button className="btn-secondary text-xs py-0.5"
                    onClick={() => testSpeakerVoice('Hello, this is a voice preview.', v.name)}>
                    ▶
                  </button>
                )}
                {!v.downloaded && (
                  <button className="btn-secondary text-xs py-0.5"
                    onClick={() => handleDownload(v.name)} disabled={downloading === v.name}>
                    {downloading === v.name ? '…' : '↓'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="flex justify-between mb-1">
          <label className="label">Speed</label>
          <span className="text-xs text-slate-300">{local.speed.toFixed(2)}</span>
        </div>
        <input type="range" className="w-full accent-blue-500" min={0.5} max={2} step={0.05} value={local.speed}
          onChange={e => setLocal(l => ({ ...l, speed: Number(e.target.value) }))}
          onMouseUp={e => patch('speed', Number((e.target as HTMLInputElement).value))} />
      </div>

      <div>
        <div className="flex justify-between mb-1">
          <label className="label">Noise Scale</label>
          <span className="text-xs text-slate-300">{local.noise_scale.toFixed(3)}</span>
        </div>
        <input type="range" className="w-full accent-blue-500" min={0} max={1} step={0.05} value={local.noise_scale}
          onChange={e => setLocal(l => ({ ...l, noise_scale: Number(e.target.value) }))}
          onMouseUp={e => patch('noise_scale', Number((e.target as HTMLInputElement).value))} />
      </div>
    </div>
  )
}
