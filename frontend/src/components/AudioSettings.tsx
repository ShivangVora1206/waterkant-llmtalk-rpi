import { useEffect, useState } from 'react'
import { getAudioDevices, patchAudioConfig, patchConfig, patchVADConfig, testMic, testSpeaker } from '../api/client'
import type { AppConfig, AudioDevice, AudioConfig, VADConfig } from '../api/types'

interface Props {
  config: AppConfig
  onConfigChange: () => void
}

export function AudioSettings({ config, onConfigChange }: Props) {
  const [devices, setDevices] = useState<AudioDevice[]>([])
  const [micResult, setMicResult] = useState<string | null>(null)
  const [audio, setAudio] = useState<AudioConfig>(config.audio)
  const [vad, setVAD] = useState<VADConfig>(config.vad)

  useEffect(() => { setAudio(config.audio); setVAD(config.vad) }, [config])
  useEffect(() => { getAudioDevices().then(setDevices).catch(console.error) }, [])

  const inputs = devices.filter(d => d.max_input_channels > 0)
  const outputs = devices.filter(d => d.max_output_channels > 0)

  const patchAudio = async (key: keyof AudioConfig, value: unknown) => {
    try { await patchAudioConfig({ [key]: value }); onConfigChange() } catch (e) { console.error(e) }
  }
  const patchVAD = async (key: keyof VADConfig, value: unknown) => {
    try { await patchVADConfig({ [key]: value }); onConfigChange() } catch (e) { console.error(e) }
  }

  const handleMicTest = async () => {
    setMicResult('Recording 3s…')
    try {
      const r = await testMic()
      setMicResult(`RMS: ${r.rms_dbfs} dBFS`)
    } catch { setMicResult('Error') }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">Audio & VAD</h3>

      <div>
        <label className="label">Mode</label>
        <select className="input" value={config.mode}
          onChange={e => { patchConfig({ mode: e.target.value as 'continuous' | 'push_to_talk' }).then(onConfigChange) }}>
          <option value="continuous">Continuous (VAD-gated)</option>
          <option value="push_to_talk">Push-to-Talk</option>
        </select>
      </div>

      <div>
        <label className="label">Input Device</label>
        <select className="input" value={audio.input_device ?? ''}
          onChange={e => { const v = e.target.value ? Number(e.target.value) : null; setAudio(a => ({ ...a, input_device: v })); patchAudio('input_device', v) }}>
          <option value="">System Default</option>
          {inputs.map(d => <option key={d.index} value={d.index}>{d.name}</option>)}
        </select>
      </div>

      <div>
        <label className="label">Output Device</label>
        <select className="input" value={audio.output_device ?? ''}
          onChange={e => { const v = e.target.value ? Number(e.target.value) : null; setAudio(a => ({ ...a, output_device: v })); patchAudio('output_device', v) }}>
          <option value="">System Default</option>
          {outputs.map(d => <option key={d.index} value={d.index}>{d.name}</option>)}
        </select>
      </div>

      <div className="flex gap-2">
        <button className="btn-secondary flex-1" onClick={() => testSpeaker()}>Test Speaker</button>
        <button className="btn-secondary flex-1" onClick={handleMicTest}>Test Mic</button>
      </div>
      {micResult && <p className="text-xs text-slate-400">{micResult}</p>}

      <div className="border-t border-border pt-3 space-y-3">
        <h4 className="text-xs font-semibold text-slate-400 uppercase">VAD Settings</h4>

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={vad.enabled}
            onChange={e => { setVAD(v => ({ ...v, enabled: e.target.checked })); patchVAD('enabled', e.target.checked) }} />
          Enable VAD
        </label>

        <div>
          <div className="flex justify-between mb-1">
            <label className="label">Threshold</label>
            <span className="text-xs text-slate-300">{vad.threshold.toFixed(2)}</span>
          </div>
          <input type="range" className="w-full accent-blue-500" min={0} max={1} step={0.05} value={vad.threshold}
            onChange={e => setVAD(v => ({ ...v, threshold: Number(e.target.value) }))}
            onMouseUp={e => patchVAD('threshold', Number((e.target as HTMLInputElement).value))} />
        </div>

        <div>
          <div className="flex justify-between mb-1">
            <label className="label">Min Speech (ms)</label>
            <span className="text-xs text-slate-300">{vad.min_speech_ms}</span>
          </div>
          <input type="range" className="w-full accent-blue-500" min={100} max={2000} step={50} value={vad.min_speech_ms}
            onChange={e => setVAD(v => ({ ...v, min_speech_ms: Number(e.target.value) }))}
            onMouseUp={e => patchVAD('min_speech_ms', Number((e.target as HTMLInputElement).value))} />
        </div>

        <div>
          <div className="flex justify-between mb-1">
            <label className="label">Silence Timeout (ms)</label>
            <span className="text-xs text-slate-300">{vad.silence_timeout_ms}</span>
          </div>
          <input type="range" className="w-full accent-blue-500" min={300} max={3000} step={100} value={vad.silence_timeout_ms}
            onChange={e => setVAD(v => ({ ...v, silence_timeout_ms: Number(e.target.value) }))}
            onMouseUp={e => patchVAD('silence_timeout_ms', Number((e.target as HTMLInputElement).value))} />
        </div>
      </div>
    </div>
  )
}
