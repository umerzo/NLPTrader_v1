import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { Signal } from '../api/client'
import { Badge, Button, Card } from './ui'
import { ChevronDown, ChevronUp, TrendingUp, AlertTriangle, Clock, Shield } from 'lucide-react'

const signalColors = {
  buy: { badge: 'buy', bg: 'bg-green-50 dark:bg-green-900/20', border: 'border-green-200 dark:border-green-800' },
  sell: { badge: 'sell', bg: 'bg-red-50 dark:bg-red-900/20', border: 'border-red-200 dark:border-red-800' },
  hold: { badge: 'hold', bg: 'bg-gray-50 dark:bg-gray-800/50', border: 'border-gray-200 dark:border-gray-700' },
}

interface SignalCardProps {
  signal: Signal
}

function sentimentLabel(signal: string, details?: any): string {
  const parts: string[] = []
  if (details?.article_count !== undefined) {
    parts.push(`${details.article_count} articles`)
  }
  if (details?.net_score !== undefined) {
    parts.push(`net ${details.net_score >= 0 ? '+' : ''}${details.net_score.toFixed(2)}`)
  }
  if (details?.positive_count !== undefined || details?.negative_count !== undefined) {
    const p = details.positive_count ?? 0
    const n = details.negative_count ?? 0
    parts.push(`${p} pos / ${n} neg`)
  }
  return parts.length > 0 ? parts.join(' · ') : (signal === 'buy' ? 'Bullish' : signal === 'sell' ? 'Bearish' : 'Neutral')
}

function fundamentalBrief(details?: any): string {
  if (details?.narrative) {
    return details.narrative
  }
  return ''
}

export function SignalCard({ signal }: SignalCardProps) {
  const [expanded, setExpanded] = useState(false)
  const colors = signalColors[signal.signal as keyof typeof signalColors] || signalColors.hold
  const generatedAt = new Date(signal.generated_at)
  const expiresAt = signal.expires_at ? new Date(signal.expires_at) : null

  return (
    <Card className={`${colors.border} ${colors.bg} transition-all ${expanded ? 'shadow-lg' : ''}`}>
      {/* Header (clickable) */}
      <div className="p-4 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg bg-gradient-to-br from-primary-500 to-primary-700">
              {signal.ticker[0]}
            </div>
            <div>
              <h3 className="font-semibold text-[var(--text-primary)]">{signal.ticker}</h3>
              <Badge variant={signal.signal === 'buy' ? 'success' : signal.signal === 'sell' ? 'destructive' : 'secondary'}>
                {signal.signal.toUpperCase()}
              </Badge>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-2xl font-bold text-[var(--text-primary)]">{signal.confidence}%</div>
              <div className="text-xs text-[var(--text-secondary)]">Confidence</div>
            </div>
            {expanded ? <ChevronUp className="w-5 h-5 text-[var(--text-secondary)]" /> : <ChevronDown className="w-5 h-5 text-[var(--text-secondary)]" />}
          </div>
        </div>

        {/* Sub-signals */}
        <div className="grid grid-cols-3 gap-2 mt-3 mb-3 p-3 bg-[var(--bg-secondary)] rounded-lg">
          <SubSignalBadge
            label="Technical"
            signal={signal.sub_signals.ta}
            explainer={signal.sub_signals.ta.details?.reasoning ? signal.sub_signals.ta.details.reasoning.split(';')[0].trim() : ''}
          />
          <SubSignalBadge
            label="Sentiment"
            signal={signal.sub_signals.sentiment}
            explainer={sentimentLabel(signal.sub_signals.sentiment.signal, signal.sub_signals.sentiment.details)}
          />
          <SubSignalBadge
            label="Fundamentals"
            signal={signal.sub_signals.fundamental}
            explainer={fundamentalBrief(signal.sub_signals.fundamental.details)}
          />
        </div>

        {/* Levels */}
        {(signal.entry || signal.sl || signal.tp1) && (
          <div className="grid grid-cols-4 gap-2 text-xs mb-3">
            <LevelBadge label="Entry" value={signal.entry} />
            <LevelBadge label="SL" value={signal.sl} color="red" />
            <LevelBadge label="TP1" value={signal.tp1} color="green" />
            <LevelBadge label="TP2" value={signal.tp2} color="green" />
          </div>
        )}

        {/* Meta */}
        <div className="flex items-center justify-between text-xs text-[var(--text-secondary)] border-t border-[var(--border-color)] pt-3">
          <div className="flex items-center gap-4">
            {signal.regime !== 'unknown' && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-[var(--bg-secondary)]">
                <span className="text-xs">📊</span> {signal.regime}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {expiresAt ? `Expires in ${formatDistanceToNow(expiresAt, { addSuffix: true })}` : 'No expiry'}
            </span>
          </div>
          <span>Generated {formatDistanceToNow(generatedAt, { addSuffix: true })}</span>
        </div>
      </div>

      {/* Expandable Details */}
      <div className={`overflow-hidden transition-all duration-300 ${expanded ? 'max-h-[5000px]' : 'max-h-0'}`}>
        <div className="border-t border-[var(--border-color)] p-4 space-y-4">
          {/* Reasoning */}
          <div>
            <h4 className="font-medium text-[var(--text-primary)] mb-2">Reasoning</h4>
            <p className="text-sm text-[var(--text-secondary)]">{signal.reasoning || 'No detailed reasoning available'}</p>
          </div>

          {/* Sub-signal details */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <SubSignalDetail title="Technical" signal={signal.sub_signals.ta} details={signal.sub_signals.ta.details} icon={<TrendingUp className="w-4 h-4" />} />
            <SubSignalDetail title="Sentiment" signal={signal.sub_signals.sentiment} details={signal.sub_signals.sentiment.details} icon={<AlertTriangle className="w-4 h-4" />} />
            <SubSignalDetail title="Fundamental" signal={signal.sub_signals.fundamental} details={signal.sub_signals.fundamental.details} icon={<Shield className="w-4 h-4" />} />
          </div>

          {/* Outcome (if available) */}
          {signal.outcome && (
            <div className="p-3 rounded-lg bg-[var(--bg-secondary)]">
              <h4 className="font-medium text-[var(--text-primary)] mb-2">Outcome</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-[var(--text-secondary)]">Result:</span> <span className={`font-medium ${signal.outcome.outcome === 'correct' ? 'text-green-600' : signal.outcome.outcome === 'incorrect' ? 'text-red-600' : 'text-yellow-600'}`}>{signal.outcome.outcome}</span></div>
                <div><span className="text-[var(--text-secondary)]">Price Change:</span> <span className="font-medium">{signal.outcome.price_change_pct !== null && signal.outcome.price_change_pct !== undefined ? (signal.outcome.price_change_pct > 0 ? '+' : '') + signal.outcome.price_change_pct.toFixed(2) + '%' : '—'}</span></div>
                <div><span className="text-[var(--text-secondary)]">Max Favorable:</span> <span className="font-medium text-green-600">+{signal.outcome.max_fav !== null && signal.outcome.max_fav !== undefined ? signal.outcome.max_fav.toFixed(2) : '—'}%</span></div>
                <div><span className="text-[var(--text-secondary)]">Max Adverse:</span> <span className="font-medium text-red-600">-{signal.outcome.max_adv !== null && signal.outcome.max_adv !== undefined ? signal.outcome.max_adv.toFixed(2) : '—'}%</span></div>
              </div>
            </div>
          )}

          {/* Expand Toggle */}
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <><ChevronUp className="w-4 h-4 mr-1" /> Less Detail</>
            ) : (
              <><ChevronDown className="w-4 h-4 mr-1" /> More Detail</>
            )}
          </Button>
        </div>
      </div>
    </Card>
  )
}

function SubSignalBadge({ label, signal, explainer }: { label: string; signal: { signal: string; confidence: number; details?: any }; explainer?: string }) {
  return (
    <div className="text-center">
      <p className="text-xs font-medium text-[var(--text-secondary)] mb-1">{label}</p>
      <div className="flex items-center justify-center gap-1">
        <Badge variant={signal.signal === 'buy' ? 'success' : signal.signal === 'sell' ? 'destructive' : 'secondary'} className="text-xs">
          {signal.signal.toUpperCase()}
        </Badge>
        <span className="text-xs text-[var(--text-secondary)]">{signal.confidence}%</span>
      </div>
      {explainer && (
        <p className="text-[11px] text-[var(--text-muted)] mt-1 leading-snug text-left px-1 line-clamp-3">{explainer}</p>
      )}
    </div>
  )
}

function LevelBadge({ label, value, color = 'blue' }: { label: string; value: number | null; color?: string }) {
  const colorClasses = {
    blue: 'text-blue-600 dark:text-blue-400',
    green: 'text-green-600 dark:text-green-400',
    red: 'text-red-600 dark:text-red-400',
  }
  return (
    <div className="text-center p-2 bg-[var(--bg-secondary)] rounded">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p className={`font-medium ${colorClasses[color as keyof typeof colorClasses] || colorClasses.blue}`}>
        {value ? value.toFixed(value < 100 ? 2 : 0) : '—'}
      </p>
    </div>
  )
}

function SubSignalDetail({ title, signal, details, icon }: { title: string; signal: { signal: string; confidence: number }; details?: any; icon: React.ReactNode }) {
  const detailText = details?.narrative || details?.reasoning || ''
  const isSentiment = title === 'Sentiment'
  return (
    <div className="p-3 bg-[var(--bg-secondary)] rounded-lg">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="font-medium text-sm">{title}</span>
        <Badge variant={signal.signal === 'buy' ? 'success' : signal.signal === 'sell' ? 'destructive' : 'secondary'} className="text-xs ml-auto">
          {signal.signal.toUpperCase()}
        </Badge>
        <span className="text-xs text-[var(--text-secondary)]">{signal.confidence}%</span>
      </div>
      {detailText && (
        <p className="text-xs text-[var(--text-muted)] leading-relaxed">{detailText}</p>
      )}
      {isSentiment && details?.article_count !== undefined && (
        <div className="space-y-2 mt-2">
          <div className="flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
            <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-500">{details.positive_count ?? 0} pos</span>
            <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500">{details.negative_count ?? 0} neg</span>
            <span className="px-1.5 py-0.5 rounded bg-gray-500/10 text-gray-400">{details.neutral_count ?? 0} neu</span>
            <span className="text-[var(--text-secondary)]">net {details.net_score >= 0 ? '+' : ''}{details.net_score?.toFixed(2)}</span>
          </div>
          {details.top_articles && details.top_articles.length > 0 && (
            <div className="space-y-1">
              {details.top_articles.slice(0, 3).map((a: any, i: number) => (
                <div key={i} className="text-[11px] text-[var(--text-muted)] leading-snug flex items-start gap-1">
                  <span className={`shrink-0 mt-0.5 ${a.sentiment === 'positive' ? 'text-green-500' : a.sentiment === 'negative' ? 'text-red-500' : 'text-gray-400'}`}>
                    {a.sentiment === 'positive' ? '▲' : a.sentiment === 'negative' ? '▼' : '●'}
                  </span>
                  <span className="line-clamp-2">{a.headline}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
