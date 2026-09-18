import { useEffect, useState } from 'react'
import { LayoutDashboard, ClipboardList, Settings2, TrendingUp, ShieldCheck, Sparkles, ExternalLink, Network } from 'lucide-react'
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

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <img src="/logo.png" alt="Australian Country Choice" className="h-11 w-auto shrink-0" />
      <div className="hidden sm:block leading-tight">
        <div className="font-bold text-[15px] text-brand-ink" style={{ fontFamily: "'Spectral', serif" }}>ACC Livestock Planner</div>
        <div className="text-[10px] text-gray-400 tracking-wide uppercase mt-0.5">Australian Country Choice</div>
      </div>
    </div>
  )
}

export default function App() {
  const [view, setView] = useState<TabId>(BLUEPRINT.tabs[0]?.id ?? 'overview')
  const [persona, setPersona] = useState<Persona>('exec')
  const [cfg, setCfg] = useState<any>({})
  const [navOpen, setNavOpen] = useState(false)
  const [workspace, setWorkspace] = useState<BookingWorkspaceMode | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => { fetch('/api/config').then(r => r.json()).then(setCfg).catch(() => {}) }, [])
  const activeLabel = BLUEPRINT.tabs.find(t => t.id === view)?.label ?? ''

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

  const navButtons = () => (
    <nav className="flex items-center gap-1 overflow-x-auto">
      {BLUEPRINT.tabs.map(t => {
        const Icon = ICONS[t.id]
        const active = view === t.id && !workspace
        return (
          <button key={t.id} onClick={() => { setView(t.id); setWorkspace(null); setNavOpen(false) }}
            aria-current={active ? 'page' : undefined}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-[13px] font-semibold uppercase tracking-wide whitespace-nowrap
              border-b-2 transition-colors
              ${active ? 'text-brand-ink border-accent' : 'text-gray-500 border-transparent hover:text-brand hover:border-brand-border'}`}>
            {Icon && <Icon size={15} />} {t.label}
          </button>
        )
      })}
    </nav>
  )

  const personaSwitch = () => (
    <div className="flex items-center gap-2 sm:gap-3">
      <span className="hidden md:inline text-[11px] uppercase tracking-wide text-gray-400">Viewing as</span>
      <div className="flex bg-gray-100 rounded-lg p-0.5">
        {PERSONAS.map(p => (
          <button key={p.id} onClick={() => setPersona(p.id)}
            className={`px-2.5 py-1.5 rounded-md text-xs font-medium transition
              ${persona === p.id ? 'bg-brand text-white' : 'text-gray-500 hover:text-brand-ink'}`}>
            {p.label}
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
    <div className="flex flex-col h-screen bg-brand-bg text-brand-ink">
      <a href="#acc-main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-2 focus:px-3 focus:py-2 focus:bg-white focus:border focus:border-brand focus:rounded">Skip to content</a>
      <header className="shrink-0 bg-white border-b border-brand-border">
        <div className="flex items-center justify-between gap-3 px-4 sm:px-6 h-16">
          <Logo />
          <div className="flex items-center gap-3">
            <div className="hidden sm:block">{brandLinks()}</div>
            {personaSwitch()}
            <button className="md:hidden p-2 -mr-1 text-gray-500" aria-label="Toggle navigation menu"
              aria-expanded={navOpen} aria-controls="acc-nav" onClick={() => setNavOpen(o => !o)}>
              <span className="block w-5 h-0.5 bg-current mb-1" />
              <span className="block w-5 h-0.5 bg-current mb-1" />
              <span className="block w-5 h-0.5 bg-current" />
            </button>
          </div>
        </div>
        <div id="acc-nav" className={`${navOpen ? 'block' : 'hidden'} md:block border-t border-brand-border px-2 sm:px-6`}>
          {navButtons()}
        </div>
      </header>
      <main id="acc-main" className="flex-1 overflow-y-auto p-4 sm:p-6">
        {workspace ? (
          <BookingWorkspace mode={workspace} onDone={closeWorkspace} onBack={() => setWorkspace(null)} />
        ) : (
          <>
            <div className="text-xs text-gray-400 mb-3 hidden sm:block">{activeLabel}</div>
            {renderView(view)}
          </>
        )}
      </main>
    </div>
  )
}
