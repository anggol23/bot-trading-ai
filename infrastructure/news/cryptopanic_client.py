"""
CryptoPanic Client - Fetches live cryptocurrency news headlines asynchronously.
"""

import aiohttp
import asyncio
import time
from typing import List

from config.settings import Config
from core.interfaces.news_port import INewsData
from utils.logger import get_logger

logger = get_logger(__name__)


class CryptoPanicClient(INewsData):
    """Implementation of INewsData using the free CryptoPanic API."""

    PLAN_CANDIDATES = ("developer", "growth", "enterprise")
    CONFIG_ERROR_COOLDOWN_SECONDS = 30 * 60
    RATE_LIMIT_COOLDOWN_SECONDS = 10 * 60

    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.news.cryptopanic_api_key
        self.api_plan = (config.news.cryptopanic_api_plan or "developer").lower()
        self.public_mode = config.news.cryptopanic_public_mode
        self.session = None
        self._resolved_base_url = None
        self._resolved_plan = None
        self._disabled_until = 0.0
        self._disable_reason = ""

    def _build_base_url(self, plan: str) -> str:
        return f"https://cryptopanic.com/api/{plan}/v2/posts/"

    def _build_params(self, coin: str) -> dict:
        params = {
            "auth_token": self.api_key,
            "currencies": coin,
            "kind": "news",
            "filter": "important",
        }
        if self.public_mode:
            params["public"] = "true"
        return params

    def _service_disabled(self) -> bool:
        return time.monotonic() < self._disabled_until

    def _disable_service(self, seconds: int, reason: str):
        self._disabled_until = time.monotonic() + seconds
        self._disable_reason = reason

    def _candidate_plans(self) -> List[str]:
        ordered = [self.api_plan, *self.PLAN_CANDIDATES]
        unique = []
        for plan in ordered:
            if plan not in unique:
                unique.append(plan)
        return unique

    async def _request_json(self, url: str, params: dict):
        session = await self._get_session()
        async with session.get(url, params=params, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "")
            payload = await response.json(content_type=None) if "json" in content_type.lower() else await response.text()
            return response.status, payload

    async def _resolve_base_url(self, coin: str) -> str:
        if self._resolved_base_url:
            return self._resolved_base_url

        params = self._build_params(coin)
        last_status = None
        for plan in self._candidate_plans():
            url = self._build_base_url(plan)
            try:
                status, payload = await self._request_json(url, params)
            except asyncio.TimeoutError:
                logger.warning(f"⏳ CryptoPanic API timeout while resolving endpoint for {coin}")
                raise
            except Exception as error:
                logger.error(f"❌ CryptoPanic endpoint probe failed for plan {plan}: {error}")
                raise

            if status == 200:
                self._resolved_base_url = url
                self._resolved_plan = plan
                if plan != self.api_plan:
                    logger.warning(
                        f"⚠️ CryptoPanic API plan auto-switched: configured={self.api_plan}, resolved={plan}"
                    )
                return url

            last_status = status
            if status in (401, 403):
                reason = f"CryptoPanic auth/plan rejected with status {status}"
                logger.warning(f"⚠️ {reason}. Disabling sentiment fetch temporarily.")
                self._disable_service(self.CONFIG_ERROR_COOLDOWN_SECONDS, reason)
                return ""

            if status == 429:
                reason = "CryptoPanic rate limited requests"
                logger.warning(f"⚠️ {reason}. Cooling down sentiment fetch temporarily.")
                self._disable_service(self.RATE_LIMIT_COOLDOWN_SECONDS, reason)
                return ""

            if status != 404:
                logger.warning(
                    f"⚠️ CryptoPanic endpoint probe for plan {plan} returned status {status}: {payload}"
                )

        reason = (
            "CryptoPanic endpoint not found for all known plans. "
            "Check CRYPTOPANIC_API_PLAN or API availability."
        )
        logger.warning(f"⚠️ {reason} Last status: {last_status}")
        self._disable_service(self.CONFIG_ERROR_COOLDOWN_SECONDS, reason)
        return ""

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def fetch_recent_headlines(self, symbol: str, limit: int = 20) -> List[str]:
        """Fetch recent headlines for a symbol using aiohttp."""
        
        # Fast exit if sentiment is disabled or no API key is set
        if not self.config.risk.enable_sentiment_veto or not self.api_key:
            return []

        if self._service_disabled():
            remaining = max(0.0, self._disabled_until - time.monotonic())
            logger.info(
                f"📰 CryptoPanic fetch skipped for {symbol}: service cooldown active for {remaining:.0f}s "
                f"({self._disable_reason})"
            )
            return []
            
        # Parse symbol (e.g., 'BTC/IDR' -> 'BTC')
        coin = symbol.split('/')[0].upper()
        
        headlines = []
        try:
            base_url = await self._resolve_base_url(coin)
            if not base_url:
                return []

            status, payload = await self._request_json(base_url, self._build_params(coin))
            if status == 200:
                data = payload if isinstance(payload, dict) else {}
                results = data.get("results", [])
                for item in results:
                    title = item.get("title")
                    if title:
                        headlines.append(title)
                        if len(headlines) >= limit:
                            break
            elif status in (401, 403):
                reason = f"CryptoPanic request rejected with status {status}"
                logger.warning(f"⚠️ {reason}. Disabling sentiment fetch temporarily.")
                self._disable_service(self.CONFIG_ERROR_COOLDOWN_SECONDS, reason)
            elif status == 429:
                reason = "CryptoPanic rate limited requests"
                logger.warning(f"⚠️ {reason}. Cooling down sentiment fetch temporarily.")
                self._disable_service(self.RATE_LIMIT_COOLDOWN_SECONDS, reason)
            elif status == 404:
                logger.warning(
                    f"⚠️ CryptoPanic returned 404 for {coin} on resolved plan {self._resolved_plan or self.api_plan}. "
                    "Refreshing endpoint cache."
                )
                self._resolved_base_url = None
                self._resolved_plan = None
            else:
                logger.warning(f"⚠️ CryptoPanic API returned status {status} for {coin}: {payload}")
                        
            return headlines
            
        except asyncio.TimeoutError:
            logger.warning(f"⏳ CryptoPanic API timeout for {symbol}")
            return []
        except Exception as e:
            logger.error(f"❌ CryptoPanic client error for {symbol}: {e}")
            return []

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🔌 CryptoPanic API session closed.")
