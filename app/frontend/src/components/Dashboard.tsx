import { useEffect, useMemo, useState } from 'react'
import { Plus, List } from 'lucide-react'
import { api, num, PROPERTIES, type BookingExpanded, type Property } from '../api'
import { Spinner } from './ui'

const FEEDLOT_LABEL: Record<Property, string> = { BPFL: 'Brindley Park', 'Opal Ck': 'Opal Creek', BVFL: 'Burnett Valley' }

export default function Dashboard({ onNewBooking, onViewAll }:
  { onNewBooking: (property?: Property) => void; onViewAll: () => void }) {
  const [bookings, setBookings] = useState<BookingExpanded[] | null>(null)

  useEffect(() => { api.bookings('exec').then(r => setBookings(r.bookings)) }, [])

  const stats = useMemo(() => {
    const byProperty: Record<Property, number> = { BPFL: 0, 'Opal Ck': 0, BVFL: 0 }
    let totalHead = 0, total = 0
    for (const b of bookings || []) {
      if (b.status === 'Cancelled') continue
      total += 1
      const head = Number(b.head_count)
      const n = Number.isFinite(head) ? head : 0
      totalHead += n
      byProperty[b.property] = (byProperty[b.property] ?? 0) + n
    }
    return { byProperty, totalHead, total }
  }, [bookings])

  return (
    <div className="space-y-6 fadein">
      <div>
        <h1 className="acc-title">ACC Livestock Procurement Planner</h1>
        <p className="text-sm text-gray-500 mt-1">Cattle bookings across all three feedlots</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Total Bookings" value={bookings ? num(stats.total) : '…'} />
        <Stat label="Total Head Count" value={bookings ? num(stats.totalHead) : '…'} />
      </div>

      <div>
        <h2 className="acc-kicker">Head count by feedlot</h2>
        {!bookings ? <Spinner /> : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {PROPERTIES.map(p => (
              <div key={p} className="rounded border border-brand-border bg-white p-5">
                <div className="text-sm font-medium text-gray-500">{FEEDLOT_LABEL[p]} <span className="text-gray-400">({p})</span></div>
                <div className="mt-2 acc-num text-[1.75rem] sm:text-4xl text-brand-ink">{num(stats.byProperty[p])}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="acc-kicker">Create booking</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {PROPERTIES.map(p => (
            <button key={p} onClick={() => onNewBooking(p)}
              className="min-h-[4.5rem] rounded bg-brand hover:bg-branddark text-white text-base font-semibold flex items-center justify-center gap-2 transition duration-200 ease-acc">
              <Plus size={20} /> New {p} booking
            </button>
          ))}
        </div>
      </div>

      <button onClick={onViewAll}
        className="min-h-14 w-full rounded border border-brand-border hover:border-brand text-brand-ink text-base font-semibold flex items-center justify-center gap-2 transition duration-200 ease-acc">
        <List size={20} /> View all bookings
      </button>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-brand-border bg-white p-5">
      <div className="text-sm text-gray-500">{label}</div>
      <div className="mt-2 acc-num text-[1.75rem] sm:text-4xl text-brand-ink">{value}</div>
    </div>
  )
}
