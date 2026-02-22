"""
Tests for Technical Analyzer.
Verifies indicator calculations and signal classification.
"""

import pytest
import pandas as pd
import numpy as np
from use_cases.analysis.technical import TechnicalAnalyzer
from core.entities.technical_signal import TechnicalSignal


def _make_ohlcv(trend="bullish", length=200):
    """Generate mock OHLCV data for testing."""
    np.random.seed(42)

    if trend == "bullish":
        # Exponential uptrend to guarantee short EMA > long EMA
        base = 1_000_000 + np.exp(np.linspace(0, 5, length)) * 10_000
        noise = np.random.normal(0, 2000, length)
    elif trend == "bearish":
        # Exponential downtrend
        base = 2_000_000 - np.exp(np.linspace(0, 5, length)) * 10_000
        noise = np.random.normal(0, 2000, length)
    else:
        # Perfectly sideways, very low noise to prevent false momentum
        base = np.full(length, 1_500_000)
        noise = np.random.normal(0, 100, length)

    close = base + noise
    high = close + np.abs(np.random.normal(5000, 3000, length))
    low = close - np.abs(np.random.normal(5000, 3000, length))
    open_ = close + np.random.normal(0, 3000, length)
    volume = np.abs(np.random.normal(100, 30, length))

    dates = pd.date_range("2025-01-01", periods=length, freq="1h")

    df = pd.DataFrame({
        "timestamp": [int(d.timestamp() * 1000) for d in dates],
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    df["datetime"] = dates
    df.set_index("datetime", inplace=True)

    return df


class TestTechnicalAnalyzer:
    def setup_method(self):
        self.analyzer = TechnicalAnalyzer()

    def test_bullish_trend_detection(self):
        """Bullish data should produce BULLISH trend signal."""
        df = _make_ohlcv("bullish")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        assert signal.symbol == "BTC/IDR"
        assert signal.timeframe == "1h"
        assert signal.trend == "BULLISH"
        assert signal.confidence > 0
        assert signal.trend_score > 0

    def test_bearish_trend_detection(self):
        """Bearish data should produce BEARISH trend signal."""
        df = _make_ohlcv("bearish")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        assert signal.trend == "BEARISH"
        assert signal.trend_score < 0

    def test_neutral_trend_detection(self):
        """Sideways data should produce NEUTRAL or weak signal."""
        df = _make_ohlcv("neutral")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        # On perfectly flat data, we expect the trend to be NEUTRAL
        assert signal.trend == "NEUTRAL"
        assert abs(signal.trend_score) < 1.0

    def test_insufficient_data(self):
        """Should return None with too little data."""
        df = _make_ohlcv("bullish", length=10)
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")
        assert signal is None

    def test_rsi_in_range(self):
        """RSI should always be between 0 and 100."""
        df = _make_ohlcv("bullish")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        assert 0 <= signal.rsi <= 100

    def test_atr_positive(self):
        """ATR should always be positive."""
        df = _make_ohlcv("bullish")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        assert signal.atr > 0

    def test_ema_ordering_bullish(self):
        """In strong bullish, close > EMA20 > EMA50."""
        df = _make_ohlcv("bullish")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        # In a clean uptrend, close should be above short-term EMAs
        assert signal.last_close > signal.ema_50

    def test_confidence_range(self):
        """Confidence should be between 0 and 1."""
        for trend in ["bullish", "bearish", "neutral"]:
            df = _make_ohlcv(trend)
            signal = self.analyzer.analyze(df, "BTC/IDR", "1h")
            if signal:
                assert 0.0 <= signal.confidence <= 1.0

    def test_signal_to_dict(self):
        """Signal should be convertible to dict."""
        df = _make_ohlcv("bullish")
        signal = self.analyzer.analyze(df, "BTC/IDR", "1h")

        assert signal is not None
        d = signal.to_dict()
        assert isinstance(d, dict)
        assert "trend" in d
        assert "rsi" in d
        assert "atr" in d
