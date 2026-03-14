"""
Order Executor - Executes trades via ccxt (paper or live mode).
"""

import time
import math
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

        min_order_idr = float(self.config.risk.min_order_idr)

        # ─── Pre-flight: Minimum Order Validation ───
        if plan.cost < min_order_idr:
            logger.error(
                f"❌ Order DITOLAK {plan.symbol}: Cost {plan.cost:,.0f} IDR "
                f"< minimum order Indodax {min_order_idr:,.0f} IDR. "
                f"Top up saldo atau naikkan RISK_PER_TRADE."
            )
            return None

        # ─── Pre-flight: Floor amount for cheap coins (harga < 1 IDR) ───
        # Indodax menolak decimal amount untuk coin seperti PEPE
        final_amount = plan.position_size
        if plan.entry_price > 0 and plan.entry_price < 1.0:
            final_amount = math.floor(plan.position_size)
            if final_amount <= 0:
                logger.error(
                    f"❌ Order DITOLAK {plan.symbol}: Amount setelah floor = 0 "
                    f"(original: {plan.position_size:.2f}). Saldo tidak cukup."
                )
                return None
            logger.info(
                f"🔢 Flooring amount {plan.symbol}: {plan.position_size:.8f} → {final_amount} "
                f"(coin harga {plan.entry_price:.6f} IDR < 1 IDR)"
            )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"⚡ LIVE ORDER: {plan.side.upper()} {plan.symbol} | "
                    f"Amount: {final_amount} | "
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
                    
                # Fix indodax API rejecting pairs without underscore
                if "indodax" in str(self.market.exchange.id).lower():
                    order_params["pair"] = plan.symbol.replace("/", "_").lower()

                # Indodax CCXT requires price even for market buy orders
                order = await self.market.exchange.create_order(
                    symbol=plan.symbol,
                    type=order_type,
                    side=plan.side,
                    amount=final_amount,
                    price=plan.entry_price,
                    params=order_params
                )

                # Indodax CCXT often returns None for average/price/filled/cost on market orders
                order_price = order.get("average") or order.get("price") or plan.entry_price
                order_amount = order.get("filled") or final_amount
                order_cost = order.get("cost") or (order_amount * order_price)

                # Save to database
                trade = {
                    "symbol": plan.symbol,
                    "side": plan.side,
                    "order_type": "market",
                    "price": order_price,
                    "amount": order_amount,
                    "cost": order_cost,
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
                
                # Fix indodax API rejecting pairs without underscore
                if "indodax" in str(self.market.exchange.id).lower():
                    order_params["pair"] = symbol.replace("/", "_").lower()
                
                try:
                    await self.market.exchange.create_order(
                        symbol=symbol,
                        type=order_type,
                        side=close_side,
                        amount=trade["amount"],
                        price=current_price,
                        params=order_params
                    )
                except __import__('ccxt').ExchangeError as e:
                    error_msg = str(e).lower()
                    if "insufficient balance" in error_msg:
                        logger.warning(f"⚠️ Indodax rejected close for {symbol} due to insufficient balance. Fetching actual balance to retry...")
                        try:
                            # Usually symbol is "BTC/IDR", base is "BTC"
                            base_coin = symbol.split('/')[0]
                            balance = await self.market.exchange.fetch_balance()
                            free_balance = balance.get(base_coin, {}).get("free", 0.0)
                            
                            if free_balance > 0:
                                logger.info(f"🔄 Retrying close {symbol} with actual free balance: {free_balance} {base_coin} (Original target: {trade['amount']})")
                                trade["amount"] = free_balance # Update the local trade dict to reflect the actual sold amount
                                await self.market.exchange.create_order(
                                    symbol=symbol,
                                    type=order_type,
                                    side=close_side,
                                    amount=free_balance,
                                    price=current_price,
                                    params=order_params
                                )
                            else:
                                logger.warning(f"⚠️ Actual free balance for {base_coin} is 0. Asset likely already sold elsewhere or stranded. Forcing DB close.")
                        except Exception as retry_e:
                            logger.error(f"❌ Failed to close {symbol} even after fetching manual balance: {retry_e}")
                            return False
                    else:
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
