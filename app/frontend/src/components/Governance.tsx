import { useEffect, useState } from 'react'
import { ShieldCheck, Eye, EyeOff, Lock } from 'lucide-react'
import { api, num, Persona } from '../api'
import { Card, Spinner } from './ui'

const isMasked = (v: any) => typeof v === 'string' && v.includes('REDACTED')
const PERSONA_LABEL: Record<Persona, string> = { exec: 'Executive', procurement: 'Procurement', operations: 'Operations' }

export default function Governance({ persona }: { persona: Persona }) {
  const [sample, setSample] = useState<any[]>([])
  const [vendors, setVendors] = useState<any[]>([])
  const [pol, setPol] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([api.governanceBookingsSample(persona), api.vendorScorecard(persona), api.governancePolicy(persona)])
      .then(([s, v, p]) => { setSample(s.bookings); setVendors(v.vendors); setPol(p.rows) })
      .finally(() => setLoading(false))
  }, [persona])

  return (
    <div className="space-y-5 fadein">
      <Card>
        <div className="flex items-start gap-3">
          <ShieldCheck className="text-brand mt-0.5 shrink-0" size={22} />
          <div className="text-sm text-gray-600">
            Commercial pricing columns are governed by <span className="font-semibold text-brand-ink">Unity Catalog ABAC</span> —
            a column tag classifies them, and a tag-driven masking function reveals or redacts values based on the
            viewer's persona group (<code className="text-brand bg-brand-bg px-1 rounded">acc_exec</code> / <code className="text-brand bg-brand-bg px-1 rounded">acc_procurement</code> / <code className="text-brand bg-brand-bg px-1 rounded">acc_operations</code>).
            You're viewing as <span className="font-semibold text-brand-ink">{PERSONA_LABEL[persona]}</span> — switch personas in the top-right to watch enforcement change live.
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
        {pol.map(r => (
          <div key={r.field} className="bg-white rounded border border-brand-border p-3 flex items-center justify-between gap-2">
            <span className="text-xs text-gray-600">{r.field}</span>
            {r.visible
              ? <span className="flex items-center gap-1 text-xs text-good shrink-0"><Eye size={13} /> Visible</span>
              : <span className="flex items-center gap-1 text-xs text-brand shrink-0"><EyeOff size={13} /> Masked</span>}
          </div>
        ))}
      </div>

      {loading ? <Spinner /> : <>
        <Card title="Bookings — pricing fields (Procurement governed)" right={<span className="text-[10px] text-gray-400">PII/commercial governed by UC column masks</span>}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 text-xs uppercase border-b border-brand-border">
                <th className="py-2 pr-3">Booking</th><th className="pr-3">Feedlot</th><th className="pr-3">Vendor</th>
                <th className="pr-3">Buyer</th><th className="pr-3 text-right">Head</th>
                <th className="pr-3">Price/Kg</th><th className="pr-3">Variation</th><th className="pr-3">Payee Details</th>
              </tr></thead>
              <tbody>
                {sample.map((b: any) => (
                  <tr key={b.id} className="border-b border-gray-100">
                    <td className="py-2 pr-3 font-mono text-xs text-gray-400">{b.id.slice(0, 8)}…</td>
                    <td className="pr-3 text-brand-ink font-medium">{b.property}</td>
                    <td className="pr-3 text-gray-500">{b.vendor_name ?? '—'}</td>
                    <td className="pr-3 text-gray-500">{b.buyer_name ?? '—'}</td>
                    <td className="pr-3 text-right text-gray-700">{num(b.head_count)}</td>
                    <Cell v={b.price_per_kg} /><Cell v={b.price_variation} /><Cell v={b.buyer_payee_details} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Vendor Scorecard">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-gray-500 text-xs uppercase border-b border-brand-border">
                <th className="py-2 pr-3">Vendor</th><th className="pr-3 text-right">Bookings</th>
                <th className="pr-3 text-right">Cancel %</th><th className="pr-3 text-right">Head Booked</th><th className="pr-3 text-right">Avg Price/Kg</th>
              </tr></thead>
              <tbody>
                {vendors.slice(0, 15).map((v: any) => (
                  <tr key={v.vendor_id} className="border-b border-gray-100">
                    <td className="py-2 pr-3 text-brand-ink font-medium">{v.vendor_name}</td>
                    <td className="pr-3 text-right text-gray-700">{v.total_bookings}</td>
                    <td className="pr-3 text-right text-gray-500">{v.cancellation_rate_pct}%</td>
                    <td className="pr-3 text-right text-gray-700">{num(v.total_head_booked)}</td>
                    <td className="pr-3 text-right">{v.avg_price_per_kg != null ? `$${Number(v.avg_price_per_kg).toFixed(2)}` : <MaskCell />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </>}
    </div>
  )
}

function Cell({ v }: { v: any }) {
  const masked = isMasked(v)
  return (
    <td className="pr-3">
      {masked
        ? <span className="inline-flex items-center gap-1 text-brand font-mono text-xs bg-brand-bg px-1.5 py-0.5 rounded"><Lock size={11} /> ███</span>
        : <span className="text-gray-700">{v ?? '—'}</span>}
    </td>
  )
}
function MaskCell() {
  return <span className="inline-flex items-center gap-1 text-brand font-mono text-xs bg-brand-bg px-1.5 py-0.5 rounded"><Lock size={11} /> ███</span>
}
