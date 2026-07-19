import { useEffect, useRef } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickData, LineStyle, CandlestickSeries, LineSeries } from 'lightweight-charts'

interface PriceBar {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface ChartOverlay {
  support_levels: number[]
  resistance_levels: number[]
  entry?: number | null
  sl?: number | null
  tp1?: number | null
  tp2?: number | null
  tp3?: number | null
}

interface TradingViewChartProps {
  data: PriceBar[]
  overlays?: ChartOverlay
  height?: number
}

export default function TradingViewChart({ data, overlays, height = 500 }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: '#0a0b0f' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e213b' },
        horzLines: { color: '#1e213b' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: '#6366f1', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#6366f1' },
        horzLine: { color: '#6366f1', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#6366f1' },
      },
      timeScale: {
        borderColor: '#1e213b',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#1e213b',
      },
    })

    chartRef.current = chart

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#34d399',
      downColor: '#f5556d',
      borderUpColor: '#34d399',
      borderDownColor: '#f5556d',
      wickUpColor: '#34d399',
      wickDownColor: '#f5556d',
    })

    const chartData: CandlestickData[] = data.map((bar) => {
      const date = new Date(bar.time)
      return {
        time: Math.floor(date.getTime() / 1000) as any,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      }
    })
    candleSeries.setData(chartData)
    chart.timeScale().fitContent()

    const overlayLines: ISeriesApi<'Line'>[] = []

    if (overlays) {
      const addLevelLine = (level: number, color: string, width: 1 | 2 | 3 | 4, style: LineStyle, label?: string) => {
        const line = chart.addSeries(LineSeries, {
          color,
          lineWidth: width,
          lineStyle: style,
          lastValueVisible: !!label,
          priceLineVisible: false,
        })
        line.setData(chartData.map((d) => ({ time: d.time, value: level })))
        overlayLines.push(line)
      }

      overlays.support_levels.forEach((level) => addLevelLine(level, '#34d399', 1, LineStyle.Dashed))
      overlays.resistance_levels.forEach((level) => addLevelLine(level, '#f5556d', 1, LineStyle.Dashed))
      if (overlays.entry) addLevelLine(overlays.entry, '#fbbf24', 2, LineStyle.Solid)
      if (overlays.tp1) addLevelLine(overlays.tp1, '#34d399', 2, LineStyle.Dotted)
      if (overlays.tp2) addLevelLine(overlays.tp2, '#34d399', 1, LineStyle.Dotted)
      if (overlays.tp3) addLevelLine(overlays.tp3, '#34d399', 1, LineStyle.Dotted)
      if (overlays.sl) addLevelLine(overlays.sl, '#f5556d', 2, LineStyle.Dashed)
    }

    return () => {
      overlayLines.forEach((line) => chart.removeSeries(line))
      chart.remove()
    }
  }, [data, overlays, height])

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-[var(--border-color)] bg-[#0a0b0f]"
        style={{ height }}
      >
        <p className="text-[var(--text-secondary)]">No price data available</p>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="rounded-lg overflow-hidden border border-[var(--border-color)]"
      style={{ height }}
    />
  )
}
