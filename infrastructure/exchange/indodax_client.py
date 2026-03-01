"""
Market Data Fetcher - OHLCV & exchange data via ccxt.async_support.
Connects to Indodax exchange and fetches price data for analysis concurrently.
"""

import time
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

from core.interfaces.market_data_port import IMarketData
from config.settings import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class MarketDataFetcher(IMarketData):
    """Fetches market data from Indodax via ccxt."""

    def __init__(self, config: Config):
        self.config = config

        # Initialize ccxt Indodax exchange
        exchange_params = {
            "enableRateLimit": True,
            "timeout": 30000,
        }

        if config.indodax.api_key and config.indodax.secret:
            exchange_params["apiKey"] = config.indodax.api_key
            exchange_params["secret"] = config.indodax.secret

        self.exchange = ccxt.indodax(exchange_params)
        self._markets_loaded = False

    async def _ensure_markets(self):
        """Load markets if not already loaded."""
        if not self._markets_loaded:
            try:
                await self.exchange.load_markets()
                self._markets_loaded = True
                logger.info(f"📡 Loaded {len(self.exchange.markets)} markets from Indodax")
            except Exception as e:
                logger.error(f"❌ Failed to load markets: {e}")
                raise

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 200,
        since: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candle data from Indodax.
        
        Args:
            symbol: Trading pair e.g. 'BTC/IDR'
            timeframe: Candle timeframe e.g. '1h', '4h', '1d'
            limit: Number of candles to fetch (max ~1000)
            since: Start timestamp in ms (optional)
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        await self._ensure_markets()

        try:
            logger.info(f"📊 Fetching {limit} x {timeframe} candles for {symbol}")

            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                since=since,
            )

            if not ohlcv:
                logger.warning(f"⚠️ No OHLCV data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            # Convert timestamp from ms to datetime
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("datetime", inplace=True)

            logger.info(
                f"✅ Got {len(df)} candles for {symbol} "
                f"({df.index[0]} → {df.index[-1]})"
            )

            return df

        except ccxt.NetworkError as e:
            logger.error(f"🌐 Network error fetching OHLCV for {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"🏦 Exchange error fetching OHLCV for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching OHLCV for {symbol}: {e}")
            raise

    async def fetch_multi_timeframe(
        self, symbol: str, timeframes: List[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for multiple timeframes simultaneously.
        Used for multi-timeframe confirmation.
        """
        if timeframes is None:
            timeframes = ["1h", "4h", "1d"]

        results = {}
        
        # Create concurrent tasks
        tasks = []
        for tf in timeframes:
            tasks.append(self.fetch_ohlcv(symbol, tf))
            
        # Await all simultaneously
        dfs = await asyncio.gather(*tasks, return_exceptions=True)
        
        for tf, df_result in zip(timeframes, dfs):
            if isinstance(df_result, Exception):
                logger.error(f"Failed to fetch {tf} for {symbol}: {df_result}")
                results[tf] = pd.DataFrame()
            else:
                results[tf] = df_result

        return results

    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch current ticker data for a symbol.

        Returns:
            Dict with: last, bid, ask, high, low, volume, etc.

        Note:
            Some micro-cap coins on Indodax (e.g. PEPE) return last=0 due to
            precision/rounding in their API. We fall back to orderbook mid-price
            when this occurs so that downstream price-dependent logic (ATR, SL/TP)
            can proceed correctly.
        """
        await self._ensure_markets()

        try:
            ticker = await self.exchange.fetch_ticker(symbol)

            last_price = ticker.get("last") or 0

            # ── Fallback: derive price from orderbook mid-price ──────────────
            if last_price <= 0:
                logger.warning(
                    f"⚠️ {symbol} ticker last={last_price} — attempting orderbook fallback"
                )
                try:
                    ob = await self.exchange.fetch_order_book(symbol, limit=5)
                    best_bid = ob["bids"][0][0] if ob.get("bids") else 0
                    best_ask = ob["asks"][0][0] if ob.get("asks") else 0
                    if best_bid > 0 and best_ask > 0:
                        last_price = (best_bid + best_ask) / 2
                        ticker["last"] = last_price
                        ticker["bid"] = best_bid
                        ticker["ask"] = best_ask
                        logger.info(
                            f"✅ {symbol} price derived from orderbook mid-price: "
                            f"{last_price:,.6f} IDR (bid={best_bid:,.6f} / ask={best_ask:,.6f})"
                        )
                    else:
                        logger.error(
                            f"❌ {symbol} orderbook fallback failed — no valid bid/ask"
                        )
                except Exception as ob_err:
                    logger.error(
                        f"❌ {symbol} orderbook fallback error: {ob_err}"
                    )
            else:
                logger.info(
                    f"💹 {symbol} Last: {last_price:,.6f} IDR | "
                    f"Vol24h: {ticker.get('baseVolume', 0):,.4f}"
                )

            return ticker

        except Exception as e:
            logger.error(f"❌ Failed to fetch ticker for {symbol}: {e}")
            raise

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        """
        Fetch order book depth.
        
        Returns:
            Dict with 'bids' and 'asks' arrays.
        """
        await self._ensure_markets()

        try:
            order_book = await self.exchange.fetch_order_book(symbol, limit)
            bid_vol = sum([b[1] for b in order_book["bids"][:10]])
            ask_vol = sum([a[1] for a in order_book["asks"][:10]])
            ratio = bid_vol / ask_vol if ask_vol > 0 else 0

            logger.info(
                f"📗 {symbol} OrderBook — "
                f"Bid Vol: {bid_vol:.4f} | Ask Vol: {ask_vol:.4f} | "
                f"B/A Ratio: {ratio:.2f}"
            )
            return order_book
        except Exception as e:
            logger.error(f"❌ Failed to fetch order book for {symbol}: {e}")
            raise

    async def fetch_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch recent public trades for a symbol.
        Used to detect volume anomalies and spikes.
        """
        await self._ensure_markets()
        try:
            trades = await self.exchange.fetch_trades(symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"❌ Failed to fetch trades for {symbol}: {e}")
            return []

    async def fetch_balance(self) -> Dict[str, Any]:
        """
        Fetch account balance (requires API key).
        
        Returns:
            Dict with balance info per currency.
        """
        await self._ensure_markets()
        if not self.config.indodax.api_key:
            logger.warning("⚠️ No API key — returning mock balance for paper trading")
            return {
                "total": {"IDR": 10_000_000},
                "free": {"IDR": 10_000_000},
                "used": {"IDR": 0},
            }

        try:
            balance = await self.exchange.fetch_balance()
            idr_total = balance.get("total", {}).get("IDR", 0)
            logger.info(f"💰 Balance: {idr_total:,.0f} IDR")
            return balance
        except Exception as e:
            logger.error(f"❌ Failed to fetch balance: {e}")
            raise

    async def get_available_pairs(self) -> List[str]:
        """Get all available trading pairs on Indodax."""
        await self._ensure_markets()
        pairs = list(self.exchange.markets.keys())
        idr_pairs = [p for p in pairs if p.endswith("/IDR")]
        logger.info(f"📋 Available IDR pairs: {len(idr_pairs)}")
        return idr_pairs

    async def validate_pairs(self, pairs: List[str]) -> List[str]:
        """Validate that requested pairs exist on the exchange."""
        available = await self.get_available_pairs()
        valid = []
        for pair in pairs:
            if pair in available:
                valid.append(pair)
            else:
                logger.warning(f"⚠️ Pair {pair} not available on Indodax — skipping")
        return valid

    async def close(self):
        """Close the CCXT exchange connection properly."""
        if hasattr(self, 'exchange'):
            await self.exchange.close()
            logger.info("🔌 CCXT Indodax exchange session closed.")
