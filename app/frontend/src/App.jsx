import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import Sidebar from './components/Sidebar.jsx'
import Chat from './components/Chat.jsx'
import Documents from './components/Documents.jsx'

export default function App() {
  const [view, setView] = useState('chat') // 'chat' | 'documents'
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [aiMock, setAiMock] = useState(null)
  const [listError, setListError] = useState('')

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations())
      setListError('')
    } catch (e) {
      setListError(e.message)
    }
  }, [])

  useEffect(() => {
    refreshConversations()
    api.health().then((h) => setAiMock(h.ai_mock)).catch(() => setAiMock(null))
  }, [refreshConversations])

  const openConversation = (id) => {
    setActiveId(id)
    setView('chat')
  }

  return (
    <div className="flex h-full bg-slate-50 text-slate-900">
      <Sidebar
        view={view}
        onViewChange={setView}
        conversations={conversations}
        activeId={activeId}
        onSelect={openConversation}
        onNew={() => openConversation(null)}
        aiMock={aiMock}
        error={listError}
      />
      {/* Ikkalasi ham mount bo'lib turadi: hujjatlarga o'tganda javob oqimi ham, polling ham uzilmaydi. */}
      <main className={`min-w-0 flex-1 flex-col ${view === 'chat' ? 'flex' : 'hidden'}`}>
        <Chat
          conversationId={activeId}
          onConversationCreated={setActiveId}
          onConversationsChanged={refreshConversations}
        />
      </main>
      <main className={`min-w-0 flex-1 flex-col ${view === 'documents' ? 'flex' : 'hidden'}`}>
        <Documents />
      </main>
    </div>
  )
}
