import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { LayoutDashboard, History, FlaskConical, BarChart2, Activity, Newspaper, Menu, ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '../lib/utils'
import { TopBar } from './TopBar'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'News', href: '/news', icon: Newspaper },
  { name: 'Technical Analysis', href: '/technical-analysis', icon: Activity },
  { name: 'Analytics', href: '/analytics', icon: BarChart2 },
  { name: 'History', href: '/history', icon: History },
  { name: 'Backtest Lab', href: '/backtest', icon: FlaskConical, badge: 'Coming Soon' },
]

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      {/* Mobile Menu Overlay */}
      {isMobile && mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 bg-[var(--bg-secondary)] border-r border-[var(--border-color)] transition-all duration-300 ease-in-out flex flex-col',
          {
            'w-64': sidebarOpen && !isMobile,
            'w-20': !sidebarOpen && !isMobile,
            'w-64 translate-x-0': isMobile && mobileMenuOpen,
            '-translate-x-full': isMobile && !mobileMenuOpen,
            'shadow-xl': isMobile && mobileMenuOpen,
          }
        )}
        aria-label="Main navigation"
      >
        {/* Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-purple-500 flex items-center justify-center">
              <span className="text-white font-bold text-sm">NT</span>
            </div>
            {sidebarOpen && !isMobile && (
              <span className="font-bold text-lg text-[var(--text-primary)]">NLPTrader</span>
            )}
          </div>
          {!isMobile && (
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-secondary)] transition-colors"
              aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <ChevronRight className="w-5 h-5" />}
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Main navigation">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href || (item.href !== '/' && location.pathname.startsWith(item.href))
            return (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive: active }) => cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
                  'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-[var(--bg-secondary)]',
                  active
                    ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-400'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]',
                  !sidebarOpen && !isMobile && 'justify-center px-2'
                )}
                aria-current={isActive ? 'page' : undefined}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" aria-hidden="true" />
                {sidebarOpen || isMobile ? (
                  <span className="flex-1 truncate">{item.name}</span>
                ) : null}
                {(sidebarOpen || isMobile) && item.badge && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary-500/10 text-primary-400 font-medium whitespace-nowrap">
                    {item.badge}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-[var(--border-color)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center">
              <span className="text-xs font-medium text-[var(--text-secondary)]">U</span>
            </div>
            {sidebarOpen && !isMobile && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)] truncate">User</p>
                <p className="text-xs text-[var(--text-secondary)] truncate">Pro Plan</p>
              </div>
            )}
          </div>
        </div>
      </aside>

    {/* Mobile Menu Button */}
    {isMobile && (
      <button
        onClick={() => setMobileMenuOpen(true)}
        className="fixed bottom-4 right-4 z-40 p-3 rounded-full bg-primary-600 text-white shadow-lg hover:shadow-xl transition-shadow lg:hidden"
        aria-label="Open menu"
      >
        <Menu className="w-6 h-6" />
      </button>
    )}

    {/* Main Content */}
    <main
      className={cn(
        'min-h-screen transition-all duration-300 flex flex-col',
        {
          'lg:ml-64': sidebarOpen,
          'lg:ml-20': !sidebarOpen,
        }
      )}
    >
      <TopBar />
      <div className="p-4 lg:p-6 pt-4 flex-1">
        <Outlet />
      </div>
    </main>
  </div>
  )
}
