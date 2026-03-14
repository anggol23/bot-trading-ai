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


def _volume(net_flow="ACCUMULATING", intensity="HIGH", confidence=0.7, imbalance_score=0.6, whale_score=0):
    return VolumeSignal(
        symbol="BTC/IDR",
        net_flow=net_flow, intensity=intensity,
        imbalance_score=imbalance_score, confidence=confidence,
        whale_score=whale_score,
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
        """Bullish price + strong distribution → HOLD (conflicting)."""
        signal = self.gen.generate(
            _tech("BULLISH"),
            _volume("DISTRIBUTING", confidence=0.8, imbalance_score=-0.5),
        )
        assert signal.action == "HOLD"
        assert "berlawanan" in signal.reason.lower() or "hati" in signal.reason.lower()

    def test_bullish_mild_distribution_can_buy_dip(self):
        """Bullish trend + mild distribution can produce a cautious BUY."""
        signal = self.gen.generate(
            _tech("BULLISH", "MODERATE", confidence=0.82),
            _volume("DISTRIBUTING", confidence=0.5, imbalance_score=-0.25),
        )
        assert signal.action in ("BUY", "STRONG_BUY")

    def test_neutral_trend_accumulating_is_smart_money_buy(self):
        """Neutral trend + volume accumulation → BUY (smart money leads)."""
        signal = self.gen.generate(
            _tech("NEUTRAL", "WEAK"),
            _volume("ACCUMULATING"),
        )
        assert signal.action == "BUY"

    def test_neutral_trend_distributing_is_hold(self):
        """Neutral trend + distribution → HOLD (wait for clearer direction)."""
        signal = self.gen.generate(
            _tech("NEUTRAL", "WEAK"),
            _volume("DISTRIBUTING", imbalance_score=-0.4),
        )
        assert signal.action == "HOLD"

    def test_neutral_trend_range_buy_on_high_volume(self):
        """Neutral trend + NEUTRAL HIGH volume + good whale + tight imbalance → Range BUY."""
        signal = self.gen.generate(
            _tech("NEUTRAL", "WEAK", confidence=0.5),
            _volume("NEUTRAL", "HIGH", confidence=0.55, imbalance_score=-0.10, whale_score=5),
        )
        assert signal.action == "BUY"
        assert signal.confidence >= 0.48

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

    def test_multi_tf_adaptive_fallback_allows_buy(self):
        """Strong multi-TF bullish alignment with non-opposing volume can become BUY."""
        tech_signals = {
            "1h": _tech("BULLISH", "MODERATE", confidence=0.82),
            "4h": TechnicalSignal(
                symbol="BTC/IDR",
                timeframe="4h",
                trend="BULLISH",
                momentum="STRONG",
                volatility="MEDIUM",
                confidence=0.9,
                rsi=60.0,
                atr=20000000,
            ),
        }
        volume = VolumeSignal(
            symbol="BTC/IDR",
            net_flow="NEUTRAL",
            intensity="HIGH",
            imbalance_score=-0.1,
            confidence=0.5,
            whale_score=5,
        )

        signal = self.gen.generate_multi_timeframe(tech_signals, volume)
        assert signal.action in ("BUY", "STRONG_BUY")
        assert signal.timeframes_aligned >= 2

    def test_multi_tf_bull_regime_allows_mild_distribution_buy(self):
        """In strong bull regime, mild distribution should not block adaptive BUY."""
        tech_signals = {
            "1h": _tech("BULLISH", "MODERATE", confidence=0.8),
            "4h": TechnicalSignal(
                symbol="BTC/IDR",
                timeframe="4h",
                trend="BULLISH",
                momentum="MODERATE",
                volatility="MEDIUM",
                confidence=0.86,
                rsi=59.0,
                atr=18000000,
            ),
        }
        volume = VolumeSignal(
            symbol="BTC/IDR",
            net_flow="DISTRIBUTING",
            intensity="HIGH",
            imbalance_score=-0.30,
            confidence=0.6,
            whale_score=4,
        )

        signal = self.gen.generate_multi_timeframe(tech_signals, volume, market_regime="TRENDING_BULL")
        assert signal.action in ("BUY", "STRONG_BUY")
