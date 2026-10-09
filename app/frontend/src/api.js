// Backend bilan aloqa. Hamma so'rovlar /api orqali (Vite proxy → localhost:8000).

export const SERVER_DOWN = "Server bilan bog'lanib bo'lmadi. Backend ishlayotganini tekshiring."

export class ApiError extends Error {}

async function errorMessage(res) {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
  } catch {
    // javob JSON emas
  }
  return res.status >= 500 ? SERVER_DOWN : `So'rov bajarilmadi (HTTP ${res.status}).`
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`/api${path}`, options)
  } catch {
    throw new ApiError(SERVER_DOWN)
  }
  if (!res.ok) throw new ApiError(await errorMessage(res))
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  health: () => request('/health'),

  listDocuments: () => request('/documents'),
  getDocument: (id) => request(`/documents/${id}`),
  deleteDocument: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
  uploadDocument: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/documents', { method: 'POST', body: form })
  },

  listConversations: () => request('/conversations'),
  createConversation: () => request('/conversations', { method: 'POST' }),
  listMessages: (id) => request(`/conversations/${id}/messages`),
}

function parseEvent(raw) {
  let event = 'message'
  const dataLines = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!dataLines.length) return null
  try {
    return { event, data: JSON.parse(dataLines.join('\n')) }
  } catch {
    return null
  }
}

/**
 * Savol yuboradi va SSE oqimini o'qiydi (EventSource faqat GET qiladi, shuning uchun fetch).
 * handlers: onToken(text), onSources(sources), onDone(), onError(message).
 * signal bekor qilinsa (To'xtatish) hech qaysi handler chaqirilmaydi.
 */
export async function streamMessage(conversationId, body, handlers, signal) {
  const { onToken, onSources, onDone, onError } = handlers
  let res
  try {
    res = await fetch(`/api/conversations/${conversationId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    if (e.name !== 'AbortError') onError(SERVER_DOWN)
    return
  }
  if (!res.ok) {
    onError(await errorMessage(res))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
      // Bitta voqea bir necha bo'lakda kelishi mumkin: faqat \n\n gacha bo'lganini ajratamiz.
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const parsed = parseEvent(buffer.slice(0, idx))
        buffer = buffer.slice(idx + 2)
        if (!parsed) continue
        const { event, data } = parsed
        if (event === 'token') onToken(data.text ?? '')
        else if (event === 'sources') onSources(data.sources ?? [])
        else if (event === 'done') return onDone()
        else if (event === 'error') return onError(data.message || "Noma'lum xato yuz berdi.")
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') onError("Server bilan aloqa uzilib qoldi.")
    return
  }
  if (!signal?.aborted) onError('Javob oxirigacha kelmadi.')
}
