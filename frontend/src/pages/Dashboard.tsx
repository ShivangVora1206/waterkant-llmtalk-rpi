import { useEffect, useState } from 'react'
import { Mic, MicOff, Plus, Pause, Play } from 'lucide-react'
import { ConversationLog } from '../components/ConversationLog'
import { StatusPanel } from '../components/StatusPanel'
import { listConversations, getConversation, newConversation, pause, pttStart, pttStop, resume } from '../api/client'
import type { Turn } from '../api/types'
import { useWebSocketState } from '../hooks/useWebSocketState'

export function Dashboard() {
  const ws = useWebSocketState()
  const [turns, setTurns] = useState<Turn[]>([])
  const [pttHeld, setPttHeld] = useState(false)
  const [paused, setPaused] = useState(false)

  const refreshTurns = async () => {
    try {
      const convs = await listConversations(1)
      if (convs.length > 0) {
        const conv = await getConversation(convs[0].id)
        if (conv?.turns) setTurns(conv.turns)
      }
    } catch { /* ignore */ }
  }

  // Load turns on mount and whenever the backend signals a new turn was persisted
  useEffect(() => { refreshTurns() }, [])
  useEffect(() => { refreshTurns() }, [ws.conversationVersion])

  const handleNewConv = async () => {
    await newConversation()
    setTurns([])
  }

  const handlePause = async () => {
    if (paused) { await resume(); setPaused(false) }
    else { await pause(); setPaused(true) }
  }

  const handlePTT = async (down: boolean) => {
    setPttHeld(down)
    if (down) await pttStart()
    else await pttStop()
  }

  return (
    <div className="flex flex-col gap-4 h-full">
      <StatusPanel
        state={ws.state}
        connected={ws.connected}
        audioLevel={ws.audioLevel}
        health={ws.health}
      />

      {ws.lastError && (
        <div className="rounded-lg bg-red-900/50 border border-red-700 px-4 py-2 text-sm text-red-200">
          ⚠ {ws.lastError}
        </div>
      )}

      {/* Conversation */}
      <div className="flex-1 rounded-xl bg-panel border border-border p-4 overflow-hidden min-h-0">
        <ConversationLog
          turns={turns}
          liveTranscript={ws.state === 'TRANSCRIBING' || ws.state === 'THINKING' ? ws.lastTranscript : undefined}
          liveResponse={ws.state === 'THINKING' || ws.state === 'SPEAKING' ? ws.lastResponse : undefined}
        />
      </div>

      {/* Controls */}
      <div className="flex gap-2 flex-wrap">
        <button
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all select-none ${
            pttHeld
              ? 'bg-red-600 text-white scale-95'
              : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
          }`}
          onMouseDown={() => handlePTT(true)}
          onMouseUp={() => handlePTT(false)}
          onTouchStart={() => handlePTT(true)}
          onTouchEnd={() => handlePTT(false)}
        >
          {pttHeld ? <MicOff size={16} /> : <Mic size={16} />}
          Push-to-Talk
        </button>

        <button className="icon-btn" onClick={handlePause} title={paused ? 'Resume' : 'Pause'}>
          {paused ? <Play size={18} /> : <Pause size={18} />}
        </button>

        <button className="icon-btn" onClick={handleNewConv} title="New Conversation">
          <Plus size={18} />
        </button>
      </div>
    </div>
  )
}
