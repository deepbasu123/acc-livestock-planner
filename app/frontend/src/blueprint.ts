// Hand-tuned to match the reference app's exact information architecture
// (dashboard / bookings / admin) plus the Databricks-flavoured bonus tabs
// (capacity forecast / governance / genie / architecture). See brand.json /
// blueprint.json for the original generator inputs.

export type NavPattern = 'top' | 'left' | 'hybrid'

export type TabId =
  | 'overview'      // dashboard: totals, head-by-feedlot, new-booking shortcuts
  | 'bookings'      // full list: search, filter, export, click-through to detail
  | 'admin'         // master data management (agents/vendors/payees/...)
  | 'forecast'      // capacity forecast (bonus, Databricks-derived)
  | 'governance'    // ABAC persona-masking demo (spine, always present)
  | 'genie'         // Genie chat (spine, always present)
  | 'architecture'  // "how it works on Databricks"

export interface BlueprintTab {
  id: TabId
  label: string
}

export interface Blueprint {
  archetype: string
  navPattern: NavPattern
  tabs: BlueprintTab[]
}

export const BLUEPRINT: Blueprint = {
  archetype: 'ops_console',
  navPattern: 'top',
  tabs: [
    { id: 'overview', label: 'Dashboard' },
    { id: 'bookings', label: 'Bookings' },
    { id: 'admin', label: 'Master Data' },
    { id: 'forecast', label: 'Capacity Forecast' },
    { id: 'governance', label: 'Governance' },
    { id: 'genie', label: 'Ask ACC' },
    { id: 'architecture', label: 'Architecture' },
  ],
}
