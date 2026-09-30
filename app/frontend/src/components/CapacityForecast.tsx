import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts'
import { Sparkles, Gauge, TrendingUp, TrendingDown, Info } from 'lucide-react'
import { api, num, Persona } from '../api'
import { Card, KPI, StatusBadge, Spinner, MarkdownBlock, chartTooltip } from './ui'

const FL_COLOR: Record<string, string> = { BPFL: '#002A54', 'Opal Ck': '#C9A227', BVFL: '#1E7E34' }

function pivotByFeedlot(weekly: any[], key: string) {
  const byWeek: Record<string, any> = {}
  weekly.forEach(w => {
    const wk = new Date(w.week_start).toLocaleDateString('en-AU', { day: '2-digit', month: 'short' })
    byWeek[wk] = byWeek[wk] || { week: wk }
    byWeek[wk][w.property] = w[key]
  })
  return Object.values(byWeek)
}

export default function CapacityForecast({ persona }: { persona: Persona }) {
  const [d, setD] = useState<any>(null)
  const [insight, setInsight] = useState('')
  const [loadingIns, setLoadingIns] = useState(false)

  useEffect(() => { setD(null); api.capacity(persona).then(setD).catch(() => {}) }, [persona])

  const genInsight = async () => {
    setLoadingIns(true); setInsight('')
    try { const r = await api.capacityInsight(persona); setInsight(r.insight) } catch (e) { setInsight(`Error: ${e}`) }
    setLoadingIns(false)
  }

  if (!d) return <Spinner label="Loading capacity forecast…" />
  const properties = Array.from(new Set((d.weekly || []).map((w: any) => w.property))) as string[]
  const utilSeries = pivotByFeedlot(d.weekly || [], 'utilization_pct')
  const priceSeries = pivotByFeedlot(d.price_trend || [], 'avg_price_per_kg')
  const priceUp = (d.kpi.price_change_pct ?? 0) >= 0

  return (
    <div className="space-y-5 fadein">
      <div>
        <h2 className="acc-title">Capacity forecast</h2>
        <p className="text-sm text-gray-500 mt-1 flex items-start gap-1.5">
          <Info size={13} className="mt-0.5 shrink-0" />
          A Databricks-derived estimate: on-feed inventory is a trailing 14-week rolling sum of booked head against
          pen capacity. The reference app only tracks bookings, not a full receival/turnoff system, so treat this as
          directional.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPI label="Peak Utilisation" value={d.kpi.peak_utilization_pct != null ? `${Math.round(d.kpi.peak_utilization_pct)}%` : '—'} accent={d.kpi.peak_utilization_pct > 100 ? '#DC3545' : undefined} />
        <KPI label="Feedlots to Watch" value={d.kpi.feedlots_over_target} accent={d.kpi.feedlots_over_target > 0 ? '#B8860B' : undefined} />
        <KPI label="Upcoming Booked Head" value={num(d.kpi.upcoming_head)} sub="Draft + Confirmed, future weeks" />
        <KPI label="Price Trend" value={d.kpi.price_change_pct != null ? <span className="flex items-center gap-1">{priceUp ? <TrendingUp size={16} className="text-good" /> : <TrendingDown size={16} className="text-bad-text" />}{d.kpi.price_change_pct}%</span> : '—'} sub="over horizon" />
      </div>

      <Card title="Utilisation % by Feedlot (weekly, history + forward bookings)">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={utilSeries} margin={{ left: -8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
            <XAxis dataKey="week" tick={{ fill: '#6B7280', fontSize: 10 }} interval={Math.ceil(utilSeries.length / 12)} />
            <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} unit="%" />
            <Tooltip contentStyle={chartTooltip} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {properties.map(p => <Line key={p} type="monotone" dataKey={p} stroke={FL_COLOR[p] || '#888'} strokeWidth={2} dot={false} connectNulls />)}
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card title="Avg Price per Kg by Feedlot (parsed from free-text price field)">
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={priceSeries} margin={{ left: -8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
              <XAxis dataKey="week" tick={{ fill: '#6B7280', fontSize: 10 }} interval={Math.ceil(priceSeries.length / 8)} />
              <YAxis tick={{ fill: '#6B7280', fontSize: 11 }} />
              <Tooltip contentStyle={chartTooltip} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {properties.map(p => <Line key={p} type="monotone" dataKey={p} stroke={FL_COLOR[p] || '#888'} strokeWidth={2} dot={false} connectNulls />)}
            </LineChart>
          </ResponsiveContainer>
        </Card>
        <Card title="AI Capacity Optimisation Strategy"
          right={<button onClick={genInsight} disabled={loadingIns}
            className="min-h-11 flex items-center gap-1.5 bg-brand hover:bg-branddark disabled:opacity-50 text-white text-sm font-semibold px-3 rounded">
            <Sparkles size={13} /> {loadingIns ? 'Generating…' : 'Generate'}</button>}>
          {loadingIns ? <Spinner label="Analysing capacity across the network…" /> :
            insight ? <MarkdownBlock text={insight} /> :
              <div className="text-sm text-gray-400 flex items-center gap-2"><Gauge size={16} /> Generate an AI capacity strategy — where to hold, redirect or accept new bookings.</div>}
        </Card>
      </div>

      <Card title="Feedlot Capacity Forecast">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-gray-500 text-xs uppercase border-b border-brand-border">
              <th className="py-2 pr-3">Feedlot</th><th className="pr-3 text-right">Est. On-Feed</th>
              <th className="pr-3 text-right">Capacity</th><th className="pr-3 text-right">Utilisation</th>
              <th className="pr-3 text-right">Target</th><th className="pr-3 text-center">Band</th><th className="pr-3">Recommended action</th>
            </tr></thead>
            <tbody>
              {(d.forecast || []).map((f: any) => (
                <tr key={f.property} className="border-b border-gray-100 last:border-0">
                  <td className="py-2.5 pr-3 font-medium text-brand-ink">{f.feedlot_name} <span className="text-gray-400">({f.property})</span></td>
                  <td className="pr-3 text-right text-gray-700">{num(f.head_on_feed_est)}</td>
                  <td className="pr-3 text-right text-gray-700">{num(f.total_capacity_head)}</td>
                  <td className="pr-3 text-right font-semibold text-brand-ink">{f.current_utilization_pct != null ? `${f.current_utilization_pct}%` : '—'}</td>
                  <td className="pr-3 text-right text-gray-500">{f.target_utilization_pct}%</td>
                  <td className="pr-3 text-center"><StatusBadge band={f.band} /></td>
                  <td className="pr-3 text-gray-600">{f.recommended_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
