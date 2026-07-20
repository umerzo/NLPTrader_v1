import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
})

// Log all requests and errors for debugging
api.interceptors.request.use((config) => {
  console.log('[API Request]', config.method?.toUpperCase(), config.url)
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error.config?.url, error.message, error.response?.data)
    return Promise.reject(error)
  }
)

export interface SubSignal {
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  details?: {
    reasoning?: string
    levels?: Record<string, number | null>
    indicators?: Record<string, any>
    article_count?: number
    net_score?: number
    positive_count?: number
    negative_count?: number
    narrative?: string
    key_themes?: string[]
    risks?: string[]
    catalyst?: string | null
  }
}

export interface SignalOutcome {
  outcome: 'correct' | 'incorrect' | 'pending'
  price_change_pct: number | null
  max_fav: number | null
  max_adv: number | null
  hit_sl: boolean
  hit_tp1: boolean
  checked_at: string
}

export interface Signal {
  id: number
  ticker: string
  signal: 'buy' | 'sell' | 'hold'
  confidence: number
  reasoning: string
  entry: number | null
  sl: number | null
  tp1: number | null
  tp2: number | null
  tp3: number | null
  horizon: string
  regime: string
  model_version: string
  generated_at: string
  expires_at: string | null
  sub_signals: {
    ta: SubSignal
    sentiment: SubSignal
    fundamental: SubSignal
  }
  outcome?: SignalOutcome | null
  status?: string
  price_change_pct?: number | null
  exit_price?: number | null
}

export interface SignalStats {
  total_signals: number
  accuracy: number
  avg_return_pct: number
  profit_factor?: number
}

export interface BacktestConfig {
  tickers: string[]
  start_date: string
  end_date: string
  timeframe: string
  horizons: number[]
  model_version?: string
}

export interface BacktestRun {
  id: number
  model_version: string
  started_at: string
  completed_at: string | null
  status: 'running' | 'completed' | 'failed'
  config: BacktestConfig
}

export interface BacktestMetrics {
  total_signals: number
  accuracy: number
  profit_factor: number
  sharpe_ratio: number
  max_drawdown: number
  calibration: Array<{
    conf_bucket: string
    count: number
    accuracy: number
    avg_return: number
  }>
  by_ticker: Record<string, {
    count: number
    accuracy: number
    avg_return: number
  }>
  by_horizon: Record<number, {
    count: number
    accuracy: number
    avg_return: number
  }>
  by_signal_type: Record<string, {
    count: number
    accuracy: number
    avg_return: number
  }>
  equity_curve: Array<{
    time: string
    equity: number
  }>
}

export interface BacktestResultsResponse {
  id: number
  model_version: string
  started_at: string
  completed_at: string | null
  status: string
  config: BacktestConfig
  metrics: BacktestMetrics | null
}

export interface HealthCheck {
  status: string
  service: string
}

export interface FullHealthCheck {
  status: string
  checks: Record<string, string>
}

export interface PaginatedSignals {
  items: Signal[]
  total: number
}

const PREFIX = '/api'

export const signalsApi = {
  getActive: (ticker?: string) => api.get<Signal[]>(`${PREFIX}/signals/active`, { params: { ticker } }).then(r => r.data),
  getHistory: (params: { ticker?: string; limit?: number; offset?: number } = {}) => api.get<PaginatedSignals>(`${PREFIX}/signals/history`, { params }).then(r => r.data),
  getStats: (ticker?: string) => api.get<SignalStats>(`${PREFIX}/outcomes/summary`, { params: { ticker } }).then(r => r.data),
  generate: (ticker: string) => api.post<Signal>(`${PREFIX}/signals/generate/${ticker}`).then(r => r.data),
  refreshAll: () => api.post<{ status: string; ingestion: any; signals_generated: string[] }>(`${PREFIX}/signals/refresh`).then(r => r.data),
}

export const backtestApi = {
  run: (config: BacktestConfig) => api.post<{ run_id: number; status: string; message: string }>(`${PREFIX}/backtest/run`, config).then(r => r.data),
  listRuns: () => api.get<BacktestRun[]>(`${PREFIX}/backtest/runs`).then(r => r.data),
  getResults: (runId: number) => api.get<BacktestResultsResponse>(`${PREFIX}/backtest/${runId}`).then(r => r.data),
  getJobStatus: (runId: number) => api.get<{ status: string; progress?: number; result?: BacktestMetrics; error?: string }>(`${PREFIX}/backtest/jobs/${runId}/status`).then(r => r.data),
}

export interface NewsArticle {
  id: number
  ticker: string
  source: string
  headline: string
  summary: string | null
  author: string | null
  published_at: string
  sentiment: string | null
  sentiment_score: number | null
  url: string
  llm_analysis?: {
    label: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    confidence: number
    reasoning: string
  } | null
}

export interface LLMAnalysisResult {
  id: number
  headline: string
  llm_analysis?: { label: string; confidence: number; reasoning: string }
  error?: string
}

export interface PaginatedNews {
  items: NewsArticle[]
  total: number
}

export interface TAAnalysis {
  ticker: string
  timeframe: string
  current_price: number
  signal: string
  confidence: number
  reasoning: string
  regime: string
  regime_multiplier: number
  indicators: {
    rsi_14: number | null
    rsi_7: number | null
    macd: number | null
    macd_signal: number | null
    macd_histogram: number | null
    sma_20: number | null
    sma_50: number | null
    ema_12: number | null
    ema_26: number | null
    bb_upper: number | null
    bb_middle: number | null
    bb_lower: number | null
    atr_14: number | null
    volume_sma_20: number | null
    current_volume: number | null
  }
  support_levels: number[]
  resistance_levels: number[]
  fibonacci: {
    levels: number[]
    swing_high: number
    swing_low: number
  }
  trade_setup: {
    direction: string
    entry: number
    stop_loss: number
    take_profit_1: number
    take_profit_2: number
    take_profit_3: number
    rr_ratio: number
  } | null
  levels: {
    entry: number | null
    sl: number | null
    tp1: number | null
    tp2: number | null
    tp3: number | null
  }
  price_data: Array<{
    time: string
    open: number
    high: number
    low: number
    close: number
    volume: number
  }>
  narrative_context: string
}

export const newsApi = {
  getArticles: (params: { ticker?: string; limit?: number; offset?: number } = {}) =>
    api.get<PaginatedNews>(`${PREFIX}/news/articles`, { params }).then(r => r.data),
  analyzeSentiment: (limit?: number) =>
    api.post<{ analyzed: number; results: LLMAnalysisResult[] }>(`${PREFIX}/news/analyze-sentiment`, null, { params: { limit } }).then(r => r.data),
}

export type TickerSearchResult =
  | {
      found: true
      ticker: string
      name: string | null
      exchange: string | null
      sector: string | null
      industry: string | null
      asset_type: string | null
      current_price: number | null
      currency: string | null
    }
  | {
      found: false
      query: string
      message: string
    }

export const tickersApi = {
  search: (q: string) =>
    api.get<TickerSearchResult>(`${PREFIX}/tickers/search`, { params: { q } }).then(r => r.data),
  track: (ticker: string) =>
    api.post<{ status: string }>(`${PREFIX}/tickers/${ticker}/track`).then(r => r.data),
}

export const taApi = {
  analyze: (ticker: string, timeframe: string = '1h') =>
    api.get<TAAnalysis>(`${PREFIX}/ta/${ticker}`, { params: { timeframe } }).then(r => r.data),
}

export const healthApi = {
  full: () => api.get<FullHealthCheck>(`${PREFIX}/health/full`).then(r => r.data),
  db: () => api.get<HealthCheck>(`${PREFIX}/health/db`).then(r => r.data),
  llm: () => api.get<HealthCheck>(`${PREFIX}/health/llm`).then(r => r.data),
  chromadb: () => api.get<HealthCheck>(`${PREFIX}/health/chromadb`).then(r => r.data),
}

export default api