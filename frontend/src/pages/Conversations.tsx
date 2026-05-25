import { useEffect, useState } from 'react'
import { deleteConversation, exportConversation, getConversation, listConversations } from '../api/client'
import type { Conversation, Turn } from '../api/types'
import { Trash2, Download } from 'lucide-react'

export function Conversations() {
  const [convs, setConvs] = useState<Conversation[]>([])
  const [selected, setSelected] = useState<Conversation | null>(null)

  useEffect(() => { listConversations().then(setConvs).catch(console.error) }, [])

  const select = async (id: string) => {
    const conv = await getConversation(id)
    setSelected(conv)
  }

  const handleDelete = async (id: string) => {
    await deleteConversation(id)
    setConvs(c => c.filter(x => x.id !== id))
    if (selected?.id === id) setSelected(null)
  }

  const handleExport = async (id: string) => {
    const res = await exportConversation(id)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `conversation-${id}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex gap-3 h-full min-h-0">
      {/* Sidebar */}
      <div className="w-48 flex-shrink-0 flex flex-col gap-1 overflow-y-auto">
        <h3 className="text-xs font-semibold text-slate-400 uppercase px-1 pb-1">Conversations</h3>
        {convs.length === 0 && <p className="text-xs text-slate-500 px-1">No conversations yet</p>}
        {convs.map(c => (
          <button key={c.id}
            className={`text-left px-3 py-2 rounded-lg text-xs transition-colors ${
              selected?.id === c.id ? 'bg-blue-700 text-white' : 'bg-panel text-slate-300 hover:bg-slate-700'
            }`}
            onClick={() => select(c.id)}>
            <div className="truncate">{c.id.slice(0, 8)}…</div>
            <div className="text-[10px] opacity-60">
              {new Date(c.updated_at * 1000).toLocaleDateString()}
            </div>
          </button>
        ))}
      </div>

      {/* Detail */}
      <div className="flex-1 flex flex-col rounded-xl bg-panel border border-border overflow-hidden min-h-0">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
            Select a conversation
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-xs text-slate-400">{selected.id}</span>
              <div className="flex gap-2">
                <button className="icon-btn" onClick={() => handleExport(selected.id)} title="Export">
                  <Download size={14} />
                </button>
                <button className="icon-btn text-red-400 hover:bg-red-900/30"
                  onClick={() => handleDelete(selected.id)} title="Delete">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {(selected.turns ?? []).map((t: Turn) => (
                <div key={t.id} className={`flex ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] rounded-xl px-4 py-2 text-sm leading-relaxed ${
                    t.role === 'user' ? 'bg-blue-700 text-white' : 'bg-slate-700 text-slate-100'
                  }`}>
                    {t.text}
                    <div className="text-[10px] opacity-50 mt-0.5">
                      {new Date(t.created_at * 1000).toLocaleTimeString()}
                      {t.stt_latency_ms > 0 && ` · STT ${t.stt_latency_ms.toFixed(0)}ms`}
                      {t.llm_latency_ms > 0 && ` · LLM ${t.llm_latency_ms.toFixed(0)}ms`}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
