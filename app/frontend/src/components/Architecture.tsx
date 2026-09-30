import { useEffect, useState } from 'react'
import {
  Database, Users, Scale, Warehouse, Workflow, Layers, ShieldCheck,
  Sparkles, LayoutDashboard, MessageSquare, Table2, GitBranch, Lock,
} from 'lucide-react'
import { api } from '../api'
import { Card, Spinner } from './ui'

const DBX_RED = '#FF3621'

function Column({ title, children }: { title: string; children: any }) {
  return (
    <div className="border border-brand-border rounded overflow-hidden bg-white flex flex-col h-full">
      <div className="bg-brand-bg border-b border-brand-border px-3 py-2 text-xs font-semibold text-brand-ink uppercase tracking-wide">{title}</div>
      <div className="p-2.5 space-y-1.5 flex-1">{children}</div>
    </div>
  )
}
function Cell({ icon: Icon, title, sub }: { icon: any; title: string; sub: string }) {
  return (
    <div className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-brand-bg">
      <Icon size={15} className="text-brand mt-0.5 shrink-0" />
      <div className="min-w-0"><div className="text-xs font-semibold text-brand-ink truncate">{title}</div><div className="text-[10.5px] text-gray-500 leading-snug">{sub}</div></div>
    </div>
  )
}
function Tile({ icon: Icon, title, sub }: { icon: any; title: string; sub: string }) {
  return (
    <div className="flex flex-col items-center text-center gap-1 border border-brand-border rounded px-2 py-2.5 bg-white">
      <Icon size={17} className="text-brand" />
      <div className="text-[11px] font-semibold text-brand-ink leading-tight">{title}</div>
      <div className="text-[10px] text-gray-500 leading-tight">{sub}</div>
    </div>
  )
}
function Bar({ children }: { children: any }) {
  return <div className="bg-brand text-white text-xs font-semibold uppercase tracking-wide px-3 py-1.5 rounded">{children}</div>
}
function DashedBox({ title, children }: { title: string; children: any }) {
  return (
    <div className="border border-dashed border-brand-border rounded">
      <div className="bg-branddark text-white text-[11px] font-semibold px-2.5 py-1.5 rounded-t">{title}</div>
      <div className="p-2 grid grid-cols-2 gap-1.5">{children}</div>
    </div>
  )
}
function Connector({ n }: { n?: number }) {
  return (
    <div className="hidden xl:flex flex-col items-center justify-center">
      <div className="w-full h-0.5" style={{ background: DBX_RED }} />
      {n && <div className="w-5 h-5 rounded-full text-white text-[10px] font-bold flex items-center justify-center -mt-2.5" style={{ background: DBX_RED }}>{n}</div>}
    </div>
  )
}

export default function Architecture() {
  const [stats, setStats] = useState<any>(null)
  useEffect(() => { api.architectureStats().then(setStats).catch(() => setStats({ ok: false })) }, [])

  return (
    <div className="space-y-5 fadein">
      <div>
        <h2 className="acc-title">How it works on Databricks</h2>
        <p className="text-sm text-gray-500 mt-1 max-w-3xl">
          Five operational systems land in Unity Catalog, conform to one governed booking model, and serve
          the AI/BI dashboard, the Genie space and this app — all on the Databricks Data Intelligence Platform.
        </p>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[1080px] grid xl:grid-cols-[minmax(0,2fr)_26px_minmax(0,2fr)_26px_minmax(0,5.4fr)_26px_minmax(0,2.6fr)] gap-3 items-stretch">
          {/* Sources */}
          <Column title="Source systems">
            <Cell icon={Warehouse} title="Feedlot Master Data" sub="BPFL, Opal Ck, BVFL capacity" />
            <Cell icon={Users} title="Counterparties" sub="Agents, vendors, payees, buyers" />
            <Cell icon={Scale} title="Reference Data" sub="Programs, weigh points, origins" />
            <Cell icon={Table2} title="Bookings" sub="cattle_bookings - the hero table" />
            <Cell icon={GitBranch} title="Audit Trail" sub="booking_history, append-only" />
          </Column>
          <Connector n={1} />

          {/* Ingestion */}
          <Column title="Ingestion">
            <Cell icon={Workflow} title="Lakeflow Jobs" sub="Orchestrates the full deploy" />
            <Cell icon={Database} title="Auto Loader / read_files" sub="Parquet staged to a UC Volume" />
            <Cell icon={GitBranch} title="Lakeflow Connect" sub="Managed connectors (production shape)" />
          </Column>
          <Connector n={2} />

          {/* Platform boundary */}
          <div className="rounded" style={{ border: `2px solid ${DBX_RED}` }}>
            <div className="text-white text-xs font-bold uppercase tracking-wide px-3 py-1.5 rounded-t" style={{ background: DBX_RED }}>
              Databricks Data + AI Platform
            </div>
            <div className="p-3 space-y-2.5">
              <Bar>Bronze — raw, source-aligned Delta tables</Bar>
              <div className="text-[11px] text-gray-500 pl-1">Batch land via <code className="bg-brand-bg px-1 rounded">read_files</code> CTAS · schema evolution &amp; time travel</div>
              <Bar>Silver / Gold — conformed booking model</Bar>
              <div className="grid grid-cols-2 gap-2">
                <DashedBox title="acc_gold.booking_expanded">
                  <Cell icon={Layers} title="1 row / booking" sub="Every FK resolved to a name" />
                  <Cell icon={Sparkles} title="price_per_kg_numeric" sub="Parsed from free-text pricing" />
                </DashedBox>
                <DashedBox title="AI on the model">
                  <Cell icon={MessageSquare} title="Genie Space" sub="NL → SQL over gold" />
                  <Cell icon={Sparkles} title="Foundation Model API" sub="Feedlot capacity summaries" />
                </DashedBox>
              </div>
              <Bar>Governance &amp; deployment foundation</Bar>
              <div className="grid grid-cols-4 gap-1.5">
                <Tile icon={ShieldCheck} title="Unity Catalog" sub="ABAC + lineage" />
                <Tile icon={Database} title="Delta Lake" sub="Storage format" />
                <Tile icon={GitBranch} title="Asset Bundles" sub="Deploy pattern" />
                <Tile icon={Table2} title="System Tables" sub="Audit & cost" />
              </div>
            </div>
          </div>
          <Connector n={3} />

          {/* Consumption */}
          <Column title="Consumption">
            <div className="grid grid-cols-2 gap-1.5">
              <Tile icon={LayoutDashboard} title="This App" sub="React + FastAPI" />
              <Tile icon={MessageSquare} title="Ask ACC" sub="Embedded Genie" />
              <Tile icon={LayoutDashboard} title="AI/BI Dashboard" sub="3 Lakeview pages" />
              <Tile icon={ShieldCheck} title="Governance tab" sub="Live ABAC demo" />
            </div>
          </Column>
        </div>
      </div>
      <div className="text-[11px] text-gray-400 flex flex-wrap gap-x-4 gap-y-1">
        <span><b className="text-brand-ink">①</b> synthetic source data generated + staged</span>
        <span><b className="text-brand-ink">②</b> loaded into Unity Catalog tables</span>
        <span><b className="text-brand-ink">③</b> served to the app, Genie and the dashboard — all reading the same governed views</span>
      </div>

      {/* Masking policy table */}
      <Card title="Masking policy — Unity Catalog ABAC">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-gray-500 text-xs uppercase border-b border-brand-border">
              <th className="py-2 pr-3">Masking function</th><th className="pr-3">Unmasks for</th><th className="pr-3">Columns covered</th>
            </tr></thead>
            <tbody>
              <tr>
                <td className="py-2 pr-3 font-mono text-xs text-brand-ink">acc_gold.mask_str_proc</td>
                <td className="pr-3 text-gray-600">acc_exec, acc_procurement</td>
                <td className="pr-3 text-gray-600">cattle_bookings price_per_kg, price_variation, buyer_payee_details</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="mt-3 text-xs text-gray-500 flex items-start gap-2">
          <Lock size={13} className="mt-0.5 shrink-0" />
          Enforcement happens inside Unity Catalog on the base table, so it applies identically whether the query comes
          from this app, the AI/BI dashboard, Genie, or a raw SQL editor — nothing to reimplement per consumer.
        </div>
      </Card>

      {/* Deployed objects strip */}
      <Card title="Deployed objects (live counts)">
        {!stats ? <Spinner /> : !stats.ok ? (
          <div className="text-sm text-gray-400">Live counts unavailable in this environment ({stats.error || 'no warehouse'}).</div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <Stat label="Catalog" value={stats.catalog} small />
            <Stat label="Tables" value={stats.total_tables} />
            <Stat label="Gold views" value={stats.gold_views} />
            <Stat label="Tagged columns" value={stats.tagged_columns} />
            <Stat label="Masks applied" value={stats.masks_applied} />
            <Stat label="Bookings" value={stats.row_counts?.bookings} />
          </div>
        )}
      </Card>
    </div>
  )
}

function Stat({ label, value, small }: { label: string; value: any; small?: boolean }) {
  return (
    <div className="bg-white rounded border border-brand-border p-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-400">{label}</div>
      <div className={`font-bold text-brand-ink ${small ? 'text-xs mt-1 break-all' : 'text-xl mt-0.5'}`}>{value ?? '—'}</div>
    </div>
  )
}
