"""
Technical Analyzer - Multi-indicator trend and momentum analysis.
Uses EMA, RSI, MACD, Bollinger Bands, ATR, and Volume Profile.
"""

import pandas as pd
import numpy as np
import ta
from typing import Optional

from core.entities.technical_signal import TechnicalSignal
from utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalAnalyzer:
    """
    Multi-indicator technical analysis engine.
    
    Analyzes OHLCV data using a weighted scoring system:
    - EMA crossovers (trend direction)
    - RSI (momentum / overbought-oversold)
    - MACD (trend momentum + divergence)
    - Bollinger Bands (volatility + squeeze)
    - ATR (volatility for stop loss)
    - Volume (confirmation)
    """

    def __init__(self):
        """Indicator weights for combined scoring."""
        self.weights = {
            "ema_trend": 0.30,    # EMA alignment = strongest trend signal
            "rsi": 0.15,          # RSI momentum
            "macd": 0.25,         # MACD trend momentum
            "bb": 0.10,           # Bollinger Band position
            "volume": 0.20,       # Volume confirmation
        }

    def analyze(self, df: pd.DataFrame, symbol: str, timeframe: str) -> Optional[TechnicalSignal]:
        """
        Run full technical analysis on OHLCV DataFrame.
        
        Args:
            df: DataFrame with columns [open, high, low, close, volume]
            symbol: Trading pair e.g. 'BTC/IDR'
            timeframe: e.g. '1h'
            
        Returns:
            TechnicalSignal or None if insufficient data
        """
        if df is None or len(df) < 200:
            logger.warning(
                f"⚠️ Insufficient data for {symbol} ({len(df) if df is not None else 0} candles, "
                f"need 200)"
            )
            # Still try with available data if > 50
            if df is None or len(df) < 50:
                return None

        try:
            # ──────────────── Calculate Indicators ────────────────

            close = df["close"]
            high = df["high"]
            low = df["low"]
            volume = df["volume"]

            # EMA (Exponential Moving Average)
            ema_20 = ta.trend.ema_indicator(close, window=20)
            ema_50 = ta.trend.ema_indicator(close, window=50)
            ema_200 = ta.trend.ema_indicator(close, window=min(200, len(df) - 1))

            # RSI (Relative Strength Index)
            rsi = ta.momentum.rsi(close, window=14)

            # MACD
            macd = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
            macd_value = macd.macd()
            macd_signal = macd.macd_signal()
            macd_hist = macd.macd_diff()

            # Bollinger Bands
            bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
            bb_upper = bb.bollinger_hband()
            bb_middle = bb.bollinger_mavg()
            bb_lower = bb.bollinger_lband()

            # ATR (Average True Range)
            atr_indicator = ta.volatility.AverageTrueRange(high, low, close, window=14)
            atr = atr_indicator.average_true_range()

            # Volume analysis
            vol_sma = volume.rolling(window=20).mean()
            volume_ratio = (volume / vol_sma).iloc[-1] if vol_sma.iloc[-1] > 0 else 1.0

            # Get latest values
            last_close_val = close.iloc[-1]
            ema_20_val = ema_20.iloc[-1]
            ema_50_val = ema_50.iloc[-1]
            ema_200_val = ema_200.iloc[-1] if len(ema_200.dropna()) > 0 else ema_50_val
            rsi_val = rsi.iloc[-1]
            macd_val = macd_value.iloc[-1]
            macd_sig_val = macd_signal.iloc[-1]
            macd_hist_val = macd_hist.iloc[-1]
            atr_val = atr.iloc[-1]

            # ──────────────── Scoring System ────────────────

            scores = {}

            # 1. EMA TREND SCORE (-1.0 to +1.0)
            ema_score = 0.0
            tolerance = last_close_val * 0.0001  # 0.01% tolerance for flat data
            
            if last_close_val > ema_20_val + tolerance:
                ema_score += 0.3
            elif last_close_val < ema_20_val - tolerance:
                ema_score -= 0.3

            if ema_20_val > ema_50_val + tolerance:
                ema_score += 0.3
            elif ema_20_val < ema_50_val - tolerance:
                ema_score -= 0.3

            if last_close_val > ema_200_val + tolerance:
                ema_score += 0.4
            elif last_close_val < ema_200_val - tolerance:
                ema_score -= 0.4

            scores["ema_trend"] = max(-1.0, min(1.0, ema_score))

            # 2. RSI SCORE (-1.0 to +1.0)
            if rsi_val > 70:
                rsi_score = -0.5 - (rsi_val - 70) / 60  # Overbought = bearish bias
            elif rsi_val < 30:
                rsi_score = 0.5 + (30 - rsi_val) / 60   # Oversold = bullish bias
            elif rsi_val > 50:
                rsi_score = (rsi_val - 50) / 40          # Above 50 = mild bullish
            else:
                rsi_score = (rsi_val - 50) / 40          # Below 50 = mild bearish
            scores["rsi"] = max(-1.0, min(1.0, rsi_score))

            # 3. MACD SCORE (-1.0 to +1.0)
            macd_score = 0.0
            macd_tolerance = abs(last_close_val) * 0.0001

            if macd_val > macd_sig_val + macd_tolerance:
                macd_score += 0.5        # Bullish crossover
            elif macd_val < macd_sig_val - macd_tolerance:
                macd_score -= 0.5        # Bearish crossover

            if macd_hist_val > macd_tolerance:
                macd_score += 0.3
            elif macd_hist_val < -macd_tolerance:
                macd_score -= 0.3

            # Histogram momentum (increasing or decreasing)
            if len(macd_hist.dropna()) > 2:
                hist_prev = macd_hist.iloc[-2]
                if macd_hist_val > hist_prev:
                    macd_score += 0.2    # Momentum increasing
                else:
                    macd_score -= 0.2

            scores["macd"] = max(-1.0, min(1.0, macd_score))

            # 4. BOLLINGER BANDS SCORE (-1.0 to +1.0)
            bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
            if bb_range > 0:
                bb_position = (last_close_val - bb_lower.iloc[-1]) / bb_range
                # Near upper band = overbought risk, near lower = bounce potential
                bb_score = (bb_position - 0.5) * 0.5  # Mild signal
            else:
                bb_score = 0.0
            scores["bb"] = max(-1.0, min(1.0, bb_score))

            # 5. VOLUME SCORE (-1.0 to +1.0)
            if volume_ratio > 1.5:
                # High volume — confirms trend direction
                vol_score = 0.5 if scores["ema_trend"] > 0 else -0.5
            elif volume_ratio > 1.0:
                vol_score = 0.2 if scores["ema_trend"] > 0 else -0.2
            else:
                vol_score = 0.0  # Low volume = weak signal
            scores["volume"] = max(-1.0, min(1.0, vol_score))

            # ──────────────── Combined Score ────────────────

            combined = sum(
                scores[k] * self.weights[k] for k in self.weights
            )
            combined = max(-1.0, min(1.0, combined))

            # ──────────────── Classify ────────────────

            # Trend
            if combined > 0.2:
                trend = "BULLISH"
            elif combined < -0.2:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"

            # Momentum strength
            abs_score = abs(combined)
            if abs_score > 0.6:
                momentum = "STRONG"
            elif abs_score > 0.3:
                momentum = "MODERATE"
            else:
                momentum = "WEAK"

            # Volatility (from ATR relative to price)
            atr_pct = (atr_val / last_close_val * 100) if last_close_val > 0 else 0
            if atr_pct > 3.0:
                volatility = "HIGH"
            elif atr_pct > 1.5:
                volatility = "MEDIUM"
            else:
                volatility = "LOW"

            # Confidence (how aligned are signals)
            same_direction = sum(
                1 for s in scores.values() if (s > 0) == (combined > 0)
            )
            confidence = same_direction / len(scores)

            signal = TechnicalSignal(
                symbol=symbol,
                timeframe=timeframe,
                trend=trend,
                momentum=momentum,
                volatility=volatility,
                confidence=round(confidence, 2),
                last_close=last_close_val,
                ema_20=round(ema_20_val, 2),
                ema_50=round(ema_50_val, 2),
                ema_200=round(ema_200_val, 2),
                rsi=round(rsi_val, 2),
                macd_value=round(macd_val, 2),
                macd_signal=round(macd_sig_val, 2),
                macd_histogram=round(macd_hist_val, 2),
                bb_upper=round(bb_upper.iloc[-1], 2),
                bb_middle=round(bb_middle.iloc[-1], 2),
                bb_lower=round(bb_lower.iloc[-1], 2),
                atr=round(atr_val, 2),
                volume_ratio=round(volume_ratio, 2),
                trend_score=round(combined, 3),
                momentum_score=round(abs_score, 3),
            )

            logger.info(
                f"📈 {symbol} [{timeframe}] → {trend} ({momentum}) | "
                f"RSI: {rsi_val:.1f} | MACD: {macd_val:+.2f} | "
                f"Confidence: {confidence:.0%}"
            )

            return signal

        except Exception as e:
            logger.error(f"❌ Technical analysis failed for {symbol}: {e}")
            return None
