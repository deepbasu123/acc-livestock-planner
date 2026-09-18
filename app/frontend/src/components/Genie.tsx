import { useState, useRef, useEffect } from 'react'
import { Send, Sparkles, User, Database } from 'lucide-react'
import { api } from '../api'
import { MarkdownBlock } from './ui'

const SUGGESTED = [
  'Which feedlot is closest to capacity this week?',
  'Total head count booked by feedlot this month?',
  'Which vendors have the highest cancellation rate?',
  'Which agents handle the most bookings?',
]

type Msg = { role: 'user' | 'genie'; text: string; sql?: string; table?: any }

export default function GenieChat() {
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [loading, setLoading] = useState(false)
  const [conv, setConv] = useState<string | undefined>()
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, loading])

  const ask = async (question: string) => {
    if (!question.trim() || loading) return
    setMsgs(m => [...m, { role: 'user', text: question }]); setQ(''); setLoading(true)
    try {
      const r = await api.genie(question, conv)
      setConv(r.conversation_id)
      setMsgs(m => [...m, { role: 'genie', text: r.answer, sql: r.sql, table: r.table }])
    } catch (e) {
      setMsgs(m => [...m, { role: 'genie', text: `Error: ${e}` }])
    }
    setLoading(false)
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto fadein">
      <div className="flex items-center gap-2 mb-3 text-sm text-gray-500">
        <Sparkles size={16} className="text-brand" />
        Ask natural-language questions across the unified ACC livestock model. Powered by <span className="text-brand-ink font-medium">AI/BI Genie</span> on Unity Catalog.
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {msgs.length === 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {SUGGESTED.map(s => (
              <button key={s} onClick={() => ask(s)} className="text-xs text-gray-600 bg-white border border-brand-border hover:border-brand hover:text-brand rounded-full px-3 py-1.5 transition">{s}</button>
            ))}
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : ''}`}>
            {m.role === 'genie' && <div className="w-8 h-8 rounded-lg bg-brand-bg flex items-center justify-center shrink-0"><Sparkles size={16} className="text-brand" /></div>}
            <div className={`max-w-[85%] sm:max-w-[80%] rounded-lg px-4 py-3 ${m.role === 'user' ? 'bg-brand text-white' : 'bg-white border border-brand-border'}`}>
              {m.role === 'user' ? <div className="text-sm leading-relaxed">{m.text}</div> : <MarkdownBlock text={m.text} />}
              {m.table && m.table.rows?.length > 0 && (
                <div className="mt-3 overflow-x-auto">
                  <table className="text-xs w-full">
                    <thead><tr className="text-gray-500 border-b border-brand-border">
                      {m.table.columns.map((c: string) => <th key={c} className="text-left py-1 pr-3">{c}</th>)}
                    </tr></thead>
                    <tbody>
                      {m.table.rows.slice(0, 12).map((row: any[], ri: number) => (
                        <tr key={ri} className="border-b border-gray-100">
                          {row.map((v, ci) => <td key={ci} className="py-1 pr-3 text-gray-700">{v}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {m.sql && (
                <details className="mt-2">
                  <summary className="text-[11px] text-gray-400 cursor-pointer flex items-center gap-1"><Database size={11} /> View generated SQL</summary>
                  <pre className="text-[11px] text-gray-600 bg-brand-bg border border-brand-border rounded p-2 mt-1 overflow-x-auto">{m.sql}</pre>
                </details>
              )}
            </div>
            {m.role === 'user' && <div className="w-8 h-8 rounded-lg bg-gray-200 flex items-center justify-center shrink-0"><User size={16} className="text-gray-600" /></div>}
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-bg flex items-center justify-center"><Sparkles size={16} className="text-brand" /></div>
            <div className="bg-white border border-brand-border rounded-lg px-4 py-3 text-sm text-gray-500">
              <span className="spin inline-block w-3.5 h-3.5 border-2 border-gray-300 border-t-brand rounded-full mr-2 align-middle" />
              Genie is thinking…
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="flex gap-2 pt-2 border-t border-brand-border">
        <input value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask(q)}
          placeholder="Ask Genie about bookings, feedlots, growers, transport…" aria-label="Ask Genie a question"
          className="acc-input flex-1" />
        <button onClick={() => ask(q)} disabled={loading}
          className="flex items-center gap-2 bg-brand hover:bg-branddark disabled:opacity-50 text-white text-sm font-semibold px-4 py-2.5 rounded">
          <Send size={15} /> Send
        </button>
      </div>
    </div>
  )
}
