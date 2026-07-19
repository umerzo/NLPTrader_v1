import { cn } from '../../lib/utils'

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'destructive' | 'secondary' | 'outline' | 'buy' | 'sell' | 'hold' | 'pending'
  size?: 'sm' | 'md' | 'lg'
}

export const Badge = ({ className, variant = 'default', size = 'md', ...props }: BadgeProps) => {
  const baseStyles = 'inline-flex items-center rounded-full font-medium transition-colors'

  const variants = {
    default: 'bg-primary-100 text-primary-700 dark:bg-primary-900/30 dark:text-primary-400',
    success: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    destructive: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    secondary: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    outline: 'border border-[var(--border-color)] bg-transparent',
    buy: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    sell: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    hold: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  }

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  }

  return (
    <span className={cn(baseStyles, variants[variant], sizes[size], className)} {...props} />
  )
}