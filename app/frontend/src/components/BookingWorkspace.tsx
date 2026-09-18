import { useEffect, useState } from 'react'
import { ArrowLeft, Copy, Trash2, Clock } from 'lucide-react'
import { api, type Property, type BookingExpanded } from '../api'
import { formatDateTime } from '../lib/week'
import { Spinner } from './ui'
import BookingForm, { bookingToInput } from './BookingForm'

type Mode = { kind: 'new'; property?: Property } | { kind: 'edit'; id: string }

export default function BookingWorkspace({ mode, onDone, onBack }:
  { mode: Mode; onDone: () => void; onBack: () => void }) {
  const [lookups, setLookups] = useState<any>(null)
  const [booking, setBooking] = useState<BookingExpanded | null>(null)
  const [history, setHistory] = useState<any[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const tasks: Promise<any>[] = [api.lookups().then(setLookups)]
    if (mode.kind === 'edit') {
      tasks.push(api.booking(mode.id).then(setBooking))
      tasks.push(api.bookingHistory(mode.id).then(r => setHistory(r.history)))
    }
    Promise.all(tasks).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode.kind, mode.kind === 'edit' ? mode.id : mode.property])

  if (loading || !lookups) return <Spinner label="Loading booking form…" />
  if (mode.kind === 'edit' && !booking) return <div className="text-sm text-gray-400">Booking not found.</div>

  const title = mode.kind === 'new' ? 'New Booking' : 'Edit Booking'
  const subtitle = mode.kind === 'edit' && booking
    ? `${booking.property} · ${booking.head_count} head · ${booking.week_number ?? booking.week_commencing ?? ''}`
    : 'Enter the booking details below'

  const doDuplicate = async () => {
    if (mode.kind !== 'edit') return
    setBusy(true)
    try {
      const dup = await api.duplicateBooking(mode.id)
      onDone()
      // eslint-disable-next-line no-alert
      alert(`Booking duplicated as ${dup.id.slice(0, 8)}… (status reset to Draft)`)
    } catch (e) { setError(String(e)) }
    setBusy(false)
  }

  const doDelete = async () => {
    if (mode.kind !== 'edit') return
    if (!confirm('Delete this booking? It will be removed from lists (soft delete, never hard-deleted).')) return
    setBusy(true)
    try { await api.deleteBooking(mode.id); onDone() } catch (e) { setError(String(e)) }
    setBusy(false)
  }

  return (
    <div className="space-y-4 fadein max-w-3xl">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <button onClick={onBack} className="p-1.5 text-gray-400 hover:text-brand-ink" aria-label="Back to bookings"><ArrowLeft size={18} /></button>
          <div>
            <h2 className="text-lg font-semibold text-brand-ink" style={{ fontFamily: "'Spectral', serif" }}>{title}</h2>
            <p className="text-xs text-gray-500">{subtitle}</p>
          </div>
        </div>
        {mode.kind === 'edit' && (
          <div className="flex items-center gap-2">
            <button onClick={doDuplicate} disabled={busy} className="flex items-center gap-1.5 border border-brand-border hover:border-brand text-brand-ink text-xs font-semibold px-3 py-2 rounded">
              <Copy size={14} /> Duplicate
            </button>
            <button onClick={() => setShowHistory(s => !s)} className="flex items-center gap-1.5 border border-brand-border hover:border-brand text-brand-ink text-xs font-semibold px-3 py-2 rounded">
              <Clock size={14} /> History ({history.length})
            </button>
            <button onClick={doDelete} disabled={busy} className="flex items-center gap-1.5 border border-brand-border hover:border-red-300 text-bad-text text-xs font-semibold px-3 py-2 rounded">
              <Trash2 size={14} /> Delete
            </button>
          </div>
        )}
      </div>

      {showHistory && mode.kind === 'edit' && (
        <div className="border border-brand-border rounded bg-white p-3 max-h-64 overflow-y-auto space-y-2">
          {history.length === 0 ? <div className="text-sm text-gray-400">No history yet.</div> : history.map(h => (
            <div key={h.id} className="text-xs border-b border-gray-100 pb-2 last:border-0 last:pb-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-brand-ink capitalize">{h.action}</span>
                <span className="text-gray-400">by {h.changed_by || 'system'} · {formatDateTime(h.changed_at)}</span>
              </div>
              {h.old_data && <div className="text-gray-400 mt-0.5 truncate">was: {h.old_data}</div>}
            </div>
          ))}
        </div>
      )}

      <BookingForm
        initial={mode.kind === 'edit' && booking ? bookingToInput(booking) : null}
        initialProperty={mode.kind === 'new' ? mode.property : undefined}
        lookups={lookups}
        busy={busy}
        error={error}
        submitLabel={mode.kind === 'edit' ? 'Save changes' : 'Save'}
        onCancel={onBack}
        onSubmit={async (values) => {
          setBusy(true); setError('')
          try {
            if (mode.kind === 'edit') await api.updateBooking(mode.id, values)
            else await api.createBooking(values)
            onDone()
          } catch (e) { setError(String(e)) }
          setBusy(false)
        }}
        onSubmitAndAddAnother={mode.kind === 'new' ? async (values) => {
          setBusy(true); setError('')
          try { await api.createBooking(values) } catch (e) { setError(String(e)) }
          setBusy(false)
        } : undefined}
      />
    </div>
  )
}
