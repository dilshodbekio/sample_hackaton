import { useEffect, useRef, useState } from 'react'
import { api, streamMessage } from '../api.js'

const EXAMPLES = [
  'Oliy toifa uchun qanday talablar bor?',
  'Attestatsiya qancha muddatda o\'tkaziladi?',
  'test-topilmadi',
  'test-xato',
]

function Sources({ sources }) {
  if (!sources?.length) return null
  return (
    <div className="mt-3 border-t border-slate-100 pt-2">
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Manbalar</p>
      <ul className="space-y-1.5">
        {sources.map((s) => (
          <li key={`${s.doc_id}-${s.page}`} className="text-sm">
            <span className="font-medium text-indigo-700">
              {s.doc_name}, {s.page}-bet
            </span>
            {s.snippet && <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{s.snippet}</p>}
          </li>
        ))}
      </ul>
    </div>
  )
}

function TypingDots() {
  return (
    <span className="inline-flex gap-1 py-1" aria-label="Yozilmoqda">
      {[0, 150, 300].map((d) => (
        <span
          key={d}
          className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
    </span>
  )
}

function Message({ m }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2.5 text-white">
          {m.content}
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-2.5 shadow-sm">
        {m.pending && !m.content ? (
          <TypingDots />
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">
            {m.content}
            {m.pending && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-slate-400 align-middle" />}
          </p>
        )}
        {m.stopped && <p className="mt-2 text-xs italic text-slate-400">To'xtatildi</p>}
        {m.error && (
          <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{m.error}</p>
        )}
        {!m.pending && <Sources sources={m.sources} />}
      </div>
    </div>
  )
}

export default function Chat({ conversationId, onConversationCreated, onConversationsChanged }) {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [sendError, setSendError] = useState('')
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const controllerRef = useRef(null)
  const justCreatedRef = useRef(null)
  const bottomRef = useRef(null)

  // Suhbat almashganda: joriy oqimni to'xtatib, xabarlarni serverdan yuklash.
  useEffect(() => {
    if (justCreatedRef.current && justCreatedRef.current === conversationId) {
      justCreatedRef.current = null // o'zimiz yaratdik, xabarlar allaqachon ekranda
      return
    }
    controllerRef.current?.abort()
    setMessages([])
    setLoadError('')
    setSendError('')
    if (!conversationId) return
    let cancelled = false
    setLoading(true)
    api
      .listMessages(conversationId)
      .then((m) => !cancelled && setMessages(m))
      .catch((e) => !cancelled && setLoadError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [conversationId])

  useEffect(() => () => controllerRef.current?.abort(), [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages])

  async function send(text) {
    const question = (text ?? input).trim()
    if (!question || streaming) return
    setSendError('')
    setStreaming(true)

    let convId = conversationId
    if (!convId) {
      try {
        const conv = await api.createConversation()
        convId = conv.id
        justCreatedRef.current = conv.id
        onConversationCreated(conv.id)
        onConversationsChanged()
      } catch (e) {
        setSendError(e.message)
        setStreaming(false)
        return
      }
    }

    const localId = `local_${Date.now()}`
    const patch = (fn) => setMessages((ms) => ms.map((m) => (m.id === localId ? { ...m, ...fn(m) } : m)))
    setMessages((ms) => [
      ...ms,
      { id: `${localId}_q`, role: 'user', content: question },
      { id: localId, role: 'assistant', content: '', sources: [], pending: true },
    ])
    setInput('')

    const controller = new AbortController()
    controllerRef.current = controller
    await streamMessage(
      convId,
      { question },
      {
        onToken: (t) => patch((m) => ({ content: m.content + t })),
        onSources: (sources) => patch(() => ({ sources })),
        onDone: () => patch(() => ({ pending: false })),
        onError: (message) => patch(() => ({ pending: false, error: message })),
      },
      controller.signal,
    )
    if (controller.signal.aborted) patch(() => ({ pending: false, stopped: true }))
    if (controllerRef.current === controller) controllerRef.current = null
    setStreaming(false)
    onConversationsChanged() // birinchi savoldan keyin sarlavha yangilanadi
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const empty = !loading && !loadError && messages.length === 0

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 px-6 py-6">
          {loading && <p className="text-center text-sm text-slate-400">Yuklanmoqda...</p>}
          {loadError && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{loadError}</p>}
          {empty && (
            <div className="pt-16 text-center">
              <h2 className="text-xl font-semibold">Hujjatlaringiz bo'yicha savol bering</h2>
              <p className="mt-2 text-sm text-slate-500">
                Javob faqat yuklangan hujjatlarga tayanadi va manbasi ko'rsatiladi.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-600 hover:border-indigo-300 hover:text-indigo-700"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <Message key={m.id} m={m} />
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-3xl px-6 py-4">
          {sendError && <p className="mb-2 text-sm text-red-600">{sendError}</p>}
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Savolingizni yozing..."
              className="max-h-40 min-h-[44px] flex-1 resize-none rounded-xl border border-slate-300 px-4 py-2.5 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            {streaming ? (
              <button
                onClick={() => controllerRef.current?.abort()}
                className="h-11 rounded-xl bg-slate-800 px-4 text-sm font-medium text-white hover:bg-slate-900"
              >
                To'xtatish
              </button>
            ) : (
              <button
                onClick={() => send()}
                disabled={!input.trim()}
                className="h-11 rounded-xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Yuborish
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
