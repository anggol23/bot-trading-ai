"""
Order Executor - Executes trades via ccxt (paper or live mode).
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional

from config.settings import Config
from core.interfaces.market_data_port import IMarketData
from core.interfaces.database_port import IDatabase
from core.interfaces.executor_port import IExecutor
from core.entities.order_plan import OrderPlan
from utils.logger import get_logger

logger = get_logger(__name__)


class OrderExecutor(IExecutor):
    """
    Executes trading orders in paper or live mode.
    
    Paper mode: simulates order without real execution
    Live mode: sends real orders via ccxt to Indodax
    """

    def __init__(self, config: Config, market_data: IMarketData, db: IDatabase):
        self.config = config
        self.market = market_data
        self.db = db
        self.mode = config.trading.mode

    async def execute(self, plan: OrderPlan) -> Optional[Dict[str, Any]]:
        """
        Execute an order plan.
        
        Args:
            plan: Approved OrderPlan from RiskManager
            
        Returns:
            Trade dict if executed, None if rejected
        """
        if not plan.approved:
            logger.warning(
                f"🚫 Order not approved: {plan.rejection_reason}"
            )
            return None

        if self.mode == "paper":
            return await self._execute_paper(plan)
        elif self.mode == "live":
            return await self._execute_live(plan)
        else:
            logger.error(f"❌ Unknown trading mode: {self.mode}")
            return None

    async def _execute_paper(self, plan: OrderPlan) -> Dict[str, Any]:
        """Simulate order execution (paper trading)."""
        trade = {
            "symbol": plan.symbol,
            "side": plan.side,
            "order_type": "market",
            "price": plan.entry_price,
            "amount": plan.position_size,
            "cost": plan.cost,
            "stop_loss": plan.stop_loss,
            "take_profit": plan.take_profit,
            "status": "open",
            "mode": "paper",
        }

        trade_id = self.db.save_trade(trade)
        trade["id"] = trade_id

        logger.trade(
            f"📝 PAPER {plan.side.upper()} {plan.symbol} | "
            f"Price: {plan.entry_price:,.0f} | Amount: {plan.position_size:.8f} | "
            f"Cost: {plan.cost:,.0f} IDR | "
            f"SL: {plan.stop_loss:,.0f} | TP: {plan.take_profit:,.0f}"
        )

        return trade

    async def _execute_live(self, plan: OrderPlan) -> Optional[Dict[str, Any]]:
        """Execute real order via ccxt to Indodax."""
        if not self.config.indodax.api_key:
            logger.error("❌ Cannot execute live order: No API key configured")
            return None

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"⚡ LIVE ORDER: {plan.side.upper()} {plan.symbol} | "
                    f"Amount: {plan.position_size:.8f} | "
                    f"Attempt {attempt + 1}/{max_retries}"
                )

                # Execute market order via ccxt
                import asyncio
                # Use standard retry with async sleep
                order = await self.market.exchange.create_order(
                    symbol=plan.symbol,
                    type="market",
                    side=plan.side,
                    amount=plan.position_size,
                )

                # Save to database
                trade = {
                    "symbol": plan.symbol,
                    "side": plan.side,
                    "order_type": "market",
                    "price": order.get("average", order.get("price", plan.entry_price)),
                    "amount": order.get("filled", plan.position_size),
                    "cost": order.get("cost", plan.cost),
                    "stop_loss": plan.stop_loss,
                    "take_profit": plan.take_profit,
                    "status": "open",
                    "mode": "live",
                }

                trade_id = self.db.save_trade(trade)
                trade["id"] = trade_id
                trade["order_id"] = order.get("id")

                logger.trade(
                    f"💰 LIVE {plan.side.upper()} {plan.symbol} EXECUTED | "
                    f"Price: {trade['price']:,.0f} | Amount: {trade['amount']:.8f} | "
                    f"Cost: {trade['cost']:,.0f} IDR | "
                    f"Order ID: {order.get('id')}"
                )

                return trade

            except Exception as e:
                logger.error(
                    f"❌ Live order attempt {attempt + 1} failed: {e}"
                )
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 2  # Exponential backoff
                    logger.info(f"⏳ Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        f"❌ All {max_retries} attempts failed for "
                        f"{plan.side.upper()} {plan.symbol}"
                    )
                    return None

    async def close_position(
        self,
        trade: Dict[str, Any],
        current_price: float,
        reason: str,
    ) -> bool:
        """
        Close an open position.
        
        Args:
            trade: Open trade dict from database
            current_price: Current market price
            reason: Reason for closing (STOP_LOSS, TAKE_PROFIT, SIGNAL, MANUAL)
            
        Returns:
            True if closed successfully
        """
        trade_id = trade["id"]
        symbol = trade["symbol"]
        side = trade["side"]

        try:
            if self.mode == "live":
                # Execute opposite order to close
                close_side = "sell" if side == "buy" else "buy"
                await self.market.exchange.create_order(
                    symbol=symbol,
                    type="market",
                    side=close_side,
                    amount=trade["amount"],
                )

            # Update database
            self.db.close_trade(trade_id, current_price, reason)

            # Calculate P&L for logging
            if side == "buy":
                pnl = (current_price - trade["price"]) * trade["amount"]
            else:
                pnl = (trade["price"] - current_price) * trade["amount"]

            pnl_pct = (pnl / trade["cost"]) * 100 if trade["cost"] > 0 else 0
            emoji = "✅" if pnl > 0 else "❌"

            logger.trade(
                f"{emoji} CLOSED {symbol} ({reason}) | "
                f"Entry: {trade['price']:,.0f} → Exit: {current_price:,.0f} | "
                f"P&L: {pnl:+,.0f} IDR ({pnl_pct:+.2f}%)"
            )

            return True

        except Exception as e:
            logger.error(f"❌ Failed to close position {trade_id}: {e}")
            return False
