import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format, formatDistanceToNow } from 'date-fns'
import { signalsApi, Signal } from '../api/client'
import { SignalCard } from '../components/SignalCard'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui'
import { BarChart2, Target, TrendingUp, CheckCircle, XCircle, AlertCircle, Loader2, RefreshCw, Sparkles, TrendingDown, Database } from 'lucide-react'

export default function Dashboard() {
  const queryClient = useQueryClient()

  const { data: activeSignals = [], isLoading: signalsLoading, refetch } = useQuery({
    queryKey: ['signals', 'active'],
    queryFn: () => signalsApi.getActive(),
    refetchInterval: 30000,
  })

  const refreshMutation = useMutation({
    mutationFn: () => signalsApi.refreshAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['signals'] })
      queryClient.invalidateQueries({ queryKey: ['history'] })
      queryClient.invalidateQueries({ queryKey: ['calibration'] })
    },
  })

  const { data: stats } = useQuery({
    queryKey: ['signals', 'stats'],
    queryFn: () => signalsApi.getStats(),
    refetchInterval: 60000,
  })

  const { data: recentHistoryRes } = useQuery({
    queryKey: ['signals', 'history', { limit: 10 }],
    queryFn: () => signalsApi.getHistory({ limit: 10 }),
  })
  const recentHistory = recentHistoryRes?.items ?? []

  const { data: calibrationRes } = useQuery({
    queryKey: ['calibration'],
    queryFn: () => signalsApi.getHistory({ limit: 500 }),
  })
  const calibration = calibrationRes?.items ?? []

  const now = new Date()
  const greeting = now.getHours() < 12 ? 'Good morning' : now.getHours() < 18 ? 'Good afternoon' : 'Good evening'
  const activeBuy = activeSignals.filter(s => s.signal === 'buy').length
  const activeSell = activeSignals.filter(s => s.signal === 'sell').length
  const activeHold = activeSignals.filter(s => s.signal === 'hold').length

  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#1a1d3a] via-[#121425] to-[#0a0b0f] border border-[var(--border-color)] p-6 lg:p-8">
        <div className="absolute top-0 right-0 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-500/5 rounded-full blur-3xl" />
        <div className="relative z-10">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-5 h-5 text-primary-400" />
                <span className="text-xs font-medium text-primary-400 uppercase tracking-wider">Decision Support System</span>
              </div>
              <h1 className="text-3xl lg:text-4xl font-bold text-[var(--text-primary)]">
                {greeting}, Trader
              </h1>
              <p className="text-[var(--text-secondary)] mt-1">{format(now, 'EEEE, MMMM d, yyyy')} · {format(now, 'HH:mm')} UTC</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
                {refreshMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin text-primary-400" />
                ) : (
                  <RefreshCw className={`w-4 h-4 text-[var(--text-secondary)] ${signalsLoading ? 'animate-spin' : ''}`} />
                )}
                <span className="text-xs text-[var(--text-secondary)]">
                  {refreshMutation.isPending ? 'Updating...' : 'Auto-refresh: 30s'}
                </span>
              </div>
              <button
                onClick={() => refreshMutation.mutate()}
                disabled={refreshMutation.isPending}
                className="p-2 rounded-lg bg-primary-600 hover:bg-primary-500 text-white transition-colors disabled:opacity-50"
                aria-label="Refresh all data"
                title="Run full pipeline: ingest news + generate signals"
              >
                {refreshMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Database className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={() => refetch()}
                disabled={signalsLoading}
                className="p-2 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] transition-colors border border-[var(--border-color)]"
                aria-label="Refresh signals"
              >
                <RefreshCw className={`w-4 h-4 ${signalsLoading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
          <div className="flex flex-wrap gap-4 mt-6">
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-500/10 border border-green-500/20">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <span className="text-sm"><span className="font-bold text-green-400">{activeBuy}</span> <span className="text-[var(--text-secondary)]">Buy</span></span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
              <TrendingDown className="w-4 h-4 text-red-400" />
              <span className="text-sm"><span className="font-bold text-red-400">{activeSell}</span> <span className="text-[var(--text-secondary)]">Sell</span></span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <BarChart2 className="w-4 h-4 text-yellow-400" />
              <span className="text-sm"><span className="font-bold text-yellow-400">{activeHold}</span> <span className="text-[var(--text-secondary)]">Hold</span></span>
            </div>
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <Target className="w-4 h-4 text-blue-400" />
              <span className="text-sm"><span className="font-bold text-blue-400">{activeSignals.length}</span> <span className="text-[var(--text-secondary)]">Active Signals</span></span>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Signals"
          value={String(activeSignals.length)}
          icon={<BarChart2 className="w-5 h-5 text-blue-500" />}
          subtitle={`${activeSignals.filter(s => s.signal === 'buy').length} Buy • ${activeSignals.filter(s => s.signal === 'sell').length} Sell`}
        />
        <StatCard
          title="Accuracy (Tracked)"
          value={`${stats?.accuracy ?? 0}%`}
          icon={<Target className="w-5 h-5 text-green-500" />}
          trend={(stats?.accuracy ?? 0) > 55 ? 'positive' : 'negative'}
        />
        <StatCard
          title="Avg Return"
          value={`${stats?.avg_return_pct ?? 0}%`}
          icon={<TrendingUp className="w-5 h-5 text-green-500" />}
          trend={(stats?.avg_return_pct ?? 0) > 0 ? 'positive' : 'negative'}
        />
        <StatCard
          title="Profit Factor"
          value={stats?.profit_factor?.toFixed(2) ?? '0.00'}
          icon={<TrendingUp className="w-5 h-5 text-purple-500" />}
        />
      </div>

      {/* Main Content */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Active Signals */}
        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-[var(--text-primary)]">Active Signals</h2>
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--text-secondary)]">Updated: {format(new Date(), 'HH:mm:ss')}</span>
              {signalsLoading && <Loader2 className="w-5 h-5 animate-spin text-primary-500 ml-2" />}
            </div>
          </div>

          {activeSignals.length === 0 ? (
            <Card className="py-12 text-center">
              <CardContent>
                <AlertCircle className="w-12 h-12 mx-auto text-[var(--text-secondary)] mb-3" />
                <p className="text-[var(--text-secondary)]">No active signals at the moment</p>
                <p className="text-sm text-[var(--text-secondary)] mt-1">New signals will appear here when generated</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3" role="list" aria-label="Active trading signals">
              {activeSignals.map((signal: Signal) => (
                <SignalCard key={signal.id} signal={signal} />
              ))}
            </div>
          )}

          {/* Calibration Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="w-5 h-5" /> Confidence Calibration
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CalibrationSummary calibration={calibration || []} />
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5" /> Performance Snapshot
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <QuickStat label="Signals Today" value={activeSignals.length} />
                <QuickStat label="Tracked Total" value={activeSignals.filter(s => s.outcome).length} />
                <QuickStat label="Avg Confidence" value={`${Math.round(activeSignals.reduce((a, b) => a + b.confidence, 0) / (activeSignals.length || 1))}%`} />
                <QuickStat label="Win Rate" value={`${activeSignals.filter(s => s.outcome?.outcome === 'correct').length}/${activeSignals.filter(s => s.outcome).length || 1}`} />
              </div>

              {/* Regime Distribution */}
              <div>
                <h4 className="text-sm font-medium text-[var(--text-secondary)] mb-2">Market Regime</h4>
                <div className="flex flex-wrap gap-2">
                  {['bull', 'bear', 'high_vol', 'chop', 'crisis'].map(regime => (
                    <span
                      key={regime}
                      className={`px-2 py-1 rounded-full text-xs font-medium ${
                        activeSignals.some(s => s.regime === regime)
                          ? 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-300'
                          : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)]'
                      }`}
                    >
                      {regime}
                    </span>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Calibration Quick View */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Target className="w-5 h-5" /> Confidence Calibration
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CalibrationBars calibration={calibration || []} />
            </CardContent>
          </Card>

          {/* Recent History */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart2 className="w-5 h-5" /> Recent History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <HistoryList signals={recentHistory || []} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

function StatCard({ title, value, icon, subtitle, trend }: { title: string; value: string; icon: React.ReactNode; subtitle?: string; trend?: 'positive' | 'negative' }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-[var(--text-secondary)]">{title}</p>
            <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{value}</p>
            {subtitle && <p className="text-xs text-[var(--text-secondary)] mt-1">{subtitle}</p>}
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

function QuickStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-3 bg-[var(--bg-tertiary)] rounded-lg">
      <p className="text-xs text-[var(--text-secondary)]">{label}</p>
      <p className="text-xl font-bold text-[var(--text-primary)] mt-1">{value}</p>
    </div>
  )
}

function CalibrationSummary({ calibration }: { calibration: Signal[] }) {
  const buckets = ['0-30', '30-50', '50-70', '70-85', '85-100']
  const data = buckets.map(bucket => {
    const [min, max] = bucket.split('-').map(Number)
    const bucketSignals = calibration.filter(s =>
      s.confidence >= min && s.confidence <= max &&
      s.outcome && (s.outcome.outcome === 'correct' || s.outcome.outcome === 'incorrect')
    )
    const correct = bucketSignals.filter(s => s.outcome?.outcome === 'correct').length
    const total = bucketSignals.length
    const accuracy = total > 0 ? Math.round(correct / total * 100) : 0
    return { bucket, count: total, accuracy, expected: (min + max) / 2 }
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

function CalibrationBars({ calibration }: { calibration: Signal[] }) {
  const buckets = ['0-30', '30-50', '50-70', '70-85', '85-100']
  const data = buckets.map(bucket => {
    const [min, max] = bucket.split('-').map(Number)
    const bucketSignals = calibration.filter(s =>
      s.confidence >= min && s.confidence <= max &&
      s.outcome && (s.outcome.outcome === 'correct' || s.outcome.outcome === 'incorrect')
    )
    const correct = bucketSignals.filter(s => s.outcome?.outcome === 'correct').length
    const total = bucketSignals.length
    const accuracy = total > 0 ? Math.round(correct / total * 100) : 0
    return { bucket, count: total, accuracy, expected: (min + max) / 2 }
  }).filter(d => d.count > 0)

  return (
    <div className="space-y-3">
      {data.map(d => {
        const [min, max] = d.bucket.split('-').map(Number)
        return (
          <div key={d.bucket} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-[var(--text-secondary)]">{d.bucket}%</span>
              <span className="font-medium">{d.count} signals</span>
            </div>
            <div className="h-2 bg-[var(--border-color)] rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-500 rounded-full transition-all duration-300"
                style={{ width: `${Math.min(100, (d.accuracy / 100) * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-[var(--text-secondary)]">
              <span>Expected: {Math.round((min + max) / 2)}%</span>
              <span className={d.accuracy >= (min + max) / 2 - 5 && d.accuracy <= (min + max) / 2 + 5 ? 'text-green-600' : 'text-red-600'}>
                Actual: {d.accuracy}%
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function HistoryList({ signals }: { signals: Signal[] }) {
  const recent = signals.slice(0, 10)
  return (
    <div className="space-y-2">
      {recent.map(s => (
        <div key={s.id} className="flex items-center justify-between py-2 border-b border-[var(--border-color)] last:border-0">
          <div className="flex items-center gap-3">
            <span className="text-[var(--text-secondary)] text-sm">{formatDistanceToNow(new Date(s.generated_at), { addSuffix: true })}</span>
            <span className="font-mono text-[var(--text-primary)] font-medium">{s.ticker}</span>
            <span className={`px-2 py-0.5 rounded text-xs ${
              s.signal === 'buy' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
              s.signal === 'sell' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
              'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
            }`}>
              {s.signal.toUpperCase()}
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[var(--text-secondary)]">{s.confidence}%</span>
            {s.outcome && (
              <span className={`px-1.5 py-0.5 rounded text-xs ${
                s.outcome.outcome === 'correct' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                s.outcome.outcome === 'incorrect' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
              }`}>
                {s.outcome.outcome}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}