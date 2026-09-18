import { useEffect, useState } from 'react'
import { PROPERTIES, STATUSES, type BookingInput, type BookingExpanded, type Property } from '../api'
import { isoWeekString, weekCommencing } from '../lib/week'

interface Lookups {
  agents: { id: string; name: string }[]
  vendors: { id: string; name: string }[]
  payees: { id: string; name: string }[]
  programs: { id: string; name: string }[]
  weigh_points: { id: string; name: string }[]
  origins: { id: string; name: string }[]
  buyers: { id: string; name: string }[]
  delivery_days: string[]
}

function makeEmpty(property: Property): BookingInput {
  return {
    property, status: 'Draft', week_number: '', week_commencing: null, head_count: 0,
    delivery_day: null, agent_id: null, vendor_id: null, payee_id: null,
    grid_text: '', program: null, price_per_kg: '', price_variation: '',
    weigh_point_id: null, origin_id: null, buyer_id: null, buyer_payee_details: '', notes: '',
  }
}

export function bookingToInput(b: BookingExpanded): BookingInput {
  return {
    property: b.property, status: b.status, week_number: b.week_number, week_commencing: b.week_commencing,
    head_count: b.head_count, delivery_day: b.delivery_day, agent_id: b.agent_id, vendor_id: b.vendor_id,
    payee_id: b.payee_id, grid_text: b.grid_text, program: b.program, price_per_kg: b.price_per_kg,
    price_variation: b.price_variation, weigh_point_id: b.weigh_point_id, origin_id: b.origin_id,
    buyer_id: b.buyer_id, buyer_payee_details: b.buyer_payee_details, notes: b.notes,
  }
}

export default function BookingForm({ initial, initialProperty, lookups, submitLabel = 'Save',
  onCancel, onSubmit, onSubmitAndAddAnother, busy, error }: {
  initial?: BookingInput | null
  initialProperty?: Property
  lookups: Lookups
  submitLabel?: string
  onCancel?: () => void
  onSubmit: (values: BookingInput) => void | Promise<void>
  onSubmitAndAddAnother?: (values: BookingInput) => void | Promise<void>
  busy?: boolean
  error?: string
}) {
  const [values, setValues] = useState<BookingInput>(() => initial ?? makeEmpty(initialProperty ?? 'BPFL'))
  const [validationError, setValidationError] = useState('')

  useEffect(() => {
    if (initial) setValues(initial)
    else if (initialProperty) setValues(v => ({ ...v, property: initialProperty }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial, initialProperty])

  const set = <K extends keyof BookingInput>(k: K, v: BookingInput[K]) => setValues(p => ({ ...p, [k]: v }))

  useEffect(() => {
    if (values.week_commencing && !values.week_number) {
      const d = new Date(values.week_commencing)
      if (!isNaN(d.getTime())) set('week_number', isoWeekString(weekCommencing(d)))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [values.week_commencing])

  const validate = () => {
    if (!values.property) { setValidationError('Destination Feedlot is required'); return false }
    if (!values.week_number && !values.week_commencing) { setValidationError('Week is required'); return false }
    if (!values.head_count || values.head_count <= 0) { setValidationError('Head Count must be greater than 0'); return false }
    setValidationError('')
    return true
  }

  const handleSave = async () => { if (validate()) await onSubmit(values) }
  const handleSaveAndNew = async () => {
    if (!validate() || !onSubmitAndAddAnother) return
    await onSubmitAndAddAnother(values)
    setValues(makeEmpty(values.property))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <div className="space-y-5">
      {(error || validationError) && (
        <div className="text-sm text-bad-text bg-red-50 border border-red-100 rounded px-3 py-2">{error || validationError}</div>
      )}

      <Section title="Booking">
        <Field label="Destination Feedlot *">
          <select className="acc-input" value={values.property} onChange={e => set('property', e.target.value as Property)}>
            {PROPERTIES.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select className="acc-input" value={values.status ?? 'Draft'} onChange={e => set('status', e.target.value as any)}>
            {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Week Number">
          <input className="acc-input" placeholder="e.g. 2026-W23" value={values.week_number ?? ''}
            onChange={e => set('week_number', e.target.value)} />
        </Field>
        <Field label="Week Commencing">
          <input type="date" className="acc-input" value={values.week_commencing ?? ''}
            onChange={e => set('week_commencing', e.target.value || null)} />
        </Field>
        <Field label="Head Count *">
          <input type="number" inputMode="numeric" min={1} className="acc-input" value={values.head_count || ''}
            onChange={e => set('head_count', Number(e.target.value) || 0)} />
        </Field>
        <Field label="Delivery Day">
          <select className="acc-input" value={values.delivery_day ?? ''} onChange={e => set('delivery_day', e.target.value || null)}>
            <option value="">— None —</option>
            {lookups.delivery_days.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
      </Section>

      <Section title="Vendor & Pricing">
        <Field label="Agent / Vendor"><MasterSelect rows={lookups.agents} value={values.agent_id} onChange={v => set('agent_id', v)} placeholder="Select agent" /></Field>
        <Field label="Vendor / Property"><MasterSelect rows={lookups.vendors} value={values.vendor_id} onChange={v => set('vendor_id', v)} placeholder="Select vendor" /></Field>
        <Field label="Payee"><MasterSelect rows={lookups.payees} value={values.payee_id} onChange={v => set('payee_id', v)} placeholder="Select payee" /></Field>
        <Field label="Grid">
          <input className="acc-input" placeholder="e.g. 2624+20c" value={values.grid_text ?? ''} onChange={e => set('grid_text', e.target.value)} />
        </Field>
        <Field label="Program">
          <select className="acc-input" value={values.program ?? ''} onChange={e => set('program', e.target.value || null)}>
            <option value="">— None —</option>
            {lookups.programs.map(p => <option key={p.id} value={p.name}>{p.name}</option>)}
          </select>
        </Field>
        <Field label="Price per Kg">
          <input className="acc-input" placeholder="e.g. 6.80" value={values.price_per_kg ?? ''} onChange={e => set('price_per_kg', e.target.value)} />
        </Field>
        <Field label="Price Variation" className="md:col-span-3">
          <input className="acc-input" placeholder="e.g. ACC pays freight" value={values.price_variation ?? ''} onChange={e => set('price_variation', e.target.value)} />
        </Field>
      </Section>

      <Section title="Logistics & Buyer">
        <Field label="Weigh Point"><MasterSelect rows={lookups.weigh_points} value={values.weigh_point_id} onChange={v => set('weigh_point_id', v)} placeholder="Select weigh point" /></Field>
        <Field label="Origin"><MasterSelect rows={lookups.origins} value={values.origin_id} onChange={v => set('origin_id', v)} placeholder="Select origin" /></Field>
        <Field label="Buyer"><MasterSelect rows={lookups.buyers} value={values.buyer_id} onChange={v => set('buyer_id', v)} placeholder="Select buyer" /></Field>
        <Field label="Buyer Payee Details" className="md:col-span-3">
          <input className="acc-input" value={values.buyer_payee_details ?? ''} onChange={e => set('buyer_payee_details', e.target.value)} />
        </Field>
      </Section>

      <Section title="Notes">
        <Field label="Notes" className="md:col-span-3">
          <textarea rows={3} className="acc-input resize-none" value={values.notes ?? ''} onChange={e => set('notes', e.target.value)} />
        </Field>
      </Section>

      <div className="sticky bottom-16 md:bottom-0 md:static -mx-4 md:mx-0 px-4 md:px-0 py-3 md:py-0 bg-white/95 md:bg-transparent backdrop-blur md:backdrop-blur-none border-t md:border-0 border-brand-border flex gap-2 flex-wrap z-10">
        <button onClick={handleSave} disabled={busy} className="h-11 px-5 flex-1 md:flex-none bg-brand hover:bg-branddark disabled:opacity-50 text-white text-sm font-semibold rounded">
          {submitLabel}
        </button>
        {onSubmitAndAddAnother && (
          <button onClick={handleSaveAndNew} disabled={busy} className="h-11 px-5 flex-1 md:flex-none border border-brand-border hover:border-brand text-brand-ink text-sm font-semibold rounded">
            Save &amp; Add Another
          </button>
        )}
        {onCancel && (
          <button onClick={onCancel} disabled={busy} className="h-11 px-4 text-gray-500 hover:text-brand-ink text-sm font-medium">Cancel</button>
        )}
      </div>
    </div>
  )
}

function MasterSelect({ rows, value, onChange, placeholder }:
  { rows: { id: string; name: string }[]; value: string | null | undefined; onChange: (v: string | null) => void; placeholder: string }) {
  return (
    <select className="acc-input" value={value ?? ''} onChange={e => onChange(e.target.value || null)}>
      <option value="">{placeholder}</option>
      {rows.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
    </select>
  )
}

function Section({ title, children }: { title: string; children: any }) {
  return (
    <section className="rounded border border-brand-border bg-white p-4 md:p-5">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">{children}</div>
    </section>
  )
}

function Field({ label, children, className }: { label: string; children: any; className?: string }) {
  return (
    <label className={`block space-y-1 ${className ?? ''}`}>
      <span className="block text-xs font-medium text-gray-500">{label}</span>
      {children}
    </label>
  )
}
