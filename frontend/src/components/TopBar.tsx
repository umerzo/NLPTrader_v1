import { Bell } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'

/**
 * Top bar, sits above the routed page content in Layout.tsx.
 *
 * The avatar and notification bell are intentionally decorative — there is
 * no auth system yet. They're isolated here (not wired to any real session
 * or notification data) so real auth can slot in later without touching
 * surrounding layout code. Do not wire fake click behavior to them beyond
 * what's here.
 *
 * The ticker tape slot is reserved but empty until Task 16
 * (GET /api/tickers/tracked/quotes) lands and `tickersApi.trackedQuotes()`
 * exists in client.ts.
 */
export function TopBar() {
  return (
    <div className="flex items-center justify-between h-14 px-4 lg:px-6 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <div className="flex-1 min-w-0">
        {/* TickerTape mounts here once Task 16 is confirmed */}
      </div>

      <div className="flex items-center gap-2 flex-shrink-0">
        <ThemeToggle />

        <button
          className="relative p-2 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-5 h-5" />
        </button>

        <div className="w-8 h-8 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center border border-[var(--border-color)]">
          <span className="text-xs font-medium text-[var(--text-secondary)]">U</span>
        </div>
      </div>
    </div>
  )
}
