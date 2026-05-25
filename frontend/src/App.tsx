import { useState } from 'react'
import { LayoutDashboard, Settings as SettingsIcon, MessageSquare } from 'lucide-react'
import { Dashboard } from './pages/Dashboard'
import { Settings } from './pages/Settings'
import { Conversations } from './pages/Conversations'
import { clsx } from 'clsx'

type Page = 'dashboard' | 'settings' | 'conversations'

const NAV = [
  { key: 'dashboard' as Page, label: 'Dashboard', Icon: LayoutDashboard },
  { key: 'settings' as Page, label: 'Settings', Icon: SettingsIcon },
  { key: 'conversations' as Page, label: 'History', Icon: MessageSquare },
]

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <div className="min-h-screen flex flex-col max-w-2xl mx-auto px-4 pt-4 pb-20">
      <header className="mb-4">
        <h1 className="text-lg font-bold text-white tracking-tight">Voice Assistant</h1>
        <p className="text-xs text-slate-400">Raspberry Pi · Local LLM</p>
      </header>

      <main className="flex-1 min-h-0">
        {page === 'dashboard' && <Dashboard />}
        {page === 'settings' && <Settings />}
        {page === 'conversations' && <Conversations />}
      </main>

      {/* Bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 bg-panel border-t border-border flex justify-around py-2 px-4">
        {NAV.map(({ key, label, Icon }) => (
          <button key={key} onClick={() => setPage(key)}
            className={clsx(
              'flex flex-col items-center gap-0.5 px-4 py-1 rounded-lg text-xs font-medium transition-colors',
              page === key ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300'
            )}>
            <Icon size={20} />
            {label}
          </button>
        ))}
      </nav>
    </div>
  )
}
