import { ReactNode, Fragment } from 'react'

// Capacity/status band colours. OPTIMAL=good (green), UNDER=headroom (blue),
// WATCH=amber, ACTION=needs attention (red), PENDING=not yet an outcome (slate).
export const bandColor: Record<string, string> = {
  OPTIMAL: '#1E7E34', UNDER: '#2563A8', WATCH: '#B8860B', ACTION: '#DC3545', PENDING: '#6C757D',
}
export const bandFill: Record<string, string> = {
  OPTIMAL: '#28A745', UNDER: '#4A90E2', WATCH: '#FFC107', ACTION: '#DC3545', PENDING: '#9CA3AF',
}

export function Card({ title, children, right, className = '' }:
  { title?: string; children: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-lg border border-brand-border ${className}`}>
      {title && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-brand-border">
          <h3 className="text-sm font-semibold text-brand-ink">{title}</h3>
          {right}
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}

export function KPI({ label, value, sub, accent }:
  { label: string; value: ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="bg-white rounded-lg border border-brand-border p-4 flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-gray-500">{label}</span>
      <span className="text-2xl font-bold font-sans" style={{ color: accent || '#252525' }}>{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  )
}

export function StatusBadge({ band, score, scoreLabel }: { band: string; score?: number | null; scoreLabel?: string }) {
  const c = bandColor[band] || '#888'
  const label = band === 'PENDING' ? 'Pending' : band.charAt(0) + band.slice(1).toLowerCase()
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold"
      style={{ background: `${c}18`, color: c, border: `1px solid ${c}40` }}>
      <span className="w-2 h-2 rounded-full" style={{ background: c }} />
      {label}{score != null ? ` · ${Math.round(score)}${scoreLabel ? ` ${scoreLabel}` : ''}` : ''}
    </span>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-gray-500 text-sm">
      <span className="spin inline-block w-4 h-4 border-2 border-gray-300 border-t-brand rounded-full" />
      {label || 'Loading…'}
    </div>
  )
}

export function Bar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: color }} />
    </div>
  )
}

export const chartTooltip = { background: '#fff', border: '1px solid #E2E7ED', borderRadius: 6, color: '#252525', fontSize: 12 }

/**
 * Lightweight markdown renderer for Foundation-Model text (headings, bold,
 * inline code, bullet/numbered lists, paragraphs). Avoids dumping raw
 * "## Heading" / "**bold**" as literal text with whitespace-pre-wrap.
 */
export function MarkdownBlock({ text, className = '' }: { text: string; className?: string }) {
  if (!text) return null
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []
  let list: { type: 'ul' | 'ol'; items: string[] } | null = null
  const flushList = (key: string) => {
    if (!list) return
    const Tag = list.type
    blocks.push(
      <Tag key={key} className={Tag === 'ul' ? 'list-disc pl-5 space-y-1 my-1.5' : 'list-decimal pl-5 space-y-1 my-1.5'}>
        {list.items.map((it, i) => <li key={i}>{inline(it)}</li>)}
      </Tag>
    )
    list = null
  }
  lines.forEach((raw, i) => {
    const line = raw.trim()
    if (!line) { flushList(`l${i}`); return }
    const h = /^(#{1,4})\s+(.*)$/.exec(line)
    if (h) {
      flushList(`l${i}`)
      const level = h[1].length
      const cls = level <= 2 ? 'text-base font-semibold text-brand-ink mt-2 mb-1' : 'text-sm font-semibold text-brand-ink mt-2 mb-1'
      blocks.push(<div key={`h${i}`} className={cls}>{inline(h[2])}</div>)
      return
    }
    const ul = /^[-*]\s+(.*)$/.exec(line)
    if (ul) {
      if (!list || list.type !== 'ul') { flushList(`l${i}`); list = { type: 'ul', items: [] } }
      list.items.push(ul[1])
      return
    }
    const ol = /^\d+[.)]\s+(.*)$/.exec(line)
    if (ol) {
      if (!list || list.type !== 'ol') { flushList(`l${i}`); list = { type: 'ol', items: [] } }
      list.items.push(ol[1])
      return
    }
    flushList(`l${i}`)
    blocks.push(<p key={`p${i}`} className="my-1 leading-relaxed">{inline(line)}</p>)
  })
  flushList('end')
  return <div className={`text-sm text-gray-700 ${className}`}>{blocks}</div>
}

function inline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean)
  return parts.map((s, i) => {
    if (s.startsWith('**') && s.endsWith('**')) return <strong key={i} className="text-brand-ink font-semibold">{s.slice(2, -2)}</strong>
    if (s.startsWith('`') && s.endsWith('`')) return <code key={i} className="text-[12px] bg-gray-100 text-brand-ink px-1 py-0.5 rounded">{s.slice(1, -1)}</code>
    return <Fragment key={i}>{s}</Fragment>
  })
}
