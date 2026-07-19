import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { signalsApi, Signal } from '../api/client'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui'
import { BarChart2, TrendingUp, Target, CheckCircle, XCircle } from 'lucide-react'

export default function Analytics() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: () => signalsApi.getStats(),
  })

  const { data: calibrationRes } = useQuery({
    queryKey: ['calibration'],
    queryFn: () => signalsApi.getHistory({ limit: 500 }),
  })
  const calibration = calibrationRes?.items ?? []

  if (isLoading) return <div className="flex items-center justify-center h-64">Loading...</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Analytics</h1>
        <p className="text-[var(--text-secondary)] text-sm mt-1">Performance analytics and calibration</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard title="Overall Accuracy" value={`${stats?.accuracy ?? 0}%`} icon={<Target className="w-5 h-5 text-blue-500" />} trend={(stats?.accuracy ?? 0) > 55 ? 'positive' : 'negative'} />
        <MetricCard title="Avg Return" value={`${stats?.avg_return_pct ?? 0}%`} icon={<TrendingUp className="w-5 h-5 text-green-500" />} trend={(stats?.avg_return_pct ?? 0) > 0 ? 'positive' : 'negative'} />
        <MetricCard title="Profit Factor" value={stats?.profit_factor?.toFixed(2) ?? '0.00'} icon={<BarChart2 className="w-5 h-5 text-purple-500" />} />
        <MetricCard title="Signals Tracked" value={String(stats?.total_signals ?? 0)} icon={<BarChart2 className="w-5 h-5 text-gray-500" />} />
      </div>

      {/* Calibration Curve */}
      <div className="grid lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" /> Confidence Calibration
            </CardTitle>
          </CardHeader>
          <CardContent>
            <CalibrationChart signals={calibration} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5" /> Signal Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SignalDistributionChart signals={calibration} />
          </CardContent>
        </Card>
      </div>

      {/* Recent Signals Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart2 className="w-5 h-5" /> Recent Signals
          </CardTitle>
        </CardHeader>
        <CardContent>
          <SignalsTable signals={calibration} />
        </CardContent>
      </Card>
    </div>
  )
}

function MetricCard({ title, value, icon, trend }: { title: string; value: string; icon: React.ReactNode; trend?: 'positive' | 'negative' }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-[var(--text-secondary)]">{title}</p>
            <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{value}</p>
          </div>
          <div className="p-2 bg-[var(--bg-tertiary)] rounded-lg">{icon}</div>
        </div>
        {trend && (
          <div className="mt-2 flex items-center gap-1">
            {trend === 'positive' ? (
              <span className="text-xs text-green-600 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Above threshold
              </span>
            ) : (
              <span className="text-xs text-red-600 flex items-center gap-1">
                <XCircle className="w-3 h-3" /> Below threshold
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function CalibrationChart({ signals }: { signals: Signal[] }) {
  const buckets = ['0-30', '30-50', '50-70', '70-85', '85-100']
  const data = buckets.map(bucket => {
    const [min, max] = bucket.split('-').map(Number)
    const bucketSignals = signals.filter(s =>
      s.confidence >= min && s.confidence <= max &&
      s.outcome && (s.outcome.outcome === 'correct' || s.outcome.outcome === 'incorrect')
    )
    const correct = bucketSignals.filter(s => s.outcome?.outcome === 'correct').length
    const total = bucketSignals.length
    const accuracy = total > 0 ? Math.round(correct / total * 100) : 0
    const expected = (min + max) / 2
    return { bucket, count: total, accuracy, expected }
  }).filter(d => d.count > 0)

  return (
    <div className="space-y-3">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-color)]">
            <th className="text-left pb-2">Confidence Range</th>
            <th className="text-right pb-2">Signals</th>
            <th className="text-right pb-2">Expected</th>
            <th className="text-right pb-2">Actual</th>
            <th className="text-right pb-2">Gap</th>
          </tr>
        </thead>
        <tbody>
          {data.map(d => (
            <tr key={d.bucket} className="border-b border-[var(--border-color)] last:border-0">
              <td className="py-2">{d.bucket}%</td>
              <td className="py-2 text-right">{d.count}</td>
              <td className="py-2 text-right">{d.expected}%</td>
              <td className="py-2 text-right font-medium">{d.accuracy}%</td>
              <td className="py-2 text-right">
                <span className={d.accuracy >= d.expected - 5 && d.accuracy <= d.expected + 5 ? 'text-green-600' : 'text-red-600'}>
                  {d.accuracy - d.expected >= 0 ? '+' : ''}{d.accuracy - d.expected}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SignalDistributionChart({ signals }: { signals: Signal[] }) {
  const buy = signals.filter(s => s.signal === 'buy').length
  const sell = signals.filter(s => s.signal === 'sell').length
  const hold = signals.filter(s => s.signal === 'hold').length
  const total = signals.length || 1

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-32">BUY</div>
        <div className="flex-1 h-8 bg-green-100 rounded overflow-hidden">
          <div className="h-full bg-green-600" style={{ width: `${(buy/total)*100}%` }} />
        </div>
        <span className="w-16 text-right">{buy} ({(buy/total*100).toFixed(1)}%)</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="w-32">SELL</div>
        <div className="flex-1 h-8 bg-red-100 rounded overflow-hidden">
          <div className="h-full bg-red-600" style={{ width: `${(sell/total)*100}%` }} />
        </div>
        <span className="w-16 text-right">{sell} ({(sell/total*100).toFixed(1)}%)</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="w-32">HOLD</div>
        <div className="flex-1 h-8 bg-gray-100 rounded overflow-hidden">
          <div className="h-full bg-gray-600" style={{ width: `${(hold/total)*100}%` }} />
        </div>
        <span className="w-16 text-right">{hold} ({(hold/total*100).toFixed(1)}%)</span>
      </div>
    </div>
  )
}

function SignalsTable({ signals }: { signals: Signal[] }) {
  const recent = signals.slice(0, 20)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-color)]">
            <th className="text-left pb-2">Time</th>
            <th className="text-left pb-2">Ticker</th>
            <th className="text-left pb-2">Signal</th>
            <th className="text-right pb-2">Conf</th>
            <th className="text-right pb-2">Entry</th>
            <th className="text-right pb-2">P&L</th>
            <th className="text-left pb-2">Outcome</th>
          </tr>
        </thead>
        <tbody>
          {recent.map(s => (
            <tr key={s.id} className="border-b border-[var(--border-color)] last:border-0">
              <td className="py-2 text-[var(--text-secondary)]">{formatDistanceToNow(new Date(s.generated_at), { addSuffix: true })}</td>
              <td className="py-2 font-mono text-[var(--text-primary)]">{s.ticker}</td>
              <td className="py-2">
                <span className={`inline-flex px-2 py-0.5 rounded text-xs ${
                  s.signal === 'buy' ? 'bg-green-100 text-green-700' :
                  s.signal === 'sell' ? 'bg-red-100 text-red-700' :
                  'bg-gray-100 text-gray-700'
                }`}>
                  {s.signal.toUpperCase()}
                </span>
              </td>
              <td className="py-2 text-right">{s.confidence}%</td>
              <td className="py-2 text-right font-mono">{s.entry ? s.entry.toLocaleString() : '—'}</td>
              <td className="py-2 text-right font-mono">
                {s.outcome?.price_change_pct !== undefined && s.outcome.price_change_pct !== null ? (
                  <span className={s.outcome.price_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {s.outcome.price_change_pct >= 0 ? '+' : ''}{s.outcome.price_change_pct.toFixed(2)}%
                  </span>
                ) : '—'}
              </td>
              <td className="py-2">
                {s.outcome ? (
                  <span className={`inline-flex px-1.5 py-0.5 rounded text-xs ${
                    s.outcome.outcome === 'correct' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                    s.outcome.outcome === 'incorrect' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                    'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                  }`}>
                    {s.outcome.outcome}
                  </span>
                ) : (
                  <span className="text-[var(--text-secondary)] text-xs">Pending</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}