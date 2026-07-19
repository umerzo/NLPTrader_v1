import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { format, formatDistanceToNow } from 'date-fns'
import { backtestApi, BacktestConfig } from '../api/client'
import { Button, Card, CardContent, CardHeader, CardTitle, Input } from '../components/ui'
import { Play, Loader2, CheckCircle, XCircle, BarChart2, TrendingUp, AlertTriangle } from 'lucide-react'

const TICKERS = ['BTC', 'ETH', 'XAUUSD', 'NVDA']
const TIMEFRAMES = ['15m', '1h', '4h', '1D']
const HORIZONS = [4, 24, 48, 72, 168]

export default function BacktestLab() {
  const queryClient = useQueryClient()
  const [config, setConfig] = useState<BacktestConfig>({
    tickers: ['BTC', 'ETH'],
    start_date: format(new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
    end_date: format(new Date(), 'yyyy-MM-dd'),
    timeframe: '1h',
    horizons: [24, 48],
  })
  const [runningRunId, setRunningRunId] = useState<number | null>(null)

  const { data: runs = [] } = useQuery({
    queryKey: ['backtest-runs'],
    queryFn: () => backtestApi.listRuns(),
  })

  const selectedRunData = runs.find(r => r.id === runningRunId) || runs[0]
  const { data: runResults, isLoading: resultsLoading } = useQuery({
    queryKey: ['backtest-results', runningRunId],
    queryFn: () => backtestApi.getResults(runningRunId!),
    enabled: !!runningRunId,
    refetchInterval: 5000,
  })

  const runMutation = useMutation({
    mutationFn: (cfg: BacktestConfig) => backtestApi.run(cfg),
    onSuccess: (data) => {
      setRunningRunId(data.run_id)
      queryClient.invalidateQueries({ queryKey: ['backtest-runs'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    runMutation.mutate(config)
  }

  const handleTickerToggle = (ticker: string) => {
    setConfig(prev => ({
      ...prev,
      tickers: prev.tickers.includes(ticker)
        ? prev.tickers.filter(t => t !== ticker)
        : [...prev.tickers, ticker],
    }))
  }

  const handleHorizonToggle = (h: number) => {
    setConfig(prev => ({
      ...prev,
      horizons: prev.horizons.includes(h)
        ? prev.horizons.filter(x => x !== h)
        : [...prev.horizons, h],
    }))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Backtest Lab</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">Walk-forward backtesting with zero lookahead bias</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--text-secondary)]">
            {runs.filter(r => r.status === 'running').length} running
          </span>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Config Panel */}
        <div className="lg:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart2 className="w-5 h-5" /> Configuration
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Tickers */}
                <div>
                  <label className="text-sm font-medium text-[var(--text-secondary)] mb-2 block">Tickers</label>
                  <div className="flex flex-wrap gap-2">
                    {TICKERS.map(t => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => handleTickerToggle(t)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          config.tickers.includes(t)
                            ? 'bg-primary-600 text-white'
                            : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)]'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Date Range */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-sm font-medium text-[var(--text-secondary)] mb-1 block">Start Date</label>
                    <Input
                      type="date"
                      value={config.start_date}
                      onChange={e => setConfig({ ...config, start_date: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-[var(--text-secondary)] mb-1 block">End Date</label>
                    <Input
                      type="date"
                      value={config.end_date}
                      onChange={e => setConfig({ ...config, end_date: e.target.value })}
                    />
                  </div>
                </div>

                {/* Timeframe */}
                <div>
                  <label className="text-sm font-medium text-[var(--text-secondary)] mb-1 block">Timeframe</label>
                  <select
                    value={config.timeframe}
                    onChange={e => setConfig({ ...config, timeframe: e.target.value })}
                    className="input w-full"
                  >
                    {TIMEFRAMES.map(tf => (
                      <option key={tf} value={tf}>{tf}</option>
                    ))}
                  </select>
                </div>

                {/* Horizons */}
                <div>
                  <label className="text-sm font-medium text-[var(--text-secondary)] mb-2 block">Prediction Horizons</label>
                  <div className="flex flex-wrap gap-2">
                    {HORIZONS.map(h => (
                      <button
                        key={h}
                        type="button"
                        onClick={() => handleHorizonToggle(h)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          config.horizons.includes(h)
                            ? 'bg-primary-600 text-white'
                            : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)]'
                        }`}
                      >
                        {h}h
                      </button>
                    ))}
                  </div>
                </div>

                {/* Run Button */}
                <Button type="submit" className="w-full" disabled={runMutation.isPending}>
                  {runMutation.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Starting...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" /> Run Backtest
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {/* Runs History */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart2 className="w-5 h-5" /> Runs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {runs.length === 0 ? (
                  <p className="text-[var(--text-secondary)] text-sm text-center py-4">No runs yet</p>
                ) : (
                  runs.map(run => (
                    <RunRow key={run.id} run={run} isSelected={runningRunId === run.id} onClick={() => setRunningRunId(run.id)} />
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Results Panel */}
        <div className="lg:col-span-2 space-y-6">
          {runningRunId && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Run #{runningRunId} Results</span>
                  <span className={`flex items-center gap-1 text-sm ${
                    selectedRunData?.status === 'completed' ? 'text-green-600' :
                    selectedRunData?.status === 'failed' ? 'text-red-600' : 'text-blue-600'
                  }`}>
                    {selectedRunData?.status === 'running' && <Loader2 className="w-4 h-4 animate-spin" />}
                    {selectedRunData?.status === 'completed' && <CheckCircle className="w-4 h-4" />}
                    {selectedRunData?.status === 'failed' && <XCircle className="w-4 h-4" />}
                    {selectedRunData?.status || 'pending'}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {resultsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
                    <span className="ml-3 text-[var(--text-secondary)]">Computing walk-forward backtest...</span>
                  </div>
                ) : runResults?.metrics ? (
                  <BacktestResults metrics={runResults.metrics} />
                ) : (
                  <div className="text-center py-8 text-[var(--text-secondary)]">
                    {selectedRunData?.status === 'failed' ? (
                      <>
                        <AlertTriangle className="w-12 h-12 mx-auto text-red-500 mb-2" />
                        <p>Backtest failed</p>
                      </>
                    ) : (
                      <p>Waiting for results...</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function RunRow({ run, isSelected, onClick }: { run: { id: number; model_version: string; started_at: string; status: string }; isSelected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full p-3 rounded-lg text-left transition-colors ${
        isSelected
          ? 'bg-primary-50 dark:bg-primary-900/20 border border-primary-200 dark:border-primary-800'
          : 'hover:bg-[var(--bg-tertiary)]'
      }`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-sm">Run #{run.id}</p>
          <p className="text-xs text-[var(--text-secondary)]">{run.model_version}</p>
        </div>
        <div className="text-right">
          <p className="text-xs text-[var(--text-secondary)]">{formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}</p>
          <span className={`inline-block px-2 py-0.5 rounded text-xs ${
            run.status === 'completed' ? 'bg-green-100 text-green-700' :
            run.status === 'failed' ? 'bg-red-100 text-red-700' :
            'bg-blue-100 text-blue-700'
          }`}>
            {run.status}
          </span>
        </div>
      </div>
    </button>
  )
}

function BacktestResults({ metrics }: { metrics: any }) {
  if (!metrics) return null

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard title="Total Signals" value={metrics.total_signals} icon={<BarChart2 className="w-5 h-5 text-blue-500" />} />
        <MetricCard title="Accuracy" value={`${metrics.accuracy}%`} icon={<CheckCircle className="w-5 h-5 text-green-500" />} />
        <MetricCard title="Profit Factor" value={metrics.profit_factor.toFixed(2)} icon={<TrendingUp className="w-5 h-5 text-purple-500" />} />
        <MetricCard title="Sharpe Ratio" value={metrics.sharpe_ratio.toFixed(2)} icon={<BarChart2 className="w-5 h-5 text-purple-500" />} />
        <MetricCard title="Max Drawdown" value={`${metrics.max_drawdown}%`} icon={<AlertTriangle className="w-5 h-5 text-red-500" />} />
      </div>

      {/* Calibration */}
      <Card>
        <CardHeader><CardTitle>Confidence Calibration</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border-color)]">
                <th className="text-left pb-2">Confidence Bucket</th>
                <th className="text-right pb-2">Signals</th>
                <th className="text-right pb-2">Actual Accuracy</th>
              </tr>
            </thead>
            <tbody>
              {metrics.calibration.map((c: any) => (
                <tr key={c.conf_bucket} className="border-b border-[var(--border-color)] last:border-0">
                  <td className="py-2">{c.conf_bucket}</td>
                  <td className="py-2 text-right">{c.count}</td>
                  <td className="py-2 text-right font-medium">{c.accuracy}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* By Ticker */}
      <Card>
        <CardHeader><CardTitle>By Ticker</CardTitle></CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border-color)]">
                <th className="text-left pb-2">Ticker</th>
                <th className="text-right pb-2">Signals</th>
                <th className="text-right pb-2">Accuracy</th>
                <th className="text-right pb-2">Avg Return</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.by_ticker).map(([ticker, data]: [string, any]) => (
                <tr key={ticker} className="border-b border-[var(--border-color)] last:border-0">
                  <td className="py-2 font-medium">{ticker}</td>
                  <td className="py-2 text-right">{data.count}</td>
                  <td className="py-2 text-right">{data.accuracy}%</td>
                  <td className="py-2 text-right">{data.avg_return > 0 ? '+' : ''}{data.avg_return.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Equity Curve */}
      <Card>
        <CardHeader><CardTitle>Equity Curve</CardTitle></CardHeader>
        <CardContent>
          <EquityCurveChart data={metrics.equity_curve} />
        </CardContent>
      </Card>
    </div>
  )
}

function MetricCard({ title, value, icon }: { title: string; value: string | number; icon: React.ReactNode }) {
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
      </CardContent>
    </Card>
  )
}

function EquityCurveChart({ data }: { data: Array<{ time: string; equity: number }> }) {
  if (!data || data.length === 0) return <p className="text-center text-[var(--text-secondary)] py-8">No equity data</p>

  const maxEquity = Math.max(...data.map(d => d.equity))
  const minEquity = Math.min(...data.map(d => d.equity))
  const range = maxEquity - minEquity || 1

  // Compute SVG paths outside JSX to avoid parsing issues
  const areaPath = data.map((d, i) => {
    const x = 40 + (i / (data.length - 1)) * 540
    const y = 180 - ((d.equity - minEquity) / range) * 160
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ') + ' L 580 180 L 40 180 Z'

  const linePath = data.map((d, i) => {
    const x = 40 + (i / (data.length - 1)) * 540
    const y = 180 - ((d.equity - minEquity) / range) * 160
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ')

  return (
    <div className="h-64 relative">
      <svg viewBox="0 0 600 200" className="w-full h-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
        </defs>
        {/* Grid */}
        <g stroke="#e2e8f0" strokeWidth="0.5" className="dark:stroke-gray-700">
          {[0, 0.25, 0.5, 0.75, 1].map(y => (
            <line key={y} x1="40" y1={20 + y * 160} x2="580" y2={20 + y * 160} />
          ))}
          {[0, 0.25, 0.5, 0.75, 1].map(x => (
            <line key={x} x1={40 + x * 540} y1="20" x2={40 + x * 540} y2="180" />
          ))}
        </g>
        {/* Area */}
        <path
          d={areaPath}
          fill="url(#equityGradient)"
        />
        {/* Line */}
        <path
          d={linePath}
          stroke="#3b82f6"
          strokeWidth="2"
          fill="none"
        />
      </svg>
      <div className="flex justify-between text-xs text-[var(--text-secondary)] mt-2">
        <span>{format(data[0].time, 'MMM d')}</span>
        <span>{format(data[data.length - 1].time, 'MMM d')}</span>
      </div>
    </div>
  )
}