import { useEffect, useMemo, useState } from 'react'
import { Plus, Download, Search } from 'lucide-react'
import { api, num, PROPERTIES, STATUSES, type BookingExpanded, type Persona } from '../api'
import { formatDate } from '../lib/week'
import { Spinner } from './ui'
import { exportBookingsToExcel } from '../lib/export-excel'

const ALL = '__all__'
const STATUS_STYLE: Record<string, string> = {
  Draft: 'bg-gray-100 text-gray-600', Confirmed: 'bg-good/15 text-good-text', Cancelled: 'bg-bad/10 text-bad-text',
}
const PROPERTY_STYLE: Record<string, string> = {
  BPFL: 'bg-blue-50 text-blue-700', 'Opal Ck': 'bg-amber-50 text-amber-700', BVFL: 'bg-emerald-50 text-emerald-700',
}

export default function BookingsList({ persona, onOpen, onNew }:
  { persona: Persona; onOpen: (id: string) => void; onNew: () => void }) {
  const [bookings, setBookings] = useState<BookingExpanded[] | null>(null)
  const [comm, setComm] = useState(true)
  const [lookups, setLookups] = useState<any>(null)
  const [search, setSearch] = useState('')
  const [property, setProperty] = useState(ALL)
  const [status, setStatus] = useState(ALL)
  const [week, setWeek] = useState(ALL)
  const [buyerId, setBuyerId] = useState(ALL)
  const [agentId, setAgentId] = useState(ALL)
  const [originId, setOriginId] = useState(ALL)

  useEffect(() => {
    api.bookings(persona).then(r => { setBookings(r.bookings); setComm(r.commercial_visible) })
    api.lookups().then(setLookups)
  }, [persona])

  const weeks = useMemo(() => {
    const set = new Set<string>()
    ;(bookings || []).forEach(b => b.week_number && set.add(b.week_number))
    return Array.from(set).sort().reverse()
  }, [bookings])

  const filtered = useMemo(() => {
    if (!bookings) return []
    const q = search.trim().toLowerCase()
    return bookings.filter(b => {
      if (property !== ALL && b.property !== property) return false
      if (status !== ALL && b.status !== status) return false
      if (week !== ALL && b.week_number !== week) return false
      if (buyerId !== ALL && b.buyer_id !== buyerId) return false
      if (agentId !== ALL && b.agent_id !== agentId) return false
      if (originId !== ALL && b.origin_id !== originId) return false
      if (!q) return true
      const hay = [b.property, b.week_number, b.delivery_day, b.notes, b.buyer_name, b.vendor_name,
        b.agent_name, b.origin_name, b.payee_name, b.grid_text, b.program, b.price_per_kg,
        b.price_variation, b.buyer_payee_details, String(b.head_count ?? '')].filter(Boolean).join(' ').toLowerCase()
      return hay.includes(q)
    })
  }, [bookings, search, property, status, week, buyerId, agentId, originId])

  if (!bookings || !lookups) return <Spinner label="Loading bookings…" />

  return (
    <div className="space-y-4 fadein">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h2 className="text-lg font-semibold text-brand-ink" style={{ fontFamily: "'Spectral', serif" }}>Bookings</h2>
          <p className="text-xs text-gray-500 mt-0.5">{filtered.length} of {bookings.length} records</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => exportBookingsToExcel(filtered)}
            className="flex items-center gap-1.5 border border-brand-border hover:border-brand text-brand-ink text-sm font-semibold px-3 py-2 rounded">
            <Download size={15} /> <span className="hidden sm:inline">Export</span>
          </button>
          <button onClick={onNew} className="flex items-center gap-1.5 bg-brand hover:bg-branddark text-white text-sm font-semibold px-3.5 py-2 rounded">
            <Plus size={16} /> New
          </button>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search all fields…"
          aria-label="Search bookings" className="acc-input pl-9" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        <FilterSelect label="Feedlot" value={property} onChange={setProperty} options={PROPERTIES} />
        <FilterSelect label="Status" value={status} onChange={setStatus} options={STATUSES} />
        <FilterSelect label="Week" value={week} onChange={setWeek} options={weeks} />
        <MasterFilter label="Buyer" value={buyerId} onChange={setBuyerId} rows={lookups.buyers} />
        <MasterFilter label="Agent" value={agentId} onChange={setAgentId} rows={lookups.agents} />
        <MasterFilter label="Origin" value={originId} onChange={setOriginId} rows={lookups.origins} />
      </div>

      {/* Mobile cards */}
      <ul className="md:hidden space-y-2">
        {filtered.length === 0 ? (
          <li className="p-6 text-center text-sm text-gray-400 border border-brand-border rounded">No bookings match your filters.</li>
        ) : filtered.slice(0, 200).map(b => (
          <li key={b.id}>
            <button onClick={() => onOpen(b.id)} className="w-full text-left block rounded border border-brand-border bg-white p-3 hover:border-brand">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${PROPERTY_STYLE[b.property] || 'bg-gray-100'}`}>{b.property}</span>
                  <span className="text-sm font-medium text-brand-ink truncate">{b.buyer_name ?? '—'}</span>
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[b.status]}`}>{b.status}</span>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-500">
                <div><div className="text-brand-ink font-semibold">{b.head_count}</div>Head</div>
                <div><div className="text-brand-ink font-semibold truncate">{b.week_number ?? '—'}</div>Week</div>
                <div><div className="text-brand-ink font-semibold truncate">{b.delivery_day || '—'}</div>Delivery</div>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-gray-500">
                <div><div className="text-gray-700 truncate">{b.agent_name ?? '—'}</div>Agent</div>
                <div><div className="text-gray-700 truncate">{b.vendor_name ?? '—'}</div>Vendor</div>
                <div><div className="text-gray-700 truncate">{b.program ?? '—'}</div>Program</div>
              </div>
            </button>
          </li>
        ))}
      </ul>

      {/* Desktop table */}
      <div className="hidden md:block border border-brand-border rounded bg-white overflow-x-auto">
        <table className="w-full text-sm min-w-[1100px]">
          <thead className="bg-brand-bg text-gray-500">
            <tr className="text-left">
              <Th>Feedlot</Th><Th>Week</Th><Th>Head</Th><Th>Agent</Th><Th>Vendor</Th><Th>Grid</Th>
              <Th>Program</Th><Th>Buyer</Th><Th>Delivery</Th><Th>Status</Th>{comm && <Th>Price/Kg</Th>}<Th>Modified</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.length === 0 ? (
              <tr><td colSpan={12} className="p-6 text-center text-gray-400">No bookings match your filters.</td></tr>
            ) : filtered.slice(0, 200).map(b => (
              <tr key={b.id} onClick={() => onOpen(b.id)} tabIndex={0} role="button"
                onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(b.id) } }}
                className="hover:bg-brand-bg cursor-pointer focus:outline-none focus:bg-brand-bg">
                <Td><span className={`text-xs font-medium px-1.5 py-0.5 rounded ${PROPERTY_STYLE[b.property] || 'bg-gray-100'}`}>{b.property}</span></Td>
                <Td>{b.week_number ?? '—'}</Td>
                <Td className="font-medium">{num(b.head_count)}</Td>
                <Td>{b.agent_name ?? '—'}</Td>
                <Td>{b.vendor_name ?? '—'}</Td>
                <Td>{b.grid_text ?? '—'}</Td>
                <Td>{b.program ?? '—'}</Td>
                <Td>{b.buyer_name ?? '—'}</Td>
                <Td>{b.delivery_day || '—'}</Td>
                <Td><span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_STYLE[b.status]}`}>{b.status}</span></Td>
                {comm && <Td>{b.price_per_kg ?? '—'}</Td>}
                <Td className="text-xs text-gray-400 whitespace-nowrap">{formatDate(b.updated_at)}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: readonly string[] }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} aria-label={label} className="acc-input text-xs h-10">
      <option value={ALL}>All {label.toLowerCase()}</option>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  )
}
function MasterFilter({ label, value, onChange, rows }: { label: string; value: string; onChange: (v: string) => void; rows: { id: string; name: string }[] }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)} aria-label={label} className="acc-input text-xs h-10">
      <option value={ALL}>All {label.toLowerCase()}s</option>
      {rows.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select>
  )
}
function Th({ children }: { children: any }) { return <th className="px-3 py-2 font-medium text-xs uppercase tracking-wide">{children}</th> }
function Td({ children, className }: { children: any; className?: string }) { return <td className={`px-3 py-2 align-middle ${className ?? ''}`}>{children}</td> }
