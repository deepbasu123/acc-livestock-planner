import { useEffect, useState } from 'react'
import { LayoutDashboard, ClipboardList, Settings2, TrendingUp, ShieldCheck, Sparkles, ExternalLink, Network, MoreHorizontal, X } from 'lucide-react'
import { Persona, Property } from './api'
import Dashboard from './components/Dashboard'
import BookingsList from './components/BookingsList'
import BookingWorkspace from './components/BookingWorkspace'
import Admin from './components/Admin'
import Governance from './components/Governance'
import GenieChat from './components/Genie'
import CapacityForecast from './components/CapacityForecast'
import Architecture from './components/Architecture'
import { BLUEPRINT, TabId } from './blueprint'

const ICONS: Record<TabId, any> = {
  overview: LayoutDashboard,
  bookings: ClipboardList,
  admin: Settings2,
  forecast: TrendingUp,
  governance: ShieldCheck,
  genie: Sparkles,
  architecture: Network,
}

const PERSONAS: { id: Persona; label: string }[] = [
  { id: 'exec', label: 'Executive' },
  { id: 'procurement', label: 'Procurement' },
  { id: 'operations', label: 'Operations' },
]

type BookingWorkspaceMode = { kind: 'new'; property?: Property } | { kind: 'edit'; id: string }

// Mobile bottom tab bar shows only the reference app's 3 core screens
// (Dashboard/Bookings/Admin - see docs/SPEC.md's "bottom tab nav on mobile"
// UX principle); the 4 Databricks-bonus tabs live behind "More" so the core
// workflow keeps its intended one-tap prominence on a phone.
const CORE_TABS: TabId[] = ['overview', 'bookings', 'admin']
const MORE_TABS: TabId[] = ['forecast', 'governance', 'genie', 'architecture']

function Logo() {
  return (
    <div className="flex items-center gap-3 min-w-0">
      <img src="/logo.png" alt="Australian Country Choice" className="h-10 sm:h-11 w-auto shrink-0" />
      <div className="hidden sm:block leading-tight min-w-0">
        <div className="font-semibold text-[15px] text-brand-ink tracking-tight">ACC Livestock Planner</div>
        <div className="text-[11px] text-gray-500 mt-0.5">Australian Country Choice</div>
      </div>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState<TabId>(BLUEPRINT.tabs[0]?.id ?? 'overview')
  const [persona, setPersona] = useState<Persona>('exec')
  const [cfg, setCfg] = useState<any>({})
  const [moreOpen, setMoreOpen] = useState(false)
  const [workspace, setWorkspace] = useState<BookingWorkspaceMode | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => { fetch('/api/config').then(r => r.json()).then(setCfg).catch(() => {}) }, [])

  const openNewBooking = (property?: Property) => setWorkspace({ kind: 'new', property })
  const openBooking = (id: string) => setWorkspace({ kind: 'edit', id })
  const closeWorkspace = () => { setWorkspace(null); setRefreshKey(k => k + 1) }

  function renderView(id: TabId) {
    switch (id) {
      case 'overview': return <Dashboard onNewBooking={openNewBooking} onViewAll={() => setView('bookings')} />
      case 'bookings': return <BookingsList key={refreshKey} persona={persona} onOpen={openBooking} onNew={() => openNewBooking()} />
      case 'admin': return <Admin />
      case 'forecast': return <CapacityForecast persona={persona} />
      case 'governance': return <Governance persona={persona} />
      case 'genie': return <GenieChat />
      case 'architecture': return <Architecture />
      default: return null
    }
  }

  const goTo = (id: TabId) => { setView(id); setWorkspace(null); setMoreOpen(false) }

  const navButtons = () => (
    <nav className="flex items-center gap-1 overflow-x-auto">
      {BLUEPRINT.tabs.map(t => {
        const Icon = ICONS[t.id]
        const active = view === t.id && !workspace
        return (
          <button key={t.id} onClick={() => goTo(t.id)}
            aria-current={active ? 'page' : undefined}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-[13px] font-medium whitespace-nowrap
              border-b-2 transition-colors duration-200 ease-acc
              ${active ? 'text-brand-ink border-accent' : 'text-gray-500 border-transparent hover:text-brand hover:border-brand-border'}`}>
            {Icon && <Icon size={15} />} {t.label}
          </button>
        )
      })}
    </nav>
  )

  // Bottom tab bar (mobile only) - the reference app's exact pattern for its
  // 3 core screens; "More" is our own addition to reach the 4 bonus tabs.
  const bottomTabBar = () => {
    const isMoreActive = MORE_TABS.includes(view) && !workspace
    return (
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 bg-white border-t border-brand-border flex items-stretch"
        style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}>
        {CORE_TABS.map(id => {
          const Icon = ICONS[id]
          const label = BLUEPRINT.tabs.find(t => t.id === id)?.label ?? id
          const active = view === id && !workspace
          return (
            <button key={id} onClick={() => goTo(id)} aria-current={active ? 'page' : undefined}
              className={`flex-1 min-h-12 flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium
                ${active ? 'text-brand' : 'text-gray-500'}`}>
              <Icon size={20} />{label}
            </button>
          )
        })}
        <button onClick={() => setMoreOpen(true)} aria-haspopup="true" aria-expanded={moreOpen}
          className={`flex-1 min-h-12 flex flex-col items-center justify-center gap-0.5 text-[11px] font-medium
            ${isMoreActive ? 'text-brand' : 'text-gray-500'}`}>
          <MoreHorizontal size={20} />More
        </button>
      </nav>
    )
  }

  const moreSheet = () => (
    <div className="md:hidden fixed inset-0 z-40 flex items-end bg-black/40" role="dialog" aria-modal="true" onClick={() => setMoreOpen(false)}>
      <div className="bg-white w-full rounded-t-lg pb-[calc(1rem+env(safe-area-inset-bottom))] fadein" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-brand-border">
          <span className="text-sm font-semibold text-brand-ink">More</span>
          <button onClick={() => setMoreOpen(false)} aria-label="Close" className="w-11 h-11 -m-2 flex items-center justify-center text-gray-400"><X size={18} /></button>
        </div>
        <div className="p-2">
          {MORE_TABS.map(id => {
            const Icon = ICONS[id]
            const label = BLUEPRINT.tabs.find(t => t.id === id)?.label ?? id
            return (
              <button key={id} onClick={() => goTo(id)}
                className={`w-full flex items-center gap-3 px-3 min-h-[48px] rounded text-sm font-medium
                  ${view === id && !workspace ? 'text-brand bg-brand-bg' : 'text-brand-ink'}`}>
                <Icon size={18} /> {label}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )

  const personaSwitch = () => (
    <div className="flex items-center gap-2 sm:gap-3">
      <span className="hidden md:inline text-[12px] text-gray-500">Viewing as</span>
      <div className="flex bg-gray-100 rounded-lg p-0.5">
        {PERSONAS.map(p => (
          <button key={p.id} onClick={() => setPersona(p.id)}
            className={`min-h-11 px-2.5 sm:px-3 rounded-md text-xs font-medium transition duration-150 ease-acc
              ${persona === p.id ? 'bg-brand text-white' : 'text-gray-500 hover:text-brand-ink'}`}>
            <span className="sm:hidden">{p.id === 'exec' ? 'Exec' : p.id === 'procurement' ? 'Procure' : 'Ops'}</span>
            <span className="hidden sm:inline">{p.label}</span>
          </button>
        ))}
      </div>
    </div>
  )

  const brandLinks = () => (
    <div className="flex items-center gap-4">
      {cfg.dashboard_url && (
        <a href={cfg.dashboard_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand">
          <ExternalLink size={13} /> <span className="hidden lg:inline">AI/BI Dashboard</span>
        </a>
      )}
      {cfg.genie_url && (
        <a href={cfg.genie_url} target="_blank" rel="noreferrer" className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-brand">
          <ExternalLink size={13} /> <span className="hidden lg:inline">Genie Space</span>
        </a>
      )}
    </div>
  )

  return (
    <div className="flex flex-col min-h-[100dvh] h-[100dvh] bg-brand-bg text-brand-ink">
      <a href="#acc-main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:px-3 focus:py-2 focus:bg-white focus:border focus:border-brand focus:rounded">Skip to content</a>
      <header className="shrink-0 bg-white border-b border-brand-border">
        <div className="flex items-center justify-between gap-3 px-4 sm:px-6 h-14 sm:h-16">
          <Logo />
          <div className="flex items-center gap-3">
            <div className="hidden sm:block">{brandLinks()}</div>
            {personaSwitch()}
          </div>
        </div>
        <div className="hidden md:block border-t border-brand-border px-2 sm:px-6">
          {navButtons()}
        </div>
      </header>
      <main id="acc-main" className="flex-1 overflow-y-auto p-4 sm:p-6 pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-6">
        <div className="mx-auto w-full max-w-[1400px]">
        {workspace ? (
          <BookingWorkspace mode={workspace} onDone={closeWorkspace} onBack={() => setWorkspace(null)} />
        ) : (
          renderView(view)
        )}
        </div>
      </main>
      {bottomTabBar()}
      {moreOpen && moreSheet()}
    </div>
  )
}
