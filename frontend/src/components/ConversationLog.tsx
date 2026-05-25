import { useEffect, useRef } from 'react'
import type { Turn } from '../api/types'

interface Props {
  turns: Turn[]
  liveTranscript?: string
  liveResponse?: string
}

export function ConversationLog({ turns, liveTranscript, liveResponse }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns, liveTranscript, liveResponse])

  return (
    <div className="flex flex-col gap-3 h-full overflow-y-auto pr-1">
      {turns.map(turn => (
        <div
          key={turn.id}
          className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
              turn.role === 'user'
                ? 'bg-blue-700 text-white rounded-br-sm'
                : 'bg-slate-700 text-slate-100 rounded-bl-sm'
            }`}
          >
            {turn.text}
            {turn.stt_latency_ms > 0 && (
              <div className="text-[10px] opacity-50 mt-1">
                STT {turn.stt_latency_ms.toFixed(0)}ms
                {turn.llm_latency_ms > 0 && ` · LLM ${turn.llm_latency_ms.toFixed(0)}ms`}
              </div>
            )}
          </div>
        </div>
      ))}

      {liveTranscript && (
        <div className="flex justify-end">
          <div className="max-w-[80%] rounded-xl rounded-br-sm px-4 py-2.5 text-sm bg-blue-900 text-blue-200 italic">
            {liveTranscript}
          </div>
        </div>
      )}

      {liveResponse && (
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-xl rounded-bl-sm px-4 py-2.5 text-sm bg-slate-800 text-slate-200">
            {liveResponse}
            <span className="inline-block w-1 h-3.5 ml-0.5 bg-slate-400 animate-pulse align-text-bottom" />
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
