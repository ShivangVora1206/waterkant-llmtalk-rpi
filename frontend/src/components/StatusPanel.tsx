import { clsx } from 'clsx'
import type { PipelineState, SystemHealth } from '../api/types'

const STATE_COLORS: Record<PipelineState, string> = {
  IDLE: 'bg-slate-600 text-slate-200',
  LISTENING: 'bg-green-600 text-white animate-pulse',
  TRANSCRIBING: 'bg-yellow-500 text-black',
  THINKING: 'bg-blue-600 text-white animate-pulse',
  SPEAKING: 'bg-purple-600 text-white',
  PAUSED: 'bg-slate-500 text-slate-200',
  ERROR: 'bg-red-600 text-white animate-bounce',
}

interface Props {
  state: PipelineState
  connected: boolean
  audioLevel: number
  health: SystemHealth | null
}

export function StatusPanel({ state, connected, audioLevel, health }: Props) {
  const dbfs = Math.max(-60, audioLevel)
  const barWidth = Math.round(((dbfs + 60) / 60) * 100)

  return (
    <div className="rounded-xl bg-panel border border-border p-5 space-y-4">
      <div className="flex items-center gap-3">
        <span className={clsx('px-4 py-1.5 rounded-full text-sm font-semibold tracking-wide', STATE_COLORS[state])}>
          {state}
        </span>
        <span className={clsx('text-xs font-medium', connected ? 'text-green-400' : 'text-red-400')}>
          {connected ? '● Connected' : '○ Reconnecting…'}
        </span>
      </div>

      {/* VU meter */}
      <div>
        <div className="text-xs text-slate-400 mb-1">Mic level — {dbfs.toFixed(0)} dBFS</div>
        <div className="h-2 rounded-full bg-slate-700 overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full transition-all duration-75',
              barWidth > 80 ? 'bg-red-500' : barWidth > 50 ? 'bg-yellow-400' : 'bg-green-500'
            )}
            style={{ width: `${barWidth}%` }}
          />
        </div>
      </div>

      {/* System health */}
      {health && (
        <div className="grid grid-cols-3 gap-2 text-xs text-center">
          <div className="rounded-lg bg-slate-800 p-2">
            <div className="text-slate-400">CPU</div>
            <div className="text-white font-semibold">{health.cpu_percent.toFixed(0)}%</div>
          </div>
          <div className="rounded-lg bg-slate-800 p-2">
            <div className="text-slate-400">RAM free</div>
            <div className="text-white font-semibold">{health.ram_free_mb} MB</div>
          </div>
          <div className={clsx('rounded-lg bg-slate-800 p-2', health.throttled && 'border border-orange-500')}>
            <div className="text-slate-400">Temp</div>
            <div className={clsx('font-semibold', health.temp_c && health.temp_c > 80 ? 'text-red-400' : 'text-white')}>
              {health.temp_c != null ? `${health.temp_c.toFixed(0)}°C` : '—'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
