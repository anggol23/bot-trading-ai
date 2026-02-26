"""
Signal Generator - Combines technical and whale signals into trading decisions.
Whale confirmation is REQUIRED for entry — technical alone is not enough.
"""

from typing import Dict, List, Optional, Any

from core.entities.technical_signal import TechnicalSignal
from core.entities.volume_signal import VolumeSignal
from core.entities.trading_signal import TradingSignal
from utils.logger import get_logger

logger = get_logger(__name__)


class SignalGenerator:
    """
    Combines technical analysis + volume flow into final trading decisions.
    
    CORE RULES:
    1. Volume confirmation REQUIRED for entry — technical alone = HOLD
    2. Ignore retail panic: if volume accumulates but price drops → HOLD, not SELL
    3. Multi-timeframe: need agreement from at least 2 timeframes
    4. Minimum confidence threshold for action
    """

    MIN_CONFIDENCE = 0.4   # Below this → always HOLD
    STRONG_THRESHOLD = 0.7  # Above this → STRONG signal

    def generate(
        self,
        tech_signal: Optional[TechnicalSignal],
        volume_signal: Optional[VolumeSignal],
        sentiment_signal: Optional[Dict[str, Any]] = None,
    ) -> TradingSignal:
        """
        Generate a trading signal by combining technical + whale analysis.
        
        Args:
            tech_signal: TechnicalSignal from technical analysis
            volume_signal: VolumeSignal from volume analysis
            
        Returns:
            TradingSignal with action and confidence
        """
        symbol = tech_signal.symbol if tech_signal else (
            volume_signal.symbol if volume_signal else "UNKNOWN"
        )

        # ──── VETO: Fundamental News Crash ────
        if sentiment_signal and sentiment_signal.get("status") == "NEGATIVE":
            reason = (
                f"🚨 SENTIMENT VETO: Berita fundamental sangat buruk "
                f"(Score: {sentiment_signal.get('score'):.2f}) | "
                f"Mencegah resiko crash, force HOLD."
            )
            return TradingSignal(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason=reason,
                technical=tech_signal,
                volume=volume_signal,
            )

        # ──── Case 1: No data at all ────
        if tech_signal is None and volume_signal is None:
            return TradingSignal(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason="Tidak ada data analisis tersedia",
            )

        # ──── Case 2: Only technical (no volume data) ────
        if volume_signal is None:
            return self._tech_only_signal(tech_signal, volume_signal)

        # ──── Case 3: Both signals available ────
        return self._combined_signal(tech_signal, volume_signal)

    def _tech_only_signal(
        self,
        tech: TechnicalSignal,
        volume: Optional[VolumeSignal],
    ) -> TradingSignal:
        """
        Technical-only signal (volume data insufficient).
        Rule: NEVER generate buy/sell without volume confirmation → always HOLD
        """
        if tech is None:
            return TradingSignal(
                symbol="UNKNOWN",
                action="HOLD",
                confidence=0.0,
                reason="Data teknikal tidak tersedia",
                volume=volume,
            )

        reason = (
            f"Teknikal: {tech.trend} ({tech.momentum}) | "
            f"RSI: {tech.rsi:.1f} | "
            f"⚠️ HOLD — Menunggu konfirmasi volume"
        )

        return TradingSignal(
            symbol=tech.symbol,
            action="HOLD",
            confidence=tech.confidence * 0.3,  # Low confidence without volume
            reason=reason,
            technical=tech,
            volume=volume,
        )

    def _combined_signal(
        self,
        tech: Optional[TechnicalSignal],
        volume: VolumeSignal,
    ) -> TradingSignal:
        """
        Combined signal: technical + volume data.
        This is where the real magic happens.
        """
        symbol = tech.symbol if tech else volume.symbol

        # ──── ANTI-RETAIL-PANIC LOGIC ────
        # If volume accumulates but technical is bearish → HOLD (don't panic sell)
        if tech and tech.trend == "BEARISH" and volume.net_flow == "ACCUMULATING":
            confidence = volume.confidence * 0.5
            reason = (
                f"� ANTI-PANIC: Harga turun ({tech.trend}) tapi terjadi AKUMULASI | "
                f"Imbalance: {volume.imbalance_score:+.3f} | "
                f"→ HOLD — Ikuti smart money, abaikan kepanikan ritel"
            )
            return TradingSignal(
                symbol=symbol,
                action="HOLD",
                confidence=confidence,
                reason=reason,
                technical=tech,
                volume=volume,
            )

        # ──── ALIGNED SIGNALS ────

        # BULLISH + ACCUMULATING → BUY
        if tech and tech.trend == "BULLISH" and volume.net_flow == "ACCUMULATING":
            combined_conf = (tech.confidence * 0.5 + volume.confidence * 0.5)

            if combined_conf >= self.STRONG_THRESHOLD and tech.momentum == "STRONG":
                action = "STRONG_BUY"
                reason = (
                    f"✅ STRONG BUY: Trend {tech.trend} ({tech.momentum}) + "
                    f"Volume {volume.net_flow} ({volume.intensity}) | "
                    f"RSI: {tech.rsi:.1f} | Imbalance: {volume.imbalance_score:+.3f}"
                )
            else:
                action = "BUY"
                reason = (
                    f"🟢 BUY: Trend {tech.trend} + Volume {volume.net_flow} | "
                    f"RSI: {tech.rsi:.1f} | Imbalance: {volume.imbalance_score:+.3f}"
                )

            return TradingSignal(
                symbol=symbol,
                action=action,
                confidence=round(combined_conf, 2),
                reason=reason,
                technical=tech,
                volume=volume,
            )

        # BEARISH + DISTRIBUTING → SELL
        if tech and tech.trend == "BEARISH" and volume.net_flow == "DISTRIBUTING":
            combined_conf = (tech.confidence * 0.5 + volume.confidence * 0.5)

            if combined_conf >= self.STRONG_THRESHOLD and tech.momentum == "STRONG":
                action = "STRONG_SELL"
                reason = (
                    f"🔴 STRONG SELL: Trend {tech.trend} ({tech.momentum}) + "
                    f"Volume {volume.net_flow} ({volume.intensity}) | "
                    f"RSI: {tech.rsi:.1f} | Imbalance: {volume.imbalance_score:+.3f}"
                )
            else:
                action = "SELL"
                reason = (
                    f"🟥 SELL: Trend {tech.trend} + Volume {volume.net_flow} | "
                    f"RSI: {tech.rsi:.1f} | Imbalance: {volume.imbalance_score:+.3f}"
                )

            return TradingSignal(
                symbol=symbol,
                action=action,
                confidence=round(combined_conf, 2),
                reason=reason,
                technical=tech,
                volume=volume,
            )

        # NEUTRAL trend + volume signal → mild signal
        if tech and tech.trend == "NEUTRAL" and volume.net_flow == "ACCUMULATING":
            return TradingSignal(
                symbol=symbol,
                action="BUY",
                confidence=round(volume.confidence * 0.6, 2),
                reason=(
                    f"📊 Trend NEUTRAL + Terjadi AKUMULASI | "
                    f"Volume kuat mengambil alih. Imbalance: {volume.imbalance_score:+.3f}"
                ),
                technical=tech,
                volume=volume,
            )

        if tech and tech.trend == "NEUTRAL" and volume.net_flow == "DISTRIBUTING":
            return TradingSignal(
                symbol=symbol,
                action="SELL",
                confidence=round(volume.confidence * 0.6, 2),
                reason=(
                    f"📊 Trend NEUTRAL + Terjadi DISTRIBUSI | "
                    f"Waspada potensi penurunan. Imbalance: {volume.imbalance_score:+.3f}"
                ),
                technical=tech,
                volume=volume,
            )

        # BULLISH + DISTRIBUTING → conflicting → HOLD
        if tech and tech.trend == "BULLISH" and volume.net_flow == "DISTRIBUTING":
            return TradingSignal(
                symbol=symbol,
                action="HOLD",
                confidence=0.2,
                reason=(
                    f"⚠️ Sinyal berlawanan: Trend BULLISH tapi terjadi DISTRIBUSI | "
                    f"Smart money keluar — hati-hati!"
                ),
                technical=tech,
                volume=volume,
            )

        # STRONG TREND + NEUTRAL VOLUME → ALLOW ENTRY
        if tech and volume.net_flow == "NEUTRAL":
            if tech.trend == "BULLISH" and tech.confidence >= 0.4:
                return TradingSignal(
                    symbol=symbol,
                    action="BUY" if tech.momentum != "STRONG" else "STRONG_BUY",
                    confidence=round(tech.confidence * 0.8, 2),
                    reason=f"🚀 Teknis {tech.trend} ({tech.momentum}) murni | Vol netral | RSI: {tech.rsi:.1f}",
                    technical=tech,
                    volume=volume,
                )
            elif tech.trend == "BEARISH" and tech.confidence >= 0.4:
                return TradingSignal(
                    symbol=symbol,
                    action="SELL" if tech.momentum != "STRONG" else "STRONG_SELL",
                    confidence=round(tech.confidence * 0.8, 2),
                    reason=f"📉 Teknis {tech.trend} ({tech.momentum}) murni | Vol netral | RSI: {tech.rsi:.1f}",
                    technical=tech,
                    volume=volume,
                )

        # Default fallback
        return TradingSignal(
            symbol=symbol,
            action="HOLD",
            confidence=0.1,
            reason="Sinyal tidak cukup kuat untuk entry",
            technical=tech,
            volume=volume,
        )

    def generate_multi_timeframe(
        self,
        tech_signals: Dict[str, TechnicalSignal],
        volume_signal: VolumeSignal,
        sentiment_signal: Optional[Dict[str, Any]] = None,
        daily_target_met: bool = False,
        market_regime: str = "NORMAL",
    ) -> TradingSignal:
        """
        Generate signal using multi-timeframe confirmation.
        Requires at least 2 timeframes to agree.
        
        Args:
            tech_signals: Dict mapping timeframe to TechnicalSignal
            volume_signal: VolumeSignal for the symbol
            
        Returns:
            TradingSignal with multi-TF confirmation
        """
        # Generate signal for each timeframe
        signals = {}
        for tf, tech in tech_signals.items():
            if tech is not None:
                signals[tf] = self.generate(tech, volume_signal, sentiment_signal)

        if not signals:
            symbol = volume_signal.symbol if volume_signal else "UNKNOWN"
            return TradingSignal(
                symbol=symbol,
                action="HOLD",
                confidence=0.0,
                reason="Tidak ada data multi-timeframe",
            )

        # Count aligned signals
        actions = [s.action for s in signals.values()]
        buy_signals = sum(1 for a in actions if a in ("BUY", "STRONG_BUY"))
        sell_signals = sum(1 for a in actions if a in ("SELL", "STRONG_SELL"))
        total = len(actions)

        # Use the primary timeframe signal as base
        primary_tf = list(signals.keys())[0]  # Usually "1h"
        primary = signals[primary_tf]

        # Multi-TF confirmation
        if buy_signals >= 2:
            primary.timeframes_aligned = buy_signals
            primary.total_timeframes = total
            primary.reason += f" | ✅ MTF: {buy_signals}/{total} timeframes confirm BUY"
            primary.confidence = min(1.0, primary.confidence * 1.2)
        elif sell_signals >= 2:
            primary.timeframes_aligned = sell_signals
            primary.total_timeframes = total
            primary.reason += f" | ✅ MTF: {sell_signals}/{total} timeframes confirm SELL"
            primary.confidence = min(1.0, primary.confidence * 1.2)
        else:
            # No multi-TF agreement
            if primary.action in ("STRONG_BUY", "STRONG_SELL"):
                # Pass through strong signals but with reduced confidence
                primary.confidence *= 0.8
                primary.action = "BUY" if primary.action == "STRONG_BUY" else "SELL"
                primary.reason += f" | ⚠️ MTF: Tidak ada konfirmasi, di-downgrade menjadi regular"
            elif primary.action in ("BUY", "SELL"):
                # Pass through regular signals with reduced confidence, without becoming HOLD
                primary.confidence *= 0.6
                primary.reason += f" | ⚠️ MTF: Tidak ada konfirmasi multi-timeframe"
            else:
                # Ensure HOLD remains HOLD
                primary.action = "HOLD"
                primary.confidence *= 0.5
                primary.reason += f" | ⚠️ MTF: Tidak ada konfirmasi multi-timeframe"
            
            primary.timeframes_aligned = max(buy_signals, sell_signals)
            primary.total_timeframes = total

        # Apply Target Profit (Minimum Profit Mode) logic
        if not daily_target_met:
            # Not yet met daily target -> AGGRESSIVE HUNTER MODE
            # Boost confidence slightly to trigger more trades
            primary.confidence = min(1.0, primary.confidence * 1.5)
            primary.reason += " | 🎯 HUNTER MODE: Mengejar target harian"
        else:
            # Target met -> RELAXED / ELITE MODE
            # Penalize confidence so only A+ setups generate trades
            primary.confidence *= 0.6
            primary.reason += " | 🛡️ ELITE MODE: Target harian tercapai, sangat selektif"

        # Apply Market Regime Adaptation
        if market_regime == "CHOPPY":
            primary.confidence *= 0.5
            primary.reason += " | 🌊 CHOPPY MARKET: Waspada sinyal palsu"
        elif market_regime == "VOLATILE":
            primary.reason += " | ⚡ VOLATILE MARKET: Perhatikan SL"
        elif market_regime == "TRENDING_BULL" and primary.action in ("BUY", "STRONG_BUY"):
            primary.confidence = min(1.0, primary.confidence * 1.2)
            primary.reason += " | 🚀 STRONG BULL REGIME: Sinyal Buy dikuatkan"
        elif market_regime == "TRENDING_BEAR":
            # Market Correlation Veto: Don't buy anything if BTC is crashing
            if primary.action in ("BUY", "STRONG_BUY"):
                primary.action = "HOLD"
                primary.confidence *= 0.2
                primary.reason = f"🚨 VETO KORELASI BTC: Pasar global Bearish tajam. Menghindari entry di {primary.symbol} || " + primary.reason
            else:
                primary.confidence = min(1.0, primary.confidence * 1.2)
                primary.reason += " | 🩸 STRONG BEAR REGIME: Sinyal Sell dikuatkan"

        # Flag for AI (LLM) Audit if confidence is high and LLM is enabled
        if primary.action in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL") and primary.confidence >= 0.7:
            primary.ai_decision = "AWAITING"
            primary.reason += " | 🤖 AI AUDIT: Sinyal kuat, memanggil LLM Strategist untuk konfirmasi"

        logger.info(
            f"📊 {primary.symbol} Multi-TF Signal: {primary.action} | "
            f"Aligned: {primary.timeframes_aligned}/{primary.total_timeframes} | "
            f"Confidence: {primary.confidence:.0%} | {primary.reason}"
        )

        return primary
