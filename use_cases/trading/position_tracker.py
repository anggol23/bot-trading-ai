"""
Position Tracker - Monitors open positions, updates SL/TP, calculates P&L.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from config.settings import Config
from core.interfaces.database_port import IDatabase
from core.interfaces.market_data_port import IMarketData
from core.interfaces.executor_port import IExecutor
from use_cases.trading.risk_manager import RiskManager
from use_cases.analysis.volume_analyzer import VolumeAnalyzer
from core.entities.position_summary import PositionSummary
from core.entities.portfolio_summary import PortfolioSummary
from utils.logger import get_logger

logger = get_logger(__name__)


class PositionTracker:
    """
    Tracks open positions and manages portfolio state.
    
    Responsibilities:
    - Monitor open positions for SL/TP hits
    - Update trailing stops
    - Calculate unrealized P&L
    - Generate portfolio summaries
    """

    def __init__(
        self,
        config: Config,
        db: IDatabase,
        market_data: IMarketData,
        risk_manager: RiskManager,
        executor: IExecutor,
        volume_analyzer: VolumeAnalyzer = None,
    ):
        self.config = config
        self.db = db
        self.market = market_data
        self.risk_mgr = risk_manager
        self.executor = executor
        self.volume_analyzer = volume_analyzer
        self._initial_equity = None

    async def check_positions(self) -> List[str]:
        """
        Check all open positions for SL/TP hits and trailing stop updates.
        
        Returns:
            List of actions taken (for logging)
        """
        open_trades = self.db.get_open_trades()
        actions = []

        if not open_trades:
            return actions

        for trade in open_trades:
            try:
                symbol = trade["symbol"]
                side = trade["side"]

                # Get current price
                ticker = await self.market.fetch_ticker(symbol)
                current_price = ticker["last"]
                
                # Check Volume Exhaustion Trailing
                if self.config.risk.enable_volume_exhaustion and self.volume_analyzer:
                    vol_signal = self.volume_analyzer.analyze(symbol)
                    
                    if side == "buy" and vol_signal.net_flow == "DISTRIBUTING" and vol_signal.intensity in ["HIGH", "MEDIUM"]:
                        close_reason = f"VOLUME EXHAUSTION: Smart Money dumping ({vol_signal.confidence:.0f}% confidence)"
                        success = await self.executor.close_position(trade, current_price, close_reason)
                        if success:
                            actions.append(f"Force Closed {symbol}: {close_reason}")
                        continue
                        
                    elif side == "sell" and vol_signal.net_flow == "ACCUMULATING" and vol_signal.intensity in ["HIGH", "MEDIUM"]:
                        close_reason = f"VOLUME EXHAUSTION: Smart Money accumulating ({vol_signal.confidence:.0f}% confidence)"
                        success = await self.executor.close_position(trade, current_price, close_reason)
                        if success:
                            actions.append(f"Force Closed {symbol}: {close_reason}")
                        continue

                # ──── Trailing Take Profit (Peak-based) & Drawdown Tracking ────
                highest_price = trade.get("highest_price", trade["price"])
                max_drawdown = trade.get("max_drawdown", 0.0)
                updated_db = False
                
                if side == "buy":
                    if current_price > highest_price:
                        highest_price = current_price
                        updated_db = True
                    # Calculate drawdown from peak
                    current_dd = (highest_price - current_price) / highest_price if highest_price > 0 else 0
                    if current_dd > max_drawdown:
                        max_drawdown = current_dd
                        updated_db = True
                elif side == "sell":
                    if current_price < highest_price:
                        highest_price = current_price
                        updated_db = True
                    # Calculate drawdown from "peak" (which is the lowest price for shorts)
                    current_dd = (current_price - highest_price) / highest_price if highest_price > 0 else 0
                    if current_dd > max_drawdown:
                        max_drawdown = current_dd
                        updated_db = True
                
                if updated_db:
                    # We will reuse the update_trade_highest_price to also update max_drawdown, 
                    # but since the DB method is fixed, let's execute a direct query here to keep it simple
                    cursor = self.db.conn.cursor()
                    cursor.execute(
                        "UPDATE trades SET highest_price = ?, max_drawdown = ? WHERE id = ?",
                        (highest_price, max_drawdown, trade["id"])
                    )
                    self.db.conn.commit()
                    
                    trade["highest_price"] = highest_price # Update local dict for risk_mgr check
                    trade["max_drawdown"] = max_drawdown
                
                # Check Trailing TP hit
                close_reason = self.risk_mgr.check_trailing_tp(trade, current_price)
                if not close_reason:
                    # Check if should close (Standard SL or TP hit)
                    close_reason = self.risk_mgr.should_close_position(
                        trade, current_price
                    )

                if close_reason:
                    success = await self.executor.close_position(
                        trade, current_price, close_reason
                    )
                    if success:
                        actions.append(
                            f"Closed {symbol}: {close_reason}"
                        )
                    continue

                # Check trailing stop update
                # Need ATR for trailing calculation
                try:
                    df = await self.market.fetch_ohlcv(symbol, "1h", limit=50)
                    if df is not None and len(df) > 14:
                        import ta as ta_lib
                        atr = ta_lib.volatility.AverageTrueRange(
                            df["high"], df["low"], df["close"], window=14
                        ).average_true_range().iloc[-1]

                        new_sl = self.risk_mgr.calculate_trailing_stop(
                            trade, current_price, atr
                        )

                        if new_sl is not None:
                            # Update SL in database
                            cursor = self.db.conn.cursor()
                            cursor.execute(
                                "UPDATE trades SET stop_loss = ? WHERE id = ?",
                                (new_sl, trade["id"])
                            )
                            self.db.conn.commit()
                            actions.append(
                                f"Trailing SL {symbol}: {trade['stop_loss']:,.0f} → {new_sl:,.0f}"
                            )
                except Exception as e:
                    logger.warning(f"⚠️ Could not update trailing stop for {symbol}: {e}")

            except Exception as e:
                logger.error(f"❌ Error checking position {trade.get('symbol')}: {e}")

        return actions

    async def get_portfolio_summary(self, equity: Optional[float] = None) -> PortfolioSummary:
        """
        Generate a complete portfolio summary.
        
        Args:
            equity: Current total equity (if known). If None, will be calculated.
        """
        open_trades = self.db.get_open_trades()
        positions = []
        total_unrealized = 0.0

        for trade in open_trades:
            try:
                ticker = await self.market.fetch_ticker(trade["symbol"])
                current_price = ticker["last"]

                if trade["side"] == "buy":
                    unrealized = (current_price - trade["price"]) * trade["amount"]
                else:
                    unrealized = (trade["price"] - current_price) * trade["amount"]

                unrealized_pct = (unrealized / trade["cost"]) * 100 if trade["cost"] > 0 else 0
                total_unrealized += unrealized

                positions.append(PositionSummary(
                    trade_id=trade["id"],
                    symbol=trade["symbol"],
                    side=trade["side"],
                    entry_price=trade["price"],
                    current_price=current_price,
                    amount=trade["amount"],
                    cost=trade["cost"],
                    stop_loss=trade.get("stop_loss", 0),
                    take_profit=trade.get("take_profit", 0),
                    unrealized_pnl=round(unrealized, 2),
                    unrealized_pnl_pct=round(unrealized_pct, 2),
                    mode=trade.get("mode", "paper"),
                ))
            except Exception as e:
                logger.warning(f"⚠️ Could not get price for {trade['symbol']}: {e}")

        # Calculate daily realized P&L
        today_trades = self.db.get_trades_today()
        realized_today = sum(
            t.get("pnl", 0) for t in today_trades
            if t.get("pnl") is not None
        )

        # Equity calculation
        total_idr = 0
        free_idr = 0

        if equity is None:
            if self.config.trading.mode == "paper":
                # In paper trading, equity is starting balance + realized PnL
                total_idr = 300_000 + realized_today
                free_idr = total_idr - sum(t["cost"] for t in open_trades)
            else:
                try:
                    balance = await self.market.fetch_balance()
                    total_idr = balance.get("total", {}).get("IDR", 0)
                    free_idr = balance.get("free", {}).get("IDR", 0)
                except Exception:
                    total_idr = 0
                    free_idr = 0
        else:
            total_idr = equity
            free_idr = equity - sum(t["cost"] for t in open_trades)

        if self._initial_equity is None:
            self._initial_equity = total_idr

        # Daily drawdown
        # The original instruction implies a property, but the context is a local calculation.
        # We'll apply the safe division logic to the existing calculation.
        current_total_equity = total_idr + total_unrealized
        if self._initial_equity == 0: # Handle initial equity being zero to prevent division by zero
            daily_dd = 0.0
        else:
            daily_dd = abs(min(0, realized_today)) / self._initial_equity * 100
        
        dd_limit = self.config.risk.daily_drawdown_limit * 100

        # Save snapshot
        self.db.save_portfolio_snapshot({
            "total_equity": current_total_equity,
            "available_balance": free_idr,
            "unrealized_pnl": total_unrealized,
            "realized_pnl_today": realized_today,
            "open_positions": len(positions),
        })

        return PortfolioSummary(
            total_equity=round(current_total_equity, 2),
            available_balance=round(free_idr, 2),
            unrealized_pnl=round(total_unrealized, 2),
            realized_pnl_today=round(realized_today, 2),
            open_positions=len(positions),
            positions=positions,
            daily_drawdown_pct=round(daily_dd, 2),
            daily_drawdown_limit_pct=dd_limit,
        )
