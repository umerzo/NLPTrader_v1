"""
ta_engine.py — Pure Technical Analysis Engine

No I/O, no HTTP, no global state. Just functions: data in → signals out.
Designed for: live signals, backtesting, unit testing.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class TASignal:
    signal: str                 # 'buy' | 'sell' | 'hold'
    confidence: int             # 0-100
    indicators: dict            # All calculated indicator values
    levels: dict                # entry, sl, tp1, tp2, tp3
    reasoning: str              # Human-readable explanation
    regime: str                 # 'bull' | 'bear' | 'high_vol' | 'chop' | 'crisis'
    regime_multiplier: float    # Confidence adjustment factor


# ──────────────────────────────────────────────────────────────────────────────
# INDICATOR CALCULATIONS (Pure NumPy/Pandas — no external deps)
# ──────────────────────────────────────────────────────────────────────────────

def sma(data: np.ndarray, window: int) -> Optional[float]:
    if len(data) < window:
        return None
    return round(float(np.mean(data[-window:])), 2)


def ema(data: np.ndarray, window: int) -> Optional[float]:
    if len(data) < window:
        return None
    multiplier = 2 / (window + 1)
    ema_val = float(np.mean(data[:window]))
    for price in data[window:]:
        ema_val = (price - ema_val) * multiplier + ema_val
    return round(ema_val, 2)


def rsi(data: np.ndarray, window: int = 14) -> Optional[float]:
    if len(data) < window + 1:
        return None
    deltas = np.diff(data[-(window + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def macd(data: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    if len(data) < slow:
        return None, None, None
    ema_fast = ema(data, fast)
    ema_slow = ema(data, slow)
    if ema_fast is None or ema_slow is None:
        return None, None, None
    macd_line = round(ema_fast - ema_slow, 2)
    # Signal line & histogram would need full series; simplified for LLM context
    return macd_line, 0, 0


def bollinger_bands(data: np.ndarray, window: int = 20, std_dev: float = 2.0) -> tuple:
    if len(data) < window:
        return None, None, None
    sma_val = float(np.mean(data[-window:]))
    std_val = float(np.std(data[-window:]))
    upper = round(sma_val + std_dev * std_val, 2)
    lower = round(sma_val - std_dev * std_val, 2)
    return upper, sma_val, lower


def atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, window: int = 14) -> Optional[float]:
    if len(closes) < window + 1:
        return None
    tr_list = []
    for i in range(len(closes) - window, len(closes)):
        high_low = highs[i] - lows[i]
        high_close = abs(highs[i] - closes[i - 1])
        low_close = abs(lows[i] - closes[i - 1])
        tr_list.append(max(high_low, high_close, low_close))
    return round(float(np.mean(tr_list)), 2)


def support_resistance(highs: np.ndarray, lows: np.ndarray, window: int = 30) -> tuple:
    if len(highs) < window * 2:
        return [], []
    recent_highs = highs[-window:]
    recent_lows = lows[-window:]
    resistance = sorted([
        round(max(recent_highs[i:i + 5]), 2)
        for i in range(0, len(recent_highs) - 4)
    ], reverse=True)[:5]
    support = sorted([
        round(min(recent_lows[i:i + 5]), 2)
        for i in range(0, len(recent_lows) - 4)
    ])[:5]
    return support, resistance


def fibonacci_levels(highs: np.ndarray, lows: np.ndarray, lookback: int = 90) -> tuple:
    if len(highs) < lookback:
        lookback = len(highs)
    swing_high = float(np.max(highs[-lookback:]))
    swing_low = float(np.min(lows[-lookback:]))
    pcts = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    levels = [round(swing_low + (swing_high - swing_low) * p, 2) for p in pcts]
    return levels, swing_high, swing_low


# ──────────────────────────────────────────────────────────────────────────────
# REGIME DETECTION
# ──────────────────────────────────────────────────────────────────────────────

def detect_regime(vix: Optional[float], spy_trend: Optional[float],
                  breadth: Optional[float] = None) -> tuple:
    """
    Returns (regime_name, confidence_multiplier)
    """
    if vix is None:
        return 'unknown', 1.0

    if vix > 40:
        return 'crisis', 0.5
    elif vix > 30:
        return 'high_vol', 0.8
    elif spy_trend is not None and spy_trend < 0 and vix > 20:
        return 'bear', 0.7
    elif spy_trend is not None and spy_trend > 0 and vix < 15:
        return 'bull', 1.1
    else:
        return 'chop', 0.9


# ──────────────────────────────────────────────────────────────────────────────
# TRADE SETUP CALCULATION
# ──────────────────────────────────────────────────────────────────────────────

def calculate_trade_setup(current_price: float,
                          support_levels: list,
                          resistance_levels: list,
                          rsi: Optional[float]) -> Optional[dict]:
    if not support_levels or not resistance_levels:
        return None
    nearest_support = max([s for s in support_levels if s < current_price], default=None)
    nearest_resistance = min([r for r in resistance_levels if r > current_price], default=None)
    if nearest_support is None or nearest_resistance is None:
        return None
    rng = nearest_resistance - nearest_support
    if rng <= 0:
        return None
    pos = (current_price - nearest_support) / rng

    if rsi is not None and rsi < 45 and pos < 0.4:
        direction = 'buy'
        entry = round(current_price, 2)
        sl = round(nearest_support - rng * 0.15, 2)
        tp1 = round(nearest_resistance, 2)
        tp2 = round(nearest_resistance + rng * 0.3, 2)
        tp3 = round(nearest_resistance + rng * 0.6, 2)
    elif rsi is not None and rsi > 55 and pos > 0.6:
        direction = 'sell'
        entry = round(current_price, 2)
        sl = round(nearest_resistance + rng * 0.15, 2)
        tp1 = round(nearest_support, 2)
        tp2 = round(nearest_support - rng * 0.3, 2)
        tp3 = round(nearest_support - rng * 0.6, 2)
    else:
        return None

    risk = round(abs(entry - sl), 2)
    reward = round(abs(tp1 - entry), 2)
    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": sl,
        "take_profit_1": tp1,
        "take_profit_2": tp2,
        "take_profit_3": tp3,
        "rr_ratio": round(reward / risk, 2) if risk > 0 else 0,
    }


# ──────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────────────────────

def generate_ta_signal(
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    volumes: np.ndarray,
    vix: Optional[float] = None,
    spy_trend: Optional[float] = None,
) -> TASignal:
    """
    Pure function: OHLCV arrays → TASignal
    No I/O, no side effects. Fully testable.
    """
    current_price = float(closes[-1])

    # Indicators
    ind = {
        'rsi_14': rsi(closes, 14),
        'rsi_7': rsi(closes, 7),
        'macd': macd(closes),
        'sma_20': sma(closes, 20),
        'sma_50': sma(closes, 50),
        'ema_12': ema(closes, 12),
        'ema_26': ema(closes, 26),
        'bb_upper': bollinger_bands(closes, 20, 2)[0],
        'bb_lower': bollinger_bands(closes, 20, 2)[2],
        'atr_14': atr(highs, lows, closes, 14),
        'volume_sma_20': sma(volumes, 20) if len(volumes) >= 20 else None,
        'current_volume': float(volumes[-1]) if len(volumes) > 0 else None,
    }

    support, resistance = support_resistance(highs, lows, 30)
    ind['support'] = support
    ind['resistance'] = resistance

    fib_levels, fib_high, fib_low = fibonacci_levels(highs, lows, 90)
    ind['fib_levels'] = fib_levels
    ind['fib_high'] = fib_high
    ind['fib_low'] = fib_low

    # Regime
    regime, regime_mult = detect_regime(vix, spy_trend)

    # Scoring
    score = 0
    reasons = []

    # Trend
    if ind['sma_20'] and ind['sma_50']:
        if ind['sma_20'] > ind['sma_50']:
            score += 15; reasons.append("SMA20 > SMA50 (uptrend)")
        else:
            score -= 15; reasons.append("SMA20 < SMA50 (downtrend)")

    # RSI
    rsi_val = ind['rsi_14']
    if rsi_val is not None:
        if rsi_val < 30:
            score += 20; reasons.append(f"RSI oversold ({rsi_val:.1f})")
        elif rsi_val > 70:
            score -= 20; reasons.append(f"RSI overbought ({rsi_val:.1f})")
        elif rsi_val < 45:
            score += 10
        elif rsi_val > 55:
            score -= 10

    # MACD
    macd_val = ind['macd'][0]
    if macd_val is not None:
        if macd_val > 0:
            score += 15; reasons.append("MACD bullish")
        else:
            score -= 15; reasons.append("MACD bearish")

    # Bollinger position
    if ind['bb_upper'] and ind['bb_lower']:
        bb_pos = (current_price - ind['bb_lower']) / (ind['bb_upper'] - ind['bb_lower'])
        if bb_pos < 0.2:
            score += 10; reasons.append("Near lower Bollinger Band")
        elif bb_pos > 0.8:
            score -= 10; reasons.append("Near upper Bollinger Band")

    # Volume
    if ind['volume_sma_20'] and ind['current_volume']:
        vol_ratio = ind['current_volume'] / ind['volume_sma_20']
        if vol_ratio > 1.5:
            score += 5 if score > 0 else -5
            reasons.append(f"Volume {vol_ratio:.1f}x avg")

    # Support/Resistance proximity
    if support:
        nearest_s = max([s for s in support if s < current_price], default=None)
        if nearest_s and (current_price - nearest_s) / current_price < 0.02:
            score += 10; reasons.append(f"At support {nearest_s:.2f}")
    if resistance:
        nearest_r = min([r for r in resistance if r > current_price], default=None)
        if nearest_r and (nearest_r - current_price) / current_price < 0.02:
            score -= 10; reasons.append(f"At resistance {nearest_r:.2f}")

    # Regime adjustment
    score *= regime_mult

    # Map to signal
    if score >= 25:
        signal = 'buy'
    elif score <= -25:
        signal = 'sell'
    else:
        signal = 'hold'

    confidence = min(95, max(5, int(50 + abs(score) * 1.5)))

    # Trade setup
    trade_setup = calculate_trade_setup(current_price, support, resistance, rsi_val)
    levels = {}
    if trade_setup:
        levels = {
            'entry': trade_setup['entry'],
            'sl': trade_setup['stop_loss'],
            'tp1': trade_setup['take_profit_1'],
            'tp2': trade_setup['take_profit_2'],
            'tp3': trade_setup['take_profit_3'],
        }
    else:
        levels = {'entry': None, 'sl': None, 'tp1': None, 'tp2': None, 'tp3': None}

    return TASignal(
        signal=signal,
        confidence=confidence,
        indicators=ind,
        levels=levels,
        reasoning="; ".join(reasons) if reasons else "No clear signal",
        regime=regime,
        regime_multiplier=regime_mult,
    )


# ──────────────────────────────────────────────────────────────────────────────
# CHART GENERATION (Optional — kept separate for side-effect isolation)
# ──────────────────────────────────────────────────────────────────────────────

def generate_ta_chart(
    full_hist: pd.DataFrame,
    display_hist: pd.DataFrame,
    ticker: str,
    timeframe: str,
    support_levels: list,
    resistance_levels: list,
    trade_setup: Optional[dict] = None,
    output_path: str = "ta_chart_temp.png",
) -> Optional[str]:
    """
    Generates and saves chart to disk. Side effect: writes file.
    Call from API layer only, not from backtest/signal generation.
    """
    try:
        import mplfinance as mpf
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    n_display = len(display_hist)
    df = display_hist.copy()
    df.columns = [c.capitalize() for c in df.columns]
    full_closes = full_hist['Close'].values

    # Indicators on full data
    bb_sma = pd.Series(full_closes).rolling(20).mean()
    bb_std = pd.Series(full_closes).rolling(20).std()
    bb_upper = bb_sma + 2 * bb_std
    bb_lower = bb_sma - 2 * bb_std
    sma20 = pd.Series(full_closes).rolling(20).mean()
    ema12 = pd.Series(full_closes).ewm(span=12, adjust=False).mean()
    ema26 = pd.Series(full_closes).ewm(span=26, adjust=False).mean()
    rsi_full = pd.Series(full_closes).rolling(50).apply(
        lambda x: rsi(x.values) if len(x) == 50 else None, raw=False
    )

    # Slice to display range
    sma20_d = sma20.iloc[-n_display:]
    ema12_d = ema12.iloc[-n_display:]
    ema26_d = ema26.iloc[-n_display:]
    bbu_d = bb_upper.iloc[-n_display:]
    bbl_d = bb_lower.iloc[-n_display:]
    rsi_d = rsi_full.iloc[-n_display:]

    apds = [
        mpf.make_addplot(bbu_d, color='#ff6b6b', width=0.5, alpha=0.4),
        mpf.make_addplot(bbl_d, color='#ff6b6b', width=0.5, alpha=0.4),
        mpf.make_addplot(sma20_d, color='#f7a23b', width=0.8),
        mpf.make_addplot(ema12_d, color='#5b8def', width=0.7),
        mpf.make_addplot(ema26_d, color='#c084fc', width=0.7, alpha=0.7),
        mpf.make_addplot(rsi_d, panel=2, color='#a78bfa', width=0.8, ylabel='RSI'),
    ]

    fig, axes = mpf.plot(
        df, type='candle', volume=True, addplot=apds, style='charles',
        figsize=(18, 11), returnfig=True, panel_ratios=(4, 1, 1),
        tight_layout=True, warn_too_much_data=2000,
    )

    # Fibonacci
    swing_high = df['High'].max()
    swing_low = df['Low'].min()
    fib_pcts = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    fib_labels = ['0%', '23.6%', '38.2%', '50%', '61.8%', '78.6%', '100%']
    for pct, lbl in zip(fib_pcts, fib_labels):
        price = swing_low + (swing_high - swing_low) * pct
        axes[0].axhline(y=price, color='#f7931a', linestyle='--', linewidth=0.5, alpha=0.35)
        axes[0].text(df.index[-1], price, f'  {lbl}', color='#f7931a', fontsize=7, va='center', alpha=0.8)

    # Support/Resistance
    for level in support_levels[:5]:
        axes[0].axhline(y=level, color='#34d399', linestyle='--', linewidth=0.7, alpha=0.7)
        axes[0].text(df.index[-1], level, f'  S:{level}', color='#34d399', fontsize=7, va='center')
    for level in resistance_levels[:5]:
        axes[0].axhline(y=level, color='#f5556d', linestyle='--', linewidth=0.7, alpha=0.7)
        axes[0].text(df.index[-1], level, f'  R:{level}', color='#f5556d', fontsize=7, va='center')

    # Trade setup
    if trade_setup:
        ts = trade_setup
        is_long = ts["direction"] == "BUY"
        clr_entry = '#34d399' if is_long else '#f5556d'
        clr_sl = '#f5556d' if is_long else '#34d399'
        clr_tp = '#34d399' if is_long else '#f5556d'
        last_idx = df.index[-1]

        axes[0].axhline(y=ts["entry"], color=clr_entry, linewidth=2.0, alpha=0.9)
        axes[0].text(last_idx, ts["entry"], f'  ENTRY {ts["entry"]}',
                     color=clr_entry, fontsize=9, fontweight='bold', va='center',
                     bbox=dict(boxstyle='round,pad=0.15', facecolor='#0f1123', edgecolor=clr_entry, alpha=0.8))

        axes[0].axhline(y=ts["stop_loss"], color=clr_sl, linewidth=1.5, alpha=0.8, linestyle='--')
        axes[0].text(last_idx, ts["stop_loss"], f'  SL {ts["stop_loss"]}',
                     color=clr_sl, fontsize=8, fontweight='bold', va='center',
                     bbox=dict(boxstyle='round,pad=0.15', facecolor='#0f1123', edgecolor=clr_sl, alpha=0.8))

        for label, val in [("TP1", ts["take_profit_1"]), ("TP2", ts["take_profit_2"]), ("TP3", ts["take_profit_3"])]:
            if val:
                axes[0].axhline(y=val, color=clr_tp, linewidth=1.0, alpha=0.6, linestyle=':')
                axes[0].text(last_idx, val, f'  {label} {val}',
                             color=clr_tp, fontsize=7, va='center',
                             bbox=dict(boxstyle='round,pad=0.1', facecolor='#0f1123', edgecolor=clr_tp, alpha=0.6))

        axes[0].text(0.02, 0.96, f'R:R 1:{ts["rr_ratio"]}', transform=axes[0].transAxes,
                     fontsize=11, fontweight='bold', color='white',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1d3a', edgecolor='#a78bfa', alpha=0.9))
        dir_label = '▲ LONG' if is_long else '▼ SHORT'
        axes[0].text(0.02, 0.90, dir_label, transform=axes[0].transAxes,
                     fontsize=12, fontweight='bold', color=clr_entry,
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1d3a', edgecolor=clr_entry, alpha=0.9))

    # RSI ref lines
    if len(axes) > 2:
        axes[2].axhline(y=70, color='#f5556d', linestyle=':', linewidth=0.5, alpha=0.5)
        axes[2].axhline(y=30, color='#34d399', linestyle=':', linewidth=0.5, alpha=0.5)
        axes[2].axhline(y=50, color='#aab0c2', linestyle=':', linewidth=0.3, alpha=0.3)
        axes[2].set_ylabel('RSI')

    axes[0].set_title(
        f'{ticker} · {timeframe.upper()} · {n_display}c'
        f'  |  BB(20,2)  |  Fib  |  RSI',
        color='white', fontsize=13, fontweight='bold'
    )

    for ax in axes:
        ax.set_facecolor('#0f1123')
        ax.tick_params(colors='#aab0c2')
        for spine in ax.spines.values():
            spine.set_color('#1a1d3a')
    fig.patch.set_facecolor('#0f1123')

    fig.savefig(output_path, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    return output_path