"""
Tests for Signal Generator.
Verifies signal combination logic, anti-retail-panic, and volume confirmation.
"""

import pytest
from core.entities.technical_signal import TechnicalSignal
from core.entities.volume_signal import VolumeSignal
from use_cases.analysis.signal_generator import SignalGenerator


def _tech(trend="BULLISH", momentum="STRONG", confidence=0.8, rsi=55.0):
    return TechnicalSignal(
        symbol="BTC/IDR", timeframe="1h",
        trend=trend, momentum=momentum,
        volatility="MEDIUM", confidence=confidence,
        rsi=rsi, atr=15000000,
    )


def _volume(net_flow="ACCUMULATING", intensity="HIGH", confidence=0.7, imbalance_score=0.6):
    return VolumeSignal(
        symbol="BTC/IDR",
        net_flow=net_flow, intensity=intensity,
        imbalance_score=imbalance_score, confidence=confidence,
    )


class TestSignalGenerator:
    def setup_method(self):
        self.gen = SignalGenerator()

    def test_bullish_plus_accumulation_is_buy(self):
        """Bullish trend + volume accumulation → BUY or STRONG_BUY."""
        signal = self.gen.generate(_tech("BULLISH"), _volume("ACCUMULATING"))
        assert signal.action in ("BUY", "STRONG_BUY")
        assert signal.confidence > 0

    def test_bearish_plus_distribution_is_sell(self):
        """Bearish trend + volume distribution → SELL or STRONG_SELL."""
        signal = self.gen.generate(
            _tech("BEARISH", "STRONG"),
            _volume("DISTRIBUTING", imbalance_score=-0.6),
        )
        assert signal.action in ("SELL", "STRONG_SELL")

    def test_tech_only_without_volume_is_hold(self):
        """Technical signal alone without volume should be HOLD."""
        signal = self.gen.generate(_tech("BULLISH"), None)
        assert signal.action == "HOLD"
        assert "volume" in signal.reason.lower() or "konfirmasi" in signal.reason.lower()

    def test_anti_retail_panic(self):
        """Bearish price + volume accumulating → HOLD (don't panic sell)."""
        signal = self.gen.generate(
            _tech("BEARISH", "STRONG"),
            _volume("ACCUMULATING"),
        )
        assert signal.action == "HOLD"
        assert "panic" in signal.reason.lower() or "PANIC" in signal.reason

    def test_conflicting_signals_is_hold(self):
        """Bullish price + volume distribution → HOLD (conflicting)."""
        signal = self.gen.generate(
            _tech("BULLISH"),
            _volume("DISTRIBUTING", imbalance_score=-0.5),
        )
        assert signal.action == "HOLD"
        assert "berlawanan" in signal.reason.lower() or "hati" in signal.reason.lower()

    def test_neutral_trend_with_volume_is_hold(self):
        """Neutral trend + volume activity → HOLD (wait for trend)."""
        signal = self.gen.generate(
            _tech("NEUTRAL", "WEAK"),
            _volume("ACCUMULATING"),
        )
        assert signal.action == "HOLD"

    def test_no_data_is_hold(self):
        """No data at all → HOLD."""
        signal = self.gen.generate(None, None)
        assert signal.action == "HOLD"
        assert signal.confidence == 0.0

    def test_strong_buy_conditions(self):
        """Strong confidence + strong momentum → STRONG_BUY."""
        signal = self.gen.generate(
            _tech("BULLISH", "STRONG", confidence=0.9),
            _volume("ACCUMULATING", "HIGH", confidence=0.9, imbalance_score=0.8),
        )
        assert signal.action == "STRONG_BUY"

    def test_signal_to_dict(self):
        """Signal should be serializable to dict."""
        signal = self.gen.generate(_tech(), _volume())
        d = signal.to_dict()
        assert isinstance(d, dict)
        assert "combined_action" in d
        assert "combined_confidence" in d
        assert "technical_trend" in d
        assert "volume_flow" in d

    def test_volume_neutral_with_bullish_tech_is_hold(self):
        """Volume NEUTRAL + Bullish tech → HOLD (no volume confirmation)."""
        signal = self.gen.generate(
            _tech("BULLISH"),
            _volume("NEUTRAL", confidence=0.1, imbalance_score=0.0),
        )
        assert signal.action == "HOLD"
