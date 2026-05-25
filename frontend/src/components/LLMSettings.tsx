import { useEffect, useState, useCallback } from 'react'
import { getLLMModels, patchLLMConfig, pullLLMModel } from '../api/client'
import type { LLMConfig, LLMModelInfo } from '../api/types'

interface Props {
  config: LLMConfig
  onConfigChange: () => void
}

export function LLMSettings({ config, onConfigChange }: Props) {
  const [models, setModels] = useState<LLMModelInfo[]>([])
  const [pulling, setPulling] = useState(false)
  const [pullName, setPullName] = useState('')
  const [pullProgress, setPullProgress] = useState('')
  const [local, setLocal] = useState<LLMConfig>(config)

  useEffect(() => { setLocal(config) }, [config])

  useEffect(() => {
    getLLMModels().then(setModels).catch(console.error)
  }, [])

  const patch = useCallback(async (key: keyof LLMConfig, value: unknown) => {
    try {
      await patchLLMConfig({ [key]: value })
      onConfigChange()
    } catch (e) { console.error(e) }
  }, [onConfigChange])

  const handlePull = async () => {
    if (!pullName.trim()) return
    setPulling(true)
    setPullProgress('Starting…')
    try {
      for await (const progress of pullLLMModel(pullName.trim())) {
        const pct = progress.total ? ` (${Math.round((progress.completed / progress.total) * 100)}%)` : ''
        setPullProgress(`${progress.status}${pct}`)
      }
      setPullProgress('Done!')
      getLLMModels().then(setModels)
    } catch (e: unknown) {
      setPullProgress(`Error: ${e}`)
    } finally {
      setPulling(false)
    }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">LLM</h3>

      <div>
        <label className="label">Model</label>
        <select
          className="input"
          value={local.model}
          onChange={e => { setLocal(l => ({ ...l, model: e.target.value })); patch('model', e.target.value) }}
        >
          {models.map(m => (
            <option key={m.name} value={m.name}>{m.name} ({(m.size_bytes / 1e9).toFixed(1)} GB)</option>
          ))}
        </select>
      </div>

      <Slider label="Temperature" min={0} max={2} step={0.05} value={local.temperature}
        onChange={v => setLocal(l => ({ ...l, temperature: v }))}
        onCommit={v => patch('temperature', v)} />
      <Slider label="Top-P" min={0} max={1} step={0.05} value={local.top_p}
        onChange={v => setLocal(l => ({ ...l, top_p: v }))}
        onCommit={v => patch('top_p', v)} />
      <Slider label="Top-K" min={0} max={100} step={1} value={local.top_k}
        onChange={v => setLocal(l => ({ ...l, top_k: v }))}
        onCommit={v => patch('top_k', v)} />
      <Slider label="Repeat Penalty" min={1} max={2} step={0.05} value={local.repeat_penalty}
        onChange={v => setLocal(l => ({ ...l, repeat_penalty: v }))}
        onCommit={v => patch('repeat_penalty', v)} />
      <Slider label="Max Tokens" min={64} max={2048} step={64} value={local.num_predict}
        onChange={v => setLocal(l => ({ ...l, num_predict: v }))}
        onCommit={v => patch('num_predict', v)} />
      <Slider label="Context Window" min={512} max={8192} step={512} value={local.num_ctx}
        onChange={v => setLocal(l => ({ ...l, num_ctx: v }))}
        onCommit={v => patch('num_ctx', v)} />

      <div>
        <label className="label">Keep Alive</label>
        <input className="input" value={local.keep_alive}
          onChange={e => setLocal(l => ({ ...l, keep_alive: e.target.value }))}
          onBlur={e => patch('keep_alive', e.target.value)} />
      </div>

      <div>
        <label className="label">System Prompt</label>
        <textarea className="input min-h-[80px] resize-y text-xs" value={local.system_prompt}
          onChange={e => setLocal(l => ({ ...l, system_prompt: e.target.value }))}
          onBlur={e => patch('system_prompt', e.target.value)} />
      </div>

      {/* Pull model */}
      <div className="border-t border-border pt-3 space-y-2">
        <label className="label">Pull Model from Ollama</label>
        <div className="flex gap-2">
          <input className="input flex-1" placeholder="e.g. qwen2.5:3b" value={pullName}
            onChange={e => setPullName(e.target.value)} />
          <button className="btn-primary" onClick={handlePull} disabled={pulling}>
            {pulling ? '…' : 'Pull'}
          </button>
        </div>
        {pullProgress && <p className="text-xs text-slate-400">{pullProgress}</p>}
      </div>
    </div>
  )
}

function Slider({ label, min, max, step, value, onChange, onCommit }: {
  label: string; min: number; max: number; step: number; value: number
  onChange: (v: number) => void; onCommit: (v: number) => void
}) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <label className="label">{label}</label>
        <span className="text-xs text-slate-300">{value}</span>
      </div>
      <input type="range" className="w-full accent-blue-500" min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
        onMouseUp={e => onCommit(Number((e.target as HTMLInputElement).value))}
        onTouchEnd={e => onCommit(Number((e.target as HTMLInputElement).value))} />
    </div>
  )
}
