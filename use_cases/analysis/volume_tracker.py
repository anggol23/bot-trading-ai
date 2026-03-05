"""
Volume Anomaly Tracker - Replaces Whale Alert.
Analyzes Indodax orderbook imbalances and massive single trades using Dynamic Z-Scores and Anti-Spoofing.
"""

import time
import numpy as np
from collections import deque
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from config.settings import Config
from core.interfaces.market_data_port import IMarketData
from core.interfaces.database_port import IDatabase
from utils.logger import get_logger

logger = get_logger(__name__)


class VolumeTracker:
    """
    On-chain alternative to Whale Alert using exchange orderbooks and trades.
    Identifies high-volume spikes using Dynamic Z-Score and detects Orderbook Spoofing.
    """
    def __init__(self, config: Config, market_data: IMarketData, db: IDatabase):
        self.config = config
        self.market = market_data
        self.db = db
        
        # Short-term memory for Anti-Spoofing
        self.ob_memory: Dict[str, deque] = {}  # symbol -> deque of recent max wall sizes
        self.spoof_blacklist: Dict[str, int] = {} # symbol -> expiry timestamp (ms)
    
    async def scan_anomalies(self, symbol: str):
        """Scan active market for volume spikes or extreme orderbook walls."""
        now_ms = int(time.time() * 1000)
        
        # Check if blacklisted due to spoofing
        if symbol in self.spoof_blacklist:
            if now_ms < self.spoof_blacklist[symbol]:
                return # Skip scanning
            else:
                logger.info(f"✅ SPOOFING PENALTY ENDED: {symbol} is removed from blacklist.")
                del self.spoof_blacklist[symbol]

        await self._check_large_trades(symbol)
        await self._check_orderbook_walls(symbol)

    async def _check_large_trades(self, symbol: str):
        """Fetch recent trades and flag anomalies using Dynamic Z-Score."""
        try:
            trades = await self.market.fetch_trades(symbol, limit=100)
            if not trades or len(trades) < 10:
                return

            # Extract costs directly in USD
            costs_usd = [(t.get("cost", 0) / 16000) for t in trades]
            
            # Calculate Dynamic Z-Score Base
            mean_vol = np.mean(costs_usd)
            std_vol = np.std(costs_usd)
            if std_vol == 0:
                std_vol = 1.0 # Prevent division by zero
                
            min_usd = self.config.volume_anomaly.min_usd_value
            z_threshold = self.config.volume_anomaly.z_score_threshold

            logged_spikes = 0
            for t, cost_usd in zip(trades, costs_usd):
                # Calculate Z-Score for this specific trade
                z_score = (cost_usd - mean_vol) / std_vol
                
                # USER RULE: Must have >3x volume spike
                volume_multiplier = cost_usd / mean_vol if mean_vol > 0 else 0
                
                # Must break historical variance (Z-Score) AND meet absolute minimums AND be >3x avg
                if z_score >= z_threshold and cost_usd >= min_usd and volume_multiplier >= 3.0:
                    event = {
                        "symbol": symbol,
                        "anomaly_type": "trade_spike",
                        "side": t.get("side", "unknown"),
                        "amount": t.get("amount", 0),
                        "price": t.get("price", 0),
                        "amount_usd": cost_usd,
                        "z_score": z_score,
                        "timestamp": t.get("timestamp", int(time.time() * 1000))
                    }
                    # Check if already saved (basic deduplication on timestamp/amount)
                    # We rely on DB or analysis layer to deduplicate if polled frequently.
                    self.db.save_volume_anomaly(event)
                    if logged_spikes < 3:
                        logger.info(f"🚨 WHALE TRADE [{symbol}]: {event['side']} ${cost_usd:,.0f} (Z-Score: {z_score:.1f})")
                        logged_spikes += 1

        except Exception as e:
            logger.error(f"Failed to scan large trades for {symbol}: {e}")

    async def _check_orderbook_walls(self, symbol: str):
        """Analyze orderbook depth to find massive bid/ask walls and detect spoofing."""
        try:
            # fetch top 50 levels
            ob = await self.market.fetch_order_book(symbol, limit=50)
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])
            
            if not bids or not asks:
                return
                
            current_price = bids[0][0]
            
            # Find the largest bid (Buy Wall)
            max_bid = max(bids, key=lambda x: x[1]*x[0]) if bids else [0, 0]
            bid_vol_usd = (max_bid[0] * max_bid[1]) / 16000
            
            # Find the largest ask (Sell Wall)
            max_ask = max(asks, key=lambda x: x[1]*x[0]) if asks else [0, 0]
            ask_vol_usd = (max_ask[0] * max_ask[1]) / 16000
            
            min_usd = self.config.volume_anomaly.min_usd_value
            now_ms = int(time.time() * 1000)
            
            if symbol not in self.ob_memory:
                self.ob_memory[symbol] = deque(maxlen=20)
                
            history = self.ob_memory[symbol]
            
            # Check for Spoofing (Massive wall disappeared without trade execution)
            # A wall is considered spoofed if it was huge, and suddenly drops by 80% 
            # while the price hasn't moved through it (no massive trade filled it).
            if len(history) > 0:
                last_state = history[-1]
                
                # Check Bid Spoofing
                if last_state['bid_vol'] > min_usd * 3 and bid_vol_usd < last_state['bid_vol'] * 0.2:
                    # Wall vanished. Did a big sell trade hit it? 
                    # If we don't see a recent giant sell anomaly, it's a spoof.
                    recent_anomalies = self.db.get_volume_anomalies(symbol, now_ms - 10000)
                    recent_sells = [a for a in recent_anomalies if a['side'] == 'sell' and a['amount_usd'] > min_usd]
                    
                    if not recent_sells:
                        logger.warning(f"⚠️ SPOOFING DETECTED! {symbol} Buy wall of ${last_state['bid_vol']:,.0f} vanished.")
                        self.spoof_blacklist[symbol] = now_ms + (self.config.volume_anomaly.spoofing_blacklist_seconds * 1000)
                        
                        self.db.save_volume_anomaly({
                            "symbol": symbol,
                            "anomaly_type": "spoofing_trap",
                            "side": "buy",
                            "amount": 0,
                            "price": last_state['bid_price'],
                            "amount_usd": last_state['bid_vol'],
                            "timestamp": now_ms
                        })
                        return # Stop processing
                        
                # Check Ask Spoofing
                if last_state['ask_vol'] > min_usd * 3 and ask_vol_usd < last_state['ask_vol'] * 0.2:
                    recent_anomalies = self.db.get_volume_anomalies(symbol, now_ms - 10000)
                    recent_buys = [a for a in recent_anomalies if a['side'] == 'buy' and a['amount_usd'] > min_usd]
                    
                    if not recent_buys:
                        logger.warning(f"⚠️ SPOOFING DETECTED! {symbol} Sell wall of ${last_state['ask_vol']:,.0f} vanished.")
                        self.spoof_blacklist[symbol] = now_ms + (self.config.volume_anomaly.spoofing_blacklist_seconds * 1000)
                        
                        self.db.save_volume_anomaly({
                            "symbol": symbol,
                            "anomaly_type": "spoofing_trap",
                            "side": "sell",
                            "amount": 0,
                            "price": last_state['ask_price'],
                            "amount_usd": last_state['ask_vol'],
                            "timestamp": now_ms
                        })
                        return # Stop processing

            # Save current state to memory
            history.append({
                "ts": now_ms,
                "bid_vol": bid_vol_usd,
                "ask_vol": ask_vol_usd,
                "bid_price": max_bid[0],
                "ask_price": max_ask[0]
            })
            
            # Save valid massive walls as valid anomalies
            if bid_vol_usd >= min_usd * 2: # Walls need to be thicker
                event = {
                    "symbol": symbol,
                    "anomaly_type": "orderbook_wall",
                    "side": "buy",
                    "amount": max_bid[1],
                    "price": max_bid[0],
                    "amount_usd": bid_vol_usd,
                    "z_score": 0.0,  # Z-score currently applies to trades, not walls directly
                    "timestamp": now_ms
                }
                self.db.save_volume_anomaly(event)
                logger.debug(f"🧱 BUY WALL: {symbol} ${event['amount_usd']:,.0f} at {max_bid[0]:,.0f}")
                
            if ask_vol_usd >= min_usd * 2: 
                event = {
                    "symbol": symbol,
                    "anomaly_type": "orderbook_wall",
                    "side": "sell",
                    "amount": max_ask[1],
                    "price": max_ask[0],
                    "amount_usd": ask_vol_usd,
                    "z_score": 0.0,
                    "timestamp": now_ms
                }
                self.db.save_volume_anomaly(event)
                logger.debug(f"🧱 SELL WALL: {symbol} ${event['amount_usd']:,.0f} at {max_ask[0]:,.0f}")
                
        except Exception as e:
            logger.error(f"Failed to scan orderbook walls for {symbol}: {e}")
