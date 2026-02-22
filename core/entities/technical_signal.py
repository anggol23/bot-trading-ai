from dataclasses import dataclass
from typing import Optional


@dataclass
class TechnicalSignal:
    """Result of technical analysis on a single timeframe."""
    symbol: str
    timeframe: str
    trend: str           # BULLISH, BEARISH, NEUTRAL
    momentum: str        # STRONG, WEAK, NEUTRAL
    volatility: str      # HIGH, LOW, NORMAL
    confidence: float    # 0.0 - 1.0
    
    # Individual indicator values
    last_close: float = 0.0
    ema_20: float = 0.0
    ema_50: float = 0.0
    ema_200: float = 0.0
    rsi: float = 0.0
    macd_value: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    atr: float = 0.0
    volume_ratio: float = 0.0  # Current vol / 20-period avg
    
    # Component scores (-1.0 to 1.0)
    trend_score: float = 0.0
    momentum_score: float = 0.0

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "trend": self.trend,
            "momentum": self.momentum,
            "volatility": self.volatility,
            "confidence": self.confidence,
            "last_close": self.last_close,
            "ema_20": self.ema_20,
            "ema_50": self.ema_50,
            "ema_200": self.ema_200,
            "rsi": self.rsi,
            "macd_value": self.macd_value,
            "macd_signal": self.macd_signal,
            "atr": self.atr,
            "volume_ratio": self.volume_ratio,
            "trend_score": self.trend_score,
            "momentum_score": self.momentum_score,
        }
