import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { format, formatDistanceToNow } from 'date-fns'
import { newsApi, NewsArticle } from '../api/client'
import { Card, CardContent, Input } from '../components/ui'
import { Newspaper, ExternalLink, ChevronLeft, ChevronRight, Search } from 'lucide-react'

const finbertColors: Record<string, string> = {
  positive: 'text-green-400',
  negative: 'text-red-400',
  neutral: 'text-yellow-400',
}

const finbertBg: Record<string, string> = {
  positive: 'bg-green-500/10 border-green-500/20',
  negative: 'bg-red-500/10 border-red-500/20',
  neutral: 'bg-yellow-500/10 border-yellow-500/20',
}

const TICKERS = ['All', 'BTC', 'ETH', 'XAUUSD', 'NVDA']

export default function News() {
  const [page, setPage] = useState(0)
  const [pageSize] = useState(20)
  const [tickerFilter, setTickerFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const { data: result = { items: [], total: 0 }, isLoading } = useQuery({
    queryKey: ['news', page, pageSize, tickerFilter],
    queryFn: () => newsApi.getArticles({
      ticker: tickerFilter || undefined,
      limit: pageSize,
      offset: page * pageSize,
    }),
  })

  const { items, total } = result
  const totalPages = Math.ceil(total / pageSize)

  const filtered = searchQuery
    ? items.filter(a => a.headline.toLowerCase().includes(searchQuery.toLowerCase()) || (a.summary || '').toLowerCase().includes(searchQuery.toLowerCase()))
    : items

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">News Feed</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">Market news with AI sentiment analysis</p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex gap-2">
              {TICKERS.map((t) => (
                <button
                  key={t}
                  onClick={() => { setTickerFilter(t === 'All' ? '' : t); setPage(0) }}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                    (t === 'All' && !tickerFilter) || tickerFilter === t
                      ? 'bg-primary-600 text-white shadow-lg shadow-primary-600/25'
                      : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)]'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            <div className="relative flex-1 max-w-xs ml-auto">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <Input
                placeholder="Search headlines..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-[var(--text-secondary)]">Loading articles...</p>
        </div>
      )}

      {/* Articles */}
      {!isLoading && (
        <div className="space-y-4">
          {filtered.length === 0 ? (
            <Card className="py-16">
              <CardContent className="text-center">
                <Newspaper className="w-16 h-16 mx-auto text-[var(--text-secondary)] mb-4 opacity-50" />
                <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">No Articles Found</h2>
                <p className="text-[var(--text-secondary)]">{searchQuery ? 'Try a different search term' : 'No news articles available for this filter'}</p>
              </CardContent>
            </Card>
          ) : (
            filtered.map((article: NewsArticle) => (
              <ArticleCard key={article.id} article={article} />
            ))
          )}
        </div>
      )}

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex items-center justify-between px-4 py-4">
          <span className="text-sm text-[var(--text-secondary)]">
            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="p-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)] disabled:opacity-50 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage(p => p + 1)}
              className="p-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border-color)] disabled:opacity-50 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ArticleCard({ article }: { article: NewsArticle }) {
  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block"
    >
      <Card className="hover:border-primary-500/30 transition-all duration-200 hover:shadow-lg hover:shadow-primary-500/5">
        <CardContent className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-[var(--bg-tertiary)] text-[var(--text-secondary)]">
                  {article.ticker}
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  {article.source} · {formatDistanceToNow(new Date(article.published_at), { addSuffix: true })}
                </span>
                {article.author && (
                  <span className="text-xs text-[var(--text-muted)]">· {article.author}</span>
                )}
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1.5 leading-snug">
                {article.headline}
              </h3>
              {article.summary && (
                <p className="text-sm text-[var(--text-secondary)] line-clamp-2">{article.summary}</p>
              )}
              <div className="flex items-center gap-2 mt-3 flex-wrap">
                {/* FinBERT badge */}
                {article.sentiment && (
                  <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium border ${finbertBg[article.sentiment] || 'bg-[var(--bg-tertiary)]'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${finbertColors[article.sentiment] || 'text-[var(--text-muted)]'}`} />
                    {article.sentiment.charAt(0).toUpperCase() + article.sentiment.slice(1)}
                    {article.sentiment_score !== null && ` (${(article.sentiment_score * 100).toFixed(0)}%)`}
                  </span>
                )}

                <span className="text-xs text-[var(--text-muted)] ml-auto">
                  {format(new Date(article.published_at), 'MMM d, yyyy HH:mm')}
                </span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-[var(--text-muted)] flex-shrink-0 mt-1" />
          </div>
        </CardContent>
      </Card>
    </a>
  )
}
