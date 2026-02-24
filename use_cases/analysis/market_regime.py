"""
Market Regime Analyzer - The 'Brain' that detects macro market conditions 
to dynamically adjust AI trading parameters.
"""

from typing import Dict, Any, Optional
import pandas as pd

from core.interfaces.market_data_port import IMarketData
from use_cases.analysis.technical import TechnicalAnalyzer
from utils.logger import get_logger

logger = get_logger(__name__)

class MarketRegimeAnalyzer:
    """
    Detects the global market regime using BTC as the primary market compass.
    Regimes:
    - TRENDING_BULL: Strong upward momentum, low-medium volatility
    - TRENDING_BEAR: Strong downward momentum
    - VOLATILE: High ATR, large price swings (whipsaws)
    - CHOPPY: Low ATR, low momentum sideways movement
    """

    def __init__(self, market_data: IMarketData, tech_analyzer: TechnicalAnalyzer):
        self.market_data = market_data
        self.tech_analyzer = tech_analyzer
        self.current_regime = "NORMAL"
        self.compass_symbol = "BTC/IDR"

    async def analyze(self) -> str:
        """
        Analyze BTC/IDR 1d or 4h chart to determine the macro regime.
        """
        try:
            # Fetch macro data (4h timeframe is good for intra-week regime)
            ohlcv_data = await self.market_data.fetch_multi_timeframe(
                self.compass_symbol, ["4h"]
            )
            df = ohlcv_data.get("4h")
            
            if df is None or df.empty:
                logger.warning("⚠️ MarketRegimeAnalyzer: No data for BTC/IDR, defaulting to NORMAL")
                return "NORMAL"

            tech = self.tech_analyzer.analyze(df, self.compass_symbol, "4h")
            if not tech:
                return "NORMAL"

            # Detect Volatility
            # High volatility: ATR is unusually high compared to price
            # We use volume_ratio and momentum to detect choppiness vs volatility
            
            is_volatile = tech.volatility == "HIGH"
            is_low_vol = tech.volatility == "LOW"
            
            if is_volatile and tech.trend == "NEUTRAL":
                regime = "VOLATILE"
            elif is_low_vol and tech.trend == "NEUTRAL":
                regime = "CHOPPY"
            elif tech.trend == "BULLISH" and tech.momentum == "STRONG":
                regime = "TRENDING_BULL"
            elif tech.trend == "BEARISH" and tech.momentum == "STRONG":
                regime = "TRENDING_BEAR"
            elif tech.trend == "BULLISH":
                regime = "TRENDING_BULL"
            elif tech.trend == "BEARISH":
                regime = "TRENDING_BEAR"
            else:
                regime = "CHOPPY"

            self.current_regime = regime
            logger.info(f"🧠 Market Regime Detected: {regime} (Berdasarkan {self.compass_symbol} 4h)")
            return regime

        except Exception as e:
            logger.error(f"❌ MarketRegimeAnalyzer error: {e}")
            return "NORMAL"
