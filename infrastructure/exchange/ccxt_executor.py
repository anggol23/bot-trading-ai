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
                
                # ─── Orderbook Depth Guard (Slippage Protection) ───
                try:
                    order_book = await self.market.fetch_order_book(plan.symbol, limit=20)
                    available_orders = order_book['asks'] if plan.side == 'buy' else order_book['bids']
                    
                    total_amount = 0.0
                    total_cost = 0.0
                    target_amount = plan.position_size
                    
                    for price, amount in available_orders:
                        if total_amount + amount >= target_amount:
                            # Fraction of the last order needed
                            remaining = target_amount - total_amount
                            total_cost += remaining * price
                            total_amount = target_amount
                            break
                        else:
                            total_cost += amount * price
                            total_amount += amount
                            
                    if total_amount < target_amount:
                        logger.warning(f"⚠️ Orderbook too thin for {plan.symbol}. Requested: {target_amount}, Available: {total_amount}")
                        return None
                        
                    avg_fill_price = total_cost / total_amount
                    slippage = abs(avg_fill_price - plan.entry_price) / plan.entry_price
                    
                    if slippage > self.config.risk.max_slippage_pct:
                        logger.warning(f"🛑 SLIPPAGE GUARD: {plan.symbol} {plan.side.upper()} rejected. Estimated slippage {slippage*100:.2f}% > max {self.config.risk.max_slippage_pct*100:.2f}%")
                        return None
                        
                    logger.info(f"🛡️ Slippage Check Passed: {plan.symbol} | Est: {slippage*100:.3f}% (Avg: {avg_fill_price:,.0f})")
                except Exception as e:
                    logger.error(f"⚠️ Failed to check orderbook for slippage, proceeding with caution: {e}")

                # Execute order via ccxt
                order_type = "market"
                order_params = {}
                
                if self.config.risk.enable_maker_only:
                    order_type = "limit"
                    # For buy, use current price (or slightly below) to be a maker
                    # For sell, use current price (or slightly above)
                    order_params = {"postOnly": True} # Ensure it only executes as maker
                    
                order = await self.market.exchange.create_order(
                    symbol=plan.symbol,
                    type=order_type,
                    side=plan.side,
                    amount=plan.position_size,
                    price=plan.entry_price if order_type == "limit" else None,
                    params=order_params
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

            except __import__('ccxt').ExchangeError as e:
                logger.error(f"❌ Exchange rejected LIVE order (NO RETRY): {e}")
                return None
            except __import__('ccxt').NetworkError as e:
                logger.error(f"🌐 Network error during LIVE order: {e}")
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 2
                    logger.info(f"⏳ Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"❌ All {max_retries} attempts failed for {plan.side.upper()} {plan.symbol}")
                    return None
            except Exception as e:
                logger.error(f"❌ Unexpected LIVE order failure: {e}")
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
                order_type = "market"
                order_params = {}
                
                if self.config.risk.enable_maker_only:
                    order_type = "limit"
                    order_params = {"postOnly": True}
                
                try:
                    await self.market.exchange.create_order(
                        symbol=symbol,
                        type=order_type,
                        side=close_side,
                        amount=trade["amount"],
                        price=current_price if order_type == "limit" else None,
                        params=order_params
                    )
                except __import__('ccxt').ExchangeError as e:
                    logger.error(f"⚠️ Exchange rejected close for {symbol}, forcing DB close to prevent Zombie Order: {e}")
                except Exception as e:
                    logger.error(f"❌ Network/Unknown error closing {symbol} on exchange (WILL RETRY NEXT TICK): {e}")
                    return False

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
