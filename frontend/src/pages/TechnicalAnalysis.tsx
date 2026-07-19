import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { taApi, TAAnalysis } from '../api/client'
import TradingViewChart from '../components/TradingViewChart'
import { Card, CardContent, CardHeader, CardTitle, Button } from '../components/ui'
import { Loader2, TrendingUp, AlertTriangle, Activity, BarChart3, Zap, Target } from 'lucide-react'

const TICKERS = ['BTC', 'ETH', 'XAUUSD', 'NVDA']
const TIMEFRAMES = ['15m', '1h', '4h', '1d']

export default function TechnicalAnalysis() {
  const [ticker, setTicker] = useState('BTC')
  const [timeframe, setTimeframe] = useState('1h')
  const [shouldAnalyze, setShouldAnalyze] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['ta-analysis', ticker, timeframe],
    queryFn: () => taApi.analyze(ticker, timeframe),
    enabled: shouldAnalyze,
  })

  const handleAnalyze = () => setShouldAnalyze(true)

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Technical Analysis</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">Advanced charting with real-time TA engine</p>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[var(--text-secondary)]">Ticker</label>
              <div className="flex gap-2">
                {TICKERS.map((t) => (
                  <button
                    key={t}
                    onClick={() => { setTicker(t); setShouldAnalyze(false) }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      ticker === t
                        ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/25'
                        : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)]'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[var(--text-secondary)]">Timeframe</label>
              <div className="flex gap-2">
                {TIMEFRAMES.map((tf) => (
                  <button
                    key={tf}
                    onClick={() => { setTimeframe(tf); setShouldAnalyze(false) }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      timeframe === tf
                        ? 'bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-primary-500/50'
                        : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)]'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
            </div>
            <Button
              onClick={handleAnalyze}
              disabled={isLoading}
              className="px-8"
              size="lg"
            >
              {isLoading ? (
                <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Analyzing...</>
              ) : (
                <><Zap className="w-5 h-5 mr-2" /> Run Analysis</>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {!shouldAnalyze && !isLoading && (
        <Card className="py-16">
          <CardContent className="text-center">
            <Activity className="w-16 h-16 mx-auto text-[var(--text-secondary)] mb-4 opacity-50" />
            <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">Ready to Analyze</h2>
            <p className="text-[var(--text-secondary)]">Select a ticker and timeframe, then click <strong>Run Analysis</strong></p>
          </CardContent>
        </Card>
      )}

      {isLoading && (
        <Card className="py-16">
          <CardContent className="text-center">
            <Loader2 className="w-12 h-12 mx-auto animate-spin text-primary-500 mb-4" />
            <p className="text-[var(--text-secondary)]">Running technical analysis on {ticker} ({timeframe})...</p>
            <p className="text-xs text-[var(--text-secondary)] mt-2">Computing indicators, S&R levels, Fibonacci, and trade setup</p>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card>
          <CardContent className="p-6 text-center">
            <AlertTriangle className="w-12 h-12 mx-auto text-red-500 mb-3" />
            <p className="text-red-500 font-medium">Analysis Failed</p>
            <p className="text-sm text-[var(--text-secondary)] mt-1">{(error as any)?.message || 'Could not complete analysis'}</p>
          </CardContent>
        </Card>
      )}

      {data && !isLoading && (
        <>
          {/* Chart */}
          <Card className="overflow-hidden">
            <CardHeader className="pb-0">
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5" />
                  {data.ticker} · {data.timeframe.toUpperCase()} · ${data.current_price.toLocaleString()}
                </CardTitle>
                <SignalBadge signal={data.signal} confidence={data.confidence} />
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <TradingViewChart
                data={data.price_data}
                overlays={{
                  support_levels: data.support_levels,
                  resistance_levels: data.resistance_levels,
                  entry: data.levels.entry,
                  sl: data.levels.sl,
                  tp1: data.levels.tp1,
                  tp2: data.levels.tp2,
                  tp3: data.levels.tp3,
                }}
                height={520}
              />
            </CardContent>
          </Card>

          {/* Analysis Brief + Signal Card row */}
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Analysis Brief */}
            <div className="lg:col-span-2 space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5" /> Analysis Brief
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="p-4 rounded-lg bg-gradient-to-br from-[var(--bg-tertiary)] to-[var(--bg-secondary)] border border-[var(--border-color)]">
                    <p className="text-sm text-[var(--text-primary)] leading-relaxed">
                      <span className="font-semibold text-primary-500">Signal: {data.signal.toUpperCase()}</span>
                      {' — '}
                      {data.reasoning}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <IndicatorBadge label="RSI (14)" value={data.indicators.rsi_14} />
                      <IndicatorBadge label="MACD" value={data.indicators.macd} />
                      <IndicatorBadge label="SMA 20/50" value={data.indicators.sma_20 !== null && data.indicators.sma_50 !== null ? `${data.indicators.sma_20?.toFixed(0)} / ${data.indicators.sma_50?.toFixed(0)}` : '—'} />
                      <IndicatorBadge label="ATR (14)" value={data.indicators.atr_14} />
                      <IndicatorBadge label="Volume" value={data.indicators.current_volume !== null && data.indicators.volume_sma_20 !== null ? `${(data.indicators.current_volume / data.indicators.volume_sma_20).toFixed(1)}x avg` : '—'} />
                    </div>
                    <div className="mt-3 text-xs text-[var(--text-muted)]">
                      Regime: <span className="font-medium text-[var(--text-secondary)]">{data.regime}</span>
                      {' · '}Confidence multiplier: <span className="font-medium text-[var(--text-secondary)]">{data.regime_multiplier}x</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Indicator Details */}
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                <IndicatorCard title="RSI (14)" value={data.indicators.rsi_14} threshold={[30, 70]} />
                <IndicatorCard title="RSI (7)" value={data.indicators.rsi_7} threshold={[30, 70]} />
                <IndicatorCard title="MACD" value={data.indicators.macd} />
                <IndicatorCard title="SMA 20" value={data.indicators.sma_20} />
                <IndicatorCard title="SMA 50" value={data.indicators.sma_50} />
                <IndicatorCard title="ATR (14)" value={data.indicators.atr_14} />
                <IndicatorCard title="BB Upper" value={data.indicators.bb_upper} />
                <IndicatorCard title="BB Middle" value={data.indicators.bb_middle} />
                <IndicatorCard title="BB Lower" value={data.indicators.bb_lower} />
                <IndicatorCard title="EMA 12" value={data.indicators.ema_12} />
                <IndicatorCard title="EMA 26" value={data.indicators.ema_26} />
                <IndicatorCard title="Vol ratio" value={data.indicators.current_volume !== null && data.indicators.volume_sma_20 !== null ? parseFloat((data.indicators.current_volume / data.indicators.volume_sma_20).toFixed(1)) : null} />
              </div>
            </div>

            {/* Signal Card Sidebar */}
            <div className="space-y-6">
              {/* Signal Summary */}
              <SignalDetailCard data={data} />

              {/* S&R Levels */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Target className="w-4 h-4" /> Key Levels
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <p className="text-xs font-medium text-[var(--text-secondary)] mb-1.5">Resistance</p>
                    <div className="space-y-1">
                      {data.resistance_levels.slice(0, 3).map((level, i) => (
                        <div key={i} className="flex items-center justify-between px-3 py-1.5 rounded bg-red-500/10 text-sm">
                          <span className="text-red-400">R{data.resistance_levels.length - i}</span>
                          <span className="font-mono text-[var(--text-primary)]">${level.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-[var(--text-secondary)] mb-1.5">Support</p>
                    <div className="space-y-1">
                      {data.support_levels.slice(0, 3).map((level, i) => (
                        <div key={i} className="flex items-center justify-between px-3 py-1.5 rounded bg-green-500/10 text-sm">
                          <span className="text-green-400">S{i + 1}</span>
                          <span className="font-mono text-[var(--text-primary)]">${level.toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Fibonacci */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Activity className="w-4 h-4" /> Fibonacci
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {data.fibonacci.levels.map((level, i) => {
                      const pcts = ['0%', '23.6%', '38.2%', '50%', '61.8%', '78.6%', '100%']
                      return (
                        <div key={i} className="flex items-center justify-between px-3 py-1 rounded text-xs">
                          <span className="text-[var(--text-muted)]">{pcts[i]}</span>
                          <span className="font-mono text-[var(--text-secondary)]">${level.toLocaleString()}</span>
                        </div>
                      )
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function SignalBadge({ signal, confidence }: { signal: string; confidence: number }) {
  const colors: Record<string, string> = {
    buy: 'bg-green-500/20 text-green-400 border-green-500/30',
    sell: 'bg-red-500/20 text-red-400 border-red-500/30',
    hold: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  }
  return (
    <div className={`px-4 py-2 rounded-lg border ${colors[signal] || colors.hold} flex items-center gap-3`}>
      <span className="text-lg font-bold">{signal.toUpperCase()}</span>
      <span className="text-2xl font-bold">{confidence}%</span>
    </div>
  )
}

function IndicatorBadge({ label, value }: { label: string; value: number | string | null }) {
  if (value === null || value === undefined) return null
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-color)] text-xs font-medium">
      <span className="text-[var(--text-muted)]">{label}:</span>
      <span className="text-[var(--text-primary)]">{typeof value === 'number' ? value.toFixed(2) : value}</span>
    </span>
  )
}

function IndicatorCard({ title, value, threshold }: { title: string; value: number | null; threshold?: [number, number] }) {
  let color = 'text-[var(--text-secondary)]'
  if (value !== null && threshold) {
    if (value <= threshold[0]) color = 'text-red-400'
    else if (value >= threshold[1]) color = 'text-red-400'
    else if (value > threshold[0] + 10 && value < threshold[1] - 10) color = 'text-green-400'
    else color = 'text-yellow-400'
  } else if (value !== null) {
    if (value > 0) color = 'text-green-400'
    else if (value < 0) color = 'text-red-400'
    else color = 'text-[var(--text-secondary)]'
  }

  return (
    <Card>
      <CardContent className="p-3">
        <p className="text-xs text-[var(--text-muted)]">{title}</p>
        <p className={`text-lg font-bold font-mono mt-0.5 ${value !== null ? color : 'text-[var(--text-muted)]'}`}>
          {value !== null ? (typeof value === 'number' ? value.toFixed(2) : value) : '—'}
        </p>
      </CardContent>
    </Card>
  )
}

function SignalDetailCard({ data }: { data: TAAnalysis }) {
  const trade = data.trade_setup
  const hasTrade = trade !== null

  return (
    <Card className={`border-2 ${data.signal === 'buy' ? 'border-green-500/30' : data.signal === 'sell' ? 'border-red-500/30' : 'border-yellow-500/30'}`}>
      <CardHeader className={`${data.signal === 'buy' ? 'bg-green-500/5' : data.signal === 'sell' ? 'bg-red-500/5' : 'bg-yellow-500/5'}`}>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Target className="w-4 h-4" /> Signal Details
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-4">
        {hasTrade ? (
          <>
            <div className="text-center">
              <div className={`text-3xl font-bold mb-1 ${
                trade.direction === 'buy' ? 'text-green-400' : 'text-red-400'
              }`}>
                {trade.direction === 'buy' ? '▲ LONG' : '▼ SHORT'}
              </div>
              <div className="text-sm text-[var(--text-secondary)]">
                Confidence: <span className="font-bold text-[var(--text-primary)]">{data.confidence}%</span>
              </div>
            </div>

            <div className="space-y-2">
              <LevelRow label="Entry" value={trade.entry} color="yellow" />
              <LevelRow label="Stop Loss" value={trade.stop_loss} color="red" />
              <LevelRow label="Take Profit 1" value={trade.take_profit_1} color="green" />
              {trade.take_profit_2 && <LevelRow label="Take Profit 2" value={trade.take_profit_2} color="green" />}
              {trade.take_profit_3 && <LevelRow label="Take Profit 3" value={trade.take_profit_3} color="green" />}
            </div>

            <div className="flex items-center justify-center gap-2 pt-2">
              <span className="text-sm text-[var(--text-secondary)]">Risk:Reward</span>
              <span className="text-lg font-bold text-[var(--text-primary)]">1:{trade.rr_ratio}</span>
            </div>
          </>
        ) : (
          <div className="text-center py-6">
            <AlertTriangle className="w-10 h-10 mx-auto text-yellow-500 mb-3" />
            <p className="text-[var(--text-secondary)] font-medium">No Feasible Signal</p>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Current market conditions do not present a clear entry opportunity.
              RSI and price position relative to S&R levels do not align for a high-confidence trade.
            </p>
            <div className="mt-4 flex flex-wrap gap-2 justify-center">
              <span className="px-2 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                RSI: {data.indicators.rsi_14 ?? '—'}
              </span>
              <span className="px-2 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                Regime: {data.regime}
              </span>
              <span className="px-2 py-1 rounded text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                Confidence: {data.confidence}%
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function LevelRow({ label, value, color }: { label: string; value: number; color: 'green' | 'red' | 'yellow' }) {
  const colors = {
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
  }
  return (
    <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-[var(--bg-tertiary)]">
      <span className="text-xs text-[var(--text-secondary)]">{label}</span>
      <span className={`font-mono font-bold ${colors[color]}`}>${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
    </div>
  )
}
