"""
CryptoPanic Client - Fetches live cryptocurrency news headlines asynchronously.
"""

import aiohttp
import asyncio
from typing import List

from config.settings import Config
from core.interfaces.news_port import INewsData
from utils.logger import get_logger

logger = get_logger(__name__)


class CryptoPanicClient(INewsData):
    """Implementation of INewsData using the free CryptoPanic API."""

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.news.cryptopanic_api_key
        self.base_url = "https://cryptopanic.com/api/v1/posts/"

    async def fetch_recent_headlines(self, symbol: str, limit: int = 20) -> List[str]:
        """Fetch recent headlines for a symbol using aiohttp."""
        
        # Fast exit if sentiment is disabled or no API key is set
        if not self.config.risk.enable_sentiment_veto or not self.api_key:
            return []
            
        # Parse symbol (e.g., 'BTC/IDR' -> 'BTC')
        coin = symbol.split('/')[0].upper()
        
        headlines = []
        try:
            params = {
                "auth_token": self.api_key,
                "currencies": coin,
                "kind": "news",
                "filter": "important", # Pre-filter for high-impact news if possible
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params, timeout=10) as response:
                    # CryptoPanic might return 401 if key is missing/invalid, or 429 if rate limited
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        for item in results:
                            # Extract headline title
                            title = item.get("title")
                            if title:
                                headlines.append(title)
                                if len(headlines) >= limit:
                                    break
                    else:
                        logger.warning(f"⚠️ CryptoPanic API returned status {response.status} for {coin}")
                        
            return headlines
            
        except asyncio.TimeoutError:
            logger.warning(f"⏳ CryptoPanic API timeout for {symbol}")
            return []
        except Exception as e:
            logger.error(f"❌ CryptoPanic client error for {symbol}: {e}")
            return []
