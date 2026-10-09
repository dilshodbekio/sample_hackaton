import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'

const POLL_MS = 2000
const MAX_BYTES = 20 * 1024 * 1024

function StatusBadge({ doc }) {
  if (doc.status === 'processing') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
        <span className="h-3 w-3 animate-spin rounded-full border-2 border-amber-300 border-t-amber-700" />
        Qayta ishlanmoqda...
      </span>
    )
  }
  if (doc.status === 'ready') {
    return (
      <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">Tayyor</span>
    )
  }
  return <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">Xato</span>
}

export default function Documents() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setDocs(await api.listDocuments())
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // processing holatidagi har bir hujjatni 2 soniyada tekshirish; ready/failed bo'lsa to'xtaydi.
  const processingIds = docs.filter((d) => d.status === 'processing').map((d) => d.id).join(',')
  useEffect(() => {
    if (!processingIds) return
    const timer = setInterval(async () => {
      for (const id of processingIds.split(',')) {
        try {
          const fresh = await api.getDocument(id)
          setDocs((ds) => ds.map((d) => (d.id === id ? { ...d, ...fresh } : d)))
        } catch {
          // keyingi urinishda qayta tekshiriladi
        }
      }
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [processingIds])

  async function upload(file) {
    if (!file) return
    setError('')
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Faqat PDF fayl yuklash mumkin.')
      return
    }
    if (file.size > MAX_BYTES) {
      setError("Fayl juda katta (ko'pi bilan 20 MB).")
      return
    }
    setUploading(true)
    try {
      const doc = await api.uploadDocument(file)
      setDocs((ds) => [
        { pages: null, chunks: null, error: null, created_at: new Date().toISOString(), ...doc },
        ...ds.filter((d) => d.id !== doc.id),
      ])
    } catch (e) {
      setError(e.message)
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  async function remove(doc) {
    if (!window.confirm(`"${doc.name}" hujjatini o'chirasizmi?`)) return
    setError('')
    try {
      await api.deleteDocument(doc.id)
      setDocs((ds) => ds.filter((d) => d.id !== doc.id))
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-3xl px-6 py-8">
        <h2 className="text-xl font-semibold">Hujjatlar</h2>
        <p className="mt-1 text-sm text-slate-500">
          Nizom va qo'llanmalarni PDF ko'rinishida yuklang. Tayyor bo'lgach, ular bo'yicha savol berish mumkin.
        </p>

        <div
          onClick={() => !uploading && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            upload(e.dataTransfer.files?.[0])
          }}
          className={`mt-6 cursor-pointer rounded-xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragOver ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 bg-white hover:border-indigo-400'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => upload(e.target.files?.[0])}
          />
          {uploading ? (
            <p className="text-sm font-medium text-indigo-700">Yuklanmoqda...</p>
          ) : (
            <>
              <p className="text-sm font-medium text-slate-700">PDF faylni shu yerga tashlang yoki bosib tanlang</p>
              <p className="mt-1 text-xs text-slate-400">Ko'pi bilan 20 MB</p>
            </>
          )}
        </div>

        {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {loading ? (
            <p className="p-4 text-sm text-slate-400">Yuklanmoqda...</p>
          ) : docs.length === 0 ? (
            <p className="p-4 text-sm text-slate-400">Hali hujjat yuklanmagan</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {docs.map((d) => (
                <li key={d.id} className="flex items-center gap-4 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{d.name}</p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {d.status === 'ready' && `${d.pages} bet · ${d.chunks} bo'lak`}
                      {d.status === 'failed' && <span className="text-red-600">{d.error || 'Qayta ishlashda xato'}</span>}
                    </p>
                  </div>
                  <StatusBadge doc={d} />
                  <button
                    onClick={() => remove(d)}
                    className="rounded-md px-2 py-1 text-sm text-slate-400 hover:bg-red-50 hover:text-red-600"
                  >
                    O'chirish
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
