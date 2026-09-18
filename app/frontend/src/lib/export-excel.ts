import * as XLSX from 'xlsx'
import type { BookingExpanded } from '../api'

// Column layout ported 1:1 from the reference app's src/lib/export-excel.ts -
// resolved names (not IDs) for every FK, plus timestamps.
export function exportBookingsToExcel(rows: BookingExpanded[], filename = 'cattle-bookings.xlsx') {
  const flat = rows.map((b) => ({
    'Booking ID': b.id,
    'Destination Feedlot': b.property,
    'Week Number': b.week_number ?? '',
    'Week Commencing': b.week_commencing ?? '',
    'Head Count': b.head_count,
    'Agent / Vendor': b.agent_name ?? '',
    'Vendor / Property': b.vendor_name ?? '',
    Payee: b.payee_name ?? '',
    Grid: b.grid_text ?? '',
    Program: b.program ?? '',
    'Price / Kg': b.price_per_kg ?? '',
    'Weigh Point': b.weigh_point_name ?? '',
    Origin: b.origin_name ?? '',
    'Price Variation': b.price_variation ?? '',
    'Delivery Day': b.delivery_day ?? '',
    Buyer: b.buyer_name ?? '',
    'Buyer Payee Details': b.buyer_payee_details ?? '',
    Notes: b.notes ?? '',
    Status: b.status,
    'Created Date': b.created_at,
    'Modified Date': b.updated_at,
  }))
  const ws = XLSX.utils.json_to_sheet(flat)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Bookings')
  XLSX.writeFile(wb, filename)
}
