import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { signalsApi, Signal } from '../api/client'
import { Badge, Button, Input } from '../components/ui'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui'
import { ChevronLeft, ChevronRight } from 'lucide-react'

const signalColors = {
  buy: 'buy',
  sell: 'sell',
  hold: 'hold',
}

const outcomeColors = {
  correct: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  incorrect: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  neutral: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
  pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
}

export default function History() {
  const [page, setPage] = useState(0)
  const [pageSize] = useState(25)
  const [tickerFilter, setTickerFilter] = useState('')
  const [signalFilter, setSignalFilter] = useState('')
  const [outcomeFilter, setOutcomeFilter] = useState('')

  const { data: result = { items: [], total: 0 }, isLoading } = useQuery({
    queryKey: ['history', page, pageSize, tickerFilter, signalFilter, outcomeFilter],
    queryFn: () => signalsApi.getHistory({
      ticker: tickerFilter || undefined,
      limit: pageSize,
      offset: page * pageSize,
    }),
  })

  const { items, total } = result
  const totalPages = Math.ceil(total / pageSize)

  // Client-side filtering since API doesn't support signal/outcome filters
  const filteredItems = items.filter((signal: Signal) => {
    if (signalFilter && signal.signal !== signalFilter) return false
    if (outcomeFilter) {
      if (!signal.outcome) return outcomeFilter === 'pending'
      if (signal.outcome.outcome !== outcomeFilter) return false
    }
    return true
  })

  if (isLoading) return <div className="flex items-center justify-center h-64">Loading...</div>

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Signal History</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">Audit trail with outcomes</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Filter ticker (e.g., BTC)"
            value={tickerFilter}
            onChange={(e) => { setTickerFilter(e.target.value); setPage(0); }}
            className="w-48"
          />
          <Select value={signalFilter} onValueChange={(v: string) => { setSignalFilter(v); setPage(0); }}>
            <SelectTrigger className="w-auto">
              <SelectValue placeholder="All Signals" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Signals</SelectItem>
              <SelectItem value="buy">Buy</SelectItem>
              <SelectItem value="sell">Sell</SelectItem>
              <SelectItem value="hold">Hold</SelectItem>
            </SelectContent>
          </Select>
          <Select value={outcomeFilter} onValueChange={(v: string) => { setOutcomeFilter(v); setPage(0); }}>
            <SelectTrigger className="w-auto">
              <SelectValue placeholder="All Outcomes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Outcomes</SelectItem>
              <SelectItem value="correct">Correct</SelectItem>
              <SelectItem value="incorrect">Incorrect</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-tertiary)] border-b border-[var(--border-color)]">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Time</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Ticker</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Signal</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Conf</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Entry</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Exit</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">P&L</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Outcome</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Regime</th>
                <th className="px-4 py-3 text-left font-medium text-[var(--text-secondary)]">Model</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]">
              {filteredItems.map((signal: Signal) => (
                <tr key={signal.id} className="hover:bg-[var(--bg-tertiary)]">
                  <td className="px-4 py-3 text-[var(--text-secondary)]">
                    {formatDistanceToNow(new Date(signal.generated_at), { addSuffix: true })}
                  </td>
                  <td className="px-4 py-3 font-mono font-medium text-[var(--text-primary)]">{signal.ticker}</td>
                  <td className="px-4 py-3">
                    <Badge className={signalColors[signal.signal as keyof typeof signalColors] || 'hold'}>
                      {signal.signal.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-[var(--text-primary)]">{signal.confidence}%</td>
                  <td className="px-4 py-3 font-mono text-[var(--text-secondary)]">
                    {signal.entry ? signal.entry.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 font-mono text-[var(--text-secondary)]">
                    {signal.tp1 ? signal.tp1.toLocaleString() : '—'}
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {signal.outcome?.price_change_pct !== undefined && signal.outcome.price_change_pct !== null ? (
                      <span className={signal.outcome.price_change_pct >= 0 ? 'text-green-600' : 'text-red-600'}>
                        {signal.outcome.price_change_pct >= 0 ? '+' : ''}{signal.outcome.price_change_pct.toFixed(2)}%
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {signal.outcome ? (
                      <Badge className={outcomeColors[signal.outcome.outcome as keyof typeof outcomeColors] || 'hold'}>
                        {signal.outcome.outcome}
                      </Badge>
                    ) : (
                      <Badge className="pending">Pending</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[var(--text-secondary)]">{signal.regime}</td>
                  <td className="px-4 py-3 text-[var(--text-secondary)] font-mono text-xs">{signal.model_version}</td>
                </tr>
              ))}
              {filteredItems.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-[var(--text-secondary)]">
                    No signals found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-4 border-t border-[var(--border-color)]">
          <span className="text-sm text-[var(--text-secondary)]">
            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}