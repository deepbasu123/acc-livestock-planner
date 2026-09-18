import { useEffect, useState } from 'react'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import { api, MASTER_TABLES, MASTER_LABELS, type MasterTable, type MasterRow } from '../api'
import { Spinner } from './ui'

export default function Admin() {
  const [active, setActive] = useState<MasterTable>('agents')
  return (
    <div className="space-y-4 fadein">
      <div>
        <h2 className="text-lg font-semibold text-brand-ink" style={{ fontFamily: "'Spectral', serif" }}>Master Data</h2>
        <p className="text-xs text-gray-500 mt-0.5">Manage the dropdown values used in bookings. Only active values appear in the booking form; historical bookings keep their original reference either way.</p>
      </div>
      <div role="tablist" className="flex flex-wrap gap-1 border-b border-brand-border">
        {MASTER_TABLES.map(t => (
          <button key={t} role="tab" aria-selected={active === t} onClick={() => setActive(t)}
            className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition
              ${active === t ? 'text-brand-ink border-accent' : 'text-gray-500 border-transparent hover:text-brand-ink'}`}>
            {MASTER_LABELS[t]}
          </button>
        ))}
      </div>
      <MasterPanel table={active} />
    </div>
  )
}

function MasterPanel({ table }: { table: MasterTable }) {
  const [rows, setRows] = useState<MasterRow[] | null>(null)
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [editing, setEditing] = useState<MasterRow | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = () => api.masterList(table).then(r => setRows(r.rows))
  useEffect(() => { setRows(null); load() }, [table])

  const save = async () => {
    if (!name.trim()) return
    setBusy(true); setError('')
    try {
      if (editing) await api.masterUpdate(table, editing.id, { name: name.trim() })
      else await api.masterAdd(table, name.trim())
      setOpen(false); setName(''); setEditing(null)
      await load()
    } catch (e) { setError(String(e)) }
    setBusy(false)
  }

  const toggleActive = async (row: MasterRow) => {
    try { await api.masterUpdate(table, row.id, { active: !row.active }); await load() } catch (e) { setError(String(e)) }
  }

  const remove = async (row: MasterRow) => {
    if (!confirm(`Delete "${row.name}"? This cannot be undone.`)) return
    try { await api.masterRemove(table, row.id); await load() } catch (e) { setError(String(e)) }
  }

  return (
    <div className="border border-brand-border rounded bg-white">
      <div className="flex items-center justify-between p-3 border-b border-brand-border">
        <h3 className="font-semibold text-sm text-brand-ink">{MASTER_LABELS[table]} {rows ? `(${rows.length})` : ''}</h3>
        <button onClick={() => { setEditing(null); setName(''); setOpen(true) }}
          className="flex items-center gap-1.5 bg-brand hover:bg-branddark text-white text-xs font-semibold px-3 py-1.5 rounded">
          <Plus size={14} /> Add
        </button>
      </div>

      {error && <div className="text-xs text-bad-text bg-red-50 px-3 py-2 border-b border-red-100">{error}</div>}

      {!rows ? <div className="p-4"><Spinner /></div> : rows.length === 0 ? (
        <div className="p-4 text-sm text-gray-400">No values yet.</div>
      ) : (
        <ul className="divide-y divide-gray-100">
          {rows.map(row => (
            <li key={row.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className={`text-sm min-w-0 truncate ${row.active ? 'text-brand-ink' : 'text-gray-400 line-through'}`}>{row.name}</span>
              <div className="flex items-center gap-3 shrink-0">
                <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer">
                  <input type="checkbox" checked={row.active} onChange={() => toggleActive(row)} className="accent-brand" /> Active
                </label>
                <button onClick={() => { setEditing(row); setName(row.name); setOpen(true) }} aria-label={`Rename ${row.name}`} className="text-gray-400 hover:text-brand-ink p-1"><Pencil size={15} /></button>
                <button onClick={() => remove(row)} aria-label={`Delete ${row.name}`} className="text-gray-400 hover:text-bad-text p-1"><Trash2 size={15} /></button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" onClick={() => setOpen(false)}>
          <div className="bg-white rounded border border-brand-border w-full max-w-sm p-5" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-brand-ink mb-3">{editing ? 'Rename' : 'Add'} {MASTER_LABELS[table].replace(/s$/, '')}</h3>
            <input autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="Name" className="acc-input"
              onKeyDown={e => e.key === 'Enter' && save()} />
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setOpen(false)} className="px-3 py-2 text-sm text-gray-500 hover:text-brand-ink">Cancel</button>
              <button onClick={save} disabled={busy} className="px-4 py-2 bg-brand hover:bg-branddark disabled:opacity-50 text-white text-sm font-semibold rounded">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
