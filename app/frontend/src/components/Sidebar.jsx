const tabClass = (active) =>
  `flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
    active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-800'
  }`

export default function Sidebar({ view, onViewChange, conversations, activeId, onSelect, onNew, aiMock, error }) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-4">
        <h1 className="text-base font-semibold">Attestatsiya yordamchisi</h1>
        {aiMock && (
          <span className="mt-1 inline-block rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            Mock rejim
          </span>
        )}
        <div className="mt-3 flex gap-1 rounded-lg bg-slate-100 p-1">
          <button className={tabClass(view === 'chat')} onClick={() => onViewChange('chat')}>
            Suhbat
          </button>
          <button className={tabClass(view === 'documents')} onClick={() => onViewChange('documents')}>
            Hujjatlar
          </button>
        </div>
      </div>

      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          + Yangi suhbat
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-3">
        {error && <p className="px-2 py-1 text-xs text-red-600">{error}</p>}
        {!error && conversations.length === 0 && (
          <p className="px-2 py-1 text-sm text-slate-400">Hali suhbatlar yo'q</p>
        )}
        <ul className="space-y-1">
          {conversations.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => onSelect(c.id)}
                title={c.title}
                className={`w-full truncate rounded-md px-3 py-2 text-left text-sm ${
                  c.id === activeId && view === 'chat'
                    ? 'bg-indigo-50 font-medium text-indigo-700'
                    : 'text-slate-700 hover:bg-slate-100'
                }`}
              >
                {c.title}
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
