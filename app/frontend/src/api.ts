export type Persona = 'exec' | 'procurement' | 'operations'
export type Property = 'BPFL' | 'Opal Ck' | 'BVFL'
export type BookingStatus = 'Draft' | 'Confirmed' | 'Cancelled'
export const PROPERTIES: Property[] = ['BPFL', 'Opal Ck', 'BVFL']
export const STATUSES: BookingStatus[] = ['Draft', 'Confirmed', 'Cancelled']

async function get(path: string) {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`${r.status} ${await r.text().catch(() => path)}`)
  return r.json()
}
async function send(method: string, path: string, body?: any) {
  const r = await fetch(path, {
    method, headers: { 'Content-Type': 'application/json' }, body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!r.ok) throw new Error(`${r.status} ${await r.text().catch(() => path)}`)
  return r.json()
}

// Persona ids are the historical exec/finance/hr triad the backend + Unity
// Catalog groups (acc_exec / acc_procurement / acc_operations) enforce.
const PERSONA_WIRE: Record<Persona, string> = { exec: 'exec', procurement: 'procurement', operations: 'operations' }

export interface BookingExpanded {
  id: string
  property: Property
  feedlot_name: string
  status: BookingStatus
  week_number: string | null
  week_commencing: string | null
  head_count: number
  delivery_day: string | null
  agent_id: string | null; agent_name: string | null
  vendor_id: string | null; vendor_name: string | null
  payee_id: string | null; payee_name: string | null
  grid_text: string | null
  program: string | null
  price_per_kg: string | null
  price_per_kg_numeric: number | null
  price_variation: string | null
  weigh_point_id: string | null; weigh_point_name: string | null
  origin_id: string | null; origin_name: string | null
  buyer_id: string | null; buyer_name: string | null
  buyer_payee_details: string | null
  notes: string | null
  created_by: string | null; created_by_email: string | null; created_at: string
  modified_by: string | null; modified_by_email: string | null; updated_at: string
  deleted_at: string | null
}

export interface BookingInput {
  property: Property
  status?: BookingStatus
  week_number?: string | null
  week_commencing?: string | null
  head_count: number
  delivery_day?: string | null
  agent_id?: string | null
  vendor_id?: string | null
  payee_id?: string | null
  grid_text?: string | null
  program?: string | null
  price_per_kg?: string | null
  price_variation?: string | null
  weigh_point_id?: string | null
  origin_id?: string | null
  buyer_id?: string | null
  buyer_payee_details?: string | null
  notes?: string | null
}

export interface MasterRow { id: string; name: string; active: boolean; created_at: string; updated_at: string }
export const MASTER_TABLES = ['agents', 'vendors', 'payees', 'programs', 'weigh_points', 'origins', 'buyers'] as const
export type MasterTable = (typeof MASTER_TABLES)[number]
export const MASTER_LABELS: Record<MasterTable, string> = {
  agents: 'Agents', vendors: 'Vendor Properties', payees: 'Payees', programs: 'Programs',
  weigh_points: 'Weigh Points', origins: 'Origins', buyers: 'Buyers',
}

function asNum(v: any): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function coerceBooking(b: any): BookingExpanded {
  return {
    ...b,
    head_count: asNum(b.head_count) ?? 0,
    price_per_kg_numeric: asNum(b.price_per_kg_numeric),
  }
}

export const api = {
  config: () => get('/api/config'),

  // Bookings. Databricks SQL JSON_ARRAY returns every cell as a string, so
  // head_count arrives as "68" — coerce once here so dashboard sums stay numeric.
  bookings: async (persona: Persona = 'exec'): Promise<{ bookings: BookingExpanded[]; commercial_visible: boolean }> => {
    const r = await get(`/api/bookings?persona=${PERSONA_WIRE[persona]}`)
    return { ...r, bookings: (r.bookings || []).map(coerceBooking) }
  },
  // Always unmasked - this feeds the edit form. See bookings.py get_booking().
  booking: async (id: string) => coerceBooking(await get(`/api/bookings/${id}`)),
  bookingHistory: (id: string) => get(`/api/bookings/${id}/history`),
  lookups: () => get('/api/bookings/lookups'),
  createBooking: async (b: BookingInput): Promise<BookingExpanded> => coerceBooking(await send('POST', '/api/bookings', b)),
  updateBooking: async (id: string, b: BookingInput): Promise<BookingExpanded> => coerceBooking(await send('PATCH', `/api/bookings/${id}`, b)),
  deleteBooking: (id: string) => send('DELETE', `/api/bookings/${id}`),
  duplicateBooking: async (id: string): Promise<BookingExpanded> => coerceBooking(await send('POST', `/api/bookings/${id}/duplicate`)),

  // Master data
  // The Databricks SQL Statement API returns every cell as a string (including
  // booleans - "true"/"false"), and "false" is truthy in JS. Coerce here, once,
  // rather than risk a `row.active ? ... : ...` silently misreading an inactive
  // row as active everywhere this list is consumed.
  masterList: async (table: MasterTable, activeOnly = false): Promise<{ rows: MasterRow[] }> => {
    const r = await get(`/api/masterdata/${table}${activeOnly ? '?active_only=true' : ''}`)
    return { ...r, rows: r.rows.map((row: any) => ({ ...row, active: row.active === true || row.active === 'true' })) }
  },
  masterAdd: (table: MasterTable, name: string) => send('POST', `/api/masterdata/${table}`, { name }),
  masterUpdate: (table: MasterTable, id: string, patch: { name?: string; active?: boolean }) =>
    send('PATCH', `/api/masterdata/${table}/${id}`, patch),
  masterRemove: (table: MasterTable, id: string) => send('DELETE', `/api/masterdata/${table}/${id}`),

  // Bonus Databricks tabs
  feedlotSummary: (property: string) => send('POST', '/api/ai/feedlot-summary', { property }),
  governancePolicy: (persona: Persona) => get(`/api/governance/policy?persona=${PERSONA_WIRE[persona]}`),
  governanceBookingsSample: (persona: Persona) => get(`/api/governance/bookings-sample?persona=${PERSONA_WIRE[persona]}`),
  vendorScorecard: (persona: Persona) => get(`/api/governance/vendor-scorecard?persona=${PERSONA_WIRE[persona]}`),
  agentPerformance: () => get('/api/governance/agent-performance'),
  capacity: (persona: Persona) => get(`/api/capacity?persona=${PERSONA_WIRE[persona]}`),
  capacityInsight: (persona: Persona) => send('POST', '/api/capacity/ai-insight', { persona: PERSONA_WIRE[persona] }),
  genie: (question: string, conversation_id?: string) => send('POST', '/api/genie/ask', { question, conversation_id }),
  architectureStats: () => get('/api/architecture/stats'),
}

export const num = (n: any) => {
  const v = Number(n)
  return Number.isFinite(v) ? v.toLocaleString('en-AU') : '-'
}
