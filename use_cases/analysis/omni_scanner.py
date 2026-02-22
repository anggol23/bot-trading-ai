"""
Omni-Scanner - The Eyes of the Leviathan.
Scans all available Indodax markets concurrently to filter out illiquid assets.
"""

import asyncio
from typing import List, Dict, Any

from config.settings import Config
from core.interfaces.market_data_port import IMarketData
from utils.logger import get_logger

logger = get_logger(__name__)


class OmniScanner:
    """
    Asynchronous market scanner.
    Filters out dead coins based on 24-hour USD volume.
    """

    def __init__(self, config: Config, market_data: IMarketData):
        self.config = config
        self.market = market_data
        
        # We will use the config's min_usd_value or default to $50,000 equivalent in IDR
        # Assuming 1 USD = 16,000 IDR
        self.min_24h_vol_idr = 50_000 * 16_000

    async def get_liquid_pairs(self) -> List[str]:
        """
        Fetch all available pairs, verify their 24h volume, and return only the liquid ones.
        Also respects the config overrides if specific pairs are requested.
        """
        try:
            # 1. Get all IDR pairs
            all_pairs = await self.market.get_available_pairs()
            logger.info(f"🌐 Omni-Scanner found {len(all_pairs)} total pairs.")

            # If user explicitly configured exact pairs, just validate and return them
            configured_pairs = self.config.trading.pairs
            # We treat empty pairs list, or "ALL" as a signal to scan the whole market
            if configured_pairs and configured_pairs[0] != "ALL":
                logger.info(f"🔍 Using {len(configured_pairs)} explicitly configured pairs.")
                return await self.market.validate_pairs(configured_pairs)

            logger.info(f"🌊 Omni-Scanner diving into {len(all_pairs)} markets to find liquidity...")
            
            # 2. Fetch all tickers to get 24h volume
            # We fetch them concurrently using asyncio.gather
            tasks = [self.market.fetch_ticker(pair) for pair in all_pairs]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            liquid_pairs = []
            for pair, ticker_result in zip(all_pairs, results):
                if isinstance(ticker_result, Exception):
                    logger.debug(f"⚠️ Failed to fetch ticker for {pair}: {ticker_result}")
                    continue
                
                # In Indodax, quoteVolume represents the 24h volume in IDR
                quote_vol = ticker_result.get("quoteVolume", 0)
                
                if quote_vol >= self.min_24h_vol_idr:
                    liquid_pairs.append(pair)
                else:
                    logger.debug(f"🗑️ Skipping {pair}: Illiquid (Vol: Rp {quote_vol:,.0f})")

            logger.info(f"🎯 Omni-Scanner filtered {len(all_pairs)} pairs down to {len(liquid_pairs)} highly liquid assets.")
            return liquid_pairs

        except Exception as e:
            logger.error(f"❌ Omni-Scanner critical failure: {e}")
            # Fallback to configured pairs or a safe default if all else fails
            fallback = ["BTC/IDR", "ETH/IDR", "USDT/IDR"]
            logger.warning(f"⚠️ Falling back to safe defaults: {fallback}")
            return fallback

