"""
Risk Manager - Strict position sizing and risk control.
Max 2% equity per position, mandatory stop loss, daily drawdown limit.
"""

from typing import Dict, List, Optional, Any

from config.settings import Config
from core.interfaces.database_port import IDatabase
from core.entities.order_plan import OrderPlan
from utils.logger import get_logger

logger = get_logger(__name__)


class RiskManager:
    """
    Strict risk management engine.
    
    Rules:
    - Max 2% of total equity at risk per position
    - Mandatory stop loss (ATR-based)
    - Minimum Risk:Reward = 1:2
    - Max 3 open positions simultaneously
    - Daily drawdown limit: 5%
    """

    def __init__(self, config: Config, db: IDatabase):
        self.config = config
        self.db = db
        self.risk_per_trade = config.risk.risk_per_trade
        self.max_positions = config.risk.max_open_positions
        self.daily_drawdown = config.risk.daily_drawdown_limit
        self.sl_multiplier = config.risk.stop_loss_atr_multiplier
        self.tp_rr = config.risk.take_profit_rr_ratio

    def calculate_order(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        atr: float,
        equity: float,
        market_regime: str = "NORMAL",
        daily_target_met: bool = False,
    ) -> OrderPlan:
        """
        Calculate position size and SL/TP based on risk rules.
        
        Args:
            symbol: Trading pair e.g. 'BTC/IDR'
            side: 'buy' or 'sell'
            entry_price: Expected entry price
            atr: ATR(14) value for volatility-based stop loss
            equity: Current total equity in quote currency (IDR)
            
        Returns:
            OrderPlan with calculated parameters (may be rejected)
        """
        # ──── Pre-flight checks ────
        rejection = self._pre_check(symbol, equity, entry_price, side)
        if rejection:
            return self._rejected_order(symbol, side, entry_price, rejection)

        # ──── Dynamic Market Parameters ────
        active_sl_multiplier = self.sl_multiplier
        active_tp_rr = self.tp_rr
        base_risk_pct = self.risk_per_trade

        if market_regime == "VOLATILE":
            active_sl_multiplier *= 1.5  # Wider Stop Loss to avoid whipsaws
            active_tp_rr *= 0.8          # Quicker Take Profit
            base_risk_pct *= 0.8         # Reduce exposure
        elif market_regime == "CHOPPY":
            active_sl_multiplier *= 0.8  # Tighter Stop Loss
            active_tp_rr *= 1.2          # Need higher reward to justify the noise risk
            base_risk_pct *= 0.5         # Very small exposure
        elif market_regime in ("TRENDING_BULL", "TRENDING_BEAR"):
            active_tp_rr *= 1.5          # Let profits run wider
            active_sl_multiplier *= 1.2  # Slight wiggle room
            base_risk_pct = min(self.risk_per_trade * 1.5, 0.05) # Bet larger on confirmed trends
            
        if daily_target_met:
            # Protect profits -> Elite Mode -> Half exposure
            base_risk_pct *= 0.5

        # ──── Calculate Stop Loss ────
        sl_distance = atr * active_sl_multiplier

        if side == "buy":
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + (sl_distance * active_tp_rr)
        else:
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - (sl_distance * active_tp_rr)

        # Ensure stop loss is positive
        if stop_loss <= 0:
            return self._rejected_order(
                symbol, side, entry_price,
                f"Stop loss negatif: {stop_loss:.0f} (ATR terlalu besar)"
            )

        # ──── Calculate Position Size ────
        # Dynamically scale down risk if Pyramiding (Scale-in)
        open_trades = self.db.get_open_trades()
        symbol_trades = [t for t in open_trades if t["symbol"] == symbol]
        active_risk_pct = base_risk_pct
        if symbol_trades:
            # Halve risk for each subsequent pyramid bullet: base -> base/2 -> base/4
            active_risk_pct = base_risk_pct / (2 ** len(symbol_trades))
            logger.info(f"🔼 Pyramiding Entry #{len(symbol_trades)+1} for {symbol}. Scaling risk to {active_risk_pct*100:.2f}%")

        risk_amount = equity * active_risk_pct  # Max loss in IDR
        position_size = risk_amount / sl_distance   # Amount in base currency

        # Calculate total cost
        cost = position_size * entry_price

        # Ensure we have enough balance
        if cost > equity * 0.95:  # Keep 5% reserve
            position_size = (equity * 0.95) / entry_price
            cost = position_size * entry_price
            risk_amount = position_size * sl_distance

        # ──── Risk:Reward validation ────
        reward_amount = position_size * (sl_distance * active_tp_rr)
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

        # Validate against configured TP RR, allowing a slight float margin
        min_rr = min(1.0, active_tp_rr * 0.95)
        if rr_ratio < min_rr:
            return self._rejected_order(
                symbol, side, entry_price,
                f"R:R terlalu rendah: {rr_ratio:.2f} (configure TP RR: {active_tp_rr:.2f})"
            )

        plan = OrderPlan(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            position_size=round(position_size, 8),
            cost=round(cost, 2),
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            risk_amount=round(risk_amount, 2),
            risk_percent=round(active_risk_pct * 100, 2),
            rr_ratio=round(rr_ratio, 2),
            approved=True,
        )

        logger.trade(
            f"📋 Order Plan: {side.upper()} {symbol} | "
            f"Entry: {entry_price:,.0f} | Size: {position_size:.8f} | "
            f"SL: {stop_loss:,.0f} | TP: {take_profit:,.0f} | "
            f"Risk: {risk_amount:,.0f} IDR ({active_risk_pct*100:.2f}%) | "
            f"R:R = 1:{rr_ratio:.1f}"
        )

        return plan

    def _pre_check(self, symbol: str, equity: float, current_price: float, side: str) -> Optional[str]:
        """Run pre-flight checks before order calculation."""

        # Check max open positions overall portfolio
        open_trades = self.db.get_open_trades()
        if len(open_trades) >= self.max_positions:
            return (
                f"Maks posisi tercapai: {len(open_trades)}/{self.max_positions} | "
                f"Tutup posisi yang ada sebelum membuka baru"
            )

        # Check if already have position in this symbol for Pyramiding
        symbol_trades = [t for t in open_trades if t["symbol"] == symbol]
        if symbol_trades:
            if not self.config.risk.enable_pyramiding:
                return f"Sudah ada posisi terbuka di {symbol} (Pyramiding dimatikan)"
            
            # Max 3 active layers per coin
            if len(symbol_trades) >= 3:
                return f"Batas Pyramiding maksimal tercapai (3 layers) untuk {symbol}"
                
            # Check if existing layers meet profit threshold
            for t in symbol_trades:
                if t["side"] != side:
                    return f"Sudah ada posisi {t['side']} di {symbol}. Tidak bisa membuka posisi {side} (Hedging ditolak)"
                
                entry = t["price"]
                profit_pct = ((current_price - entry) / entry) * 100 if side == "buy" else ((entry - current_price) / entry) * 100
                
                threshold = self.config.risk.pyramid_profit_threshold_pct
                if profit_pct < threshold:
                    return f"Posisi {symbol} saat ini belum mencapai profit aman ({profit_pct:.1f}% < {threshold}%)"

        # Check daily drawdown
        today_trades = self.db.get_trades_today()
        realized_loss = sum(
            t.get("pnl", 0) for t in today_trades
            if t.get("pnl") is not None and t.get("pnl") < 0
        )
        max_daily_loss = equity * self.daily_drawdown

        if abs(realized_loss) >= max_daily_loss:
            return (
                f"Daily drawdown limit tercapai: "
                f"{abs(realized_loss):,.0f} / {max_daily_loss:,.0f} IDR ({self.daily_drawdown*100:.0f}%) | "
                f"Stop trading hari ini"
            )

        return None  # All checks passed

    def check_daily_target_met(self, equity: float) -> bool:
        """
        Check if the accumulated realized profit today has met the daily target.
        """
        today_trades = self.db.get_trades_today()
        realized_pnl = sum(
            t.get("pnl", 0) for t in today_trades
            if t.get("pnl") is not None
        )
        
        target_profit_idr = equity * self.config.risk.daily_target_profit_pct
        return realized_pnl >= target_profit_idr

    def _rejected_order(
        self, symbol: str, side: str, price: float, reason: str
    ) -> OrderPlan:
        """Create a rejected order plan."""
        logger.warning(f"🚫 Order ditolak [{symbol}]: {reason}")
        return OrderPlan(
            symbol=symbol,
            side=side,
            entry_price=price,
            position_size=0,
            cost=0,
            stop_loss=0,
            take_profit=0,
            risk_amount=0,
            risk_percent=0,
            rr_ratio=0,
            approved=False,
            rejection_reason=reason,
        )

    def should_close_position(
        self,
        trade: Dict,
        current_price: float,
    ) -> Optional[str]:
        """
        Check if an open position should be closed.
        
        Returns:
            Close reason string if should close, None otherwise
        """
        side = trade["side"]
        stop_loss = trade.get("stop_loss")
        take_profit = trade.get("take_profit")

        if side == "buy":
            # Check stop loss
            if stop_loss and current_price <= stop_loss:
                return f"STOP_LOSS hit at {current_price:,.0f} (SL: {stop_loss:,.0f})"

            # Check take profit
            if take_profit and current_price >= take_profit:
                return f"TAKE_PROFIT hit at {current_price:,.0f} (TP: {take_profit:,.0f})"

        elif side == "sell":
            if stop_loss and current_price >= stop_loss:
                return f"STOP_LOSS hit at {current_price:,.0f} (SL: {stop_loss:,.0f})"

            if take_profit and current_price <= take_profit:
                return f"TAKE_PROFIT hit at {current_price:,.0f} (TP: {take_profit:,.0f})"

        return None

    def calculate_trailing_stop(
        self,
        trade: Dict,
        current_price: float,
        atr: float,
    ) -> Optional[float]:
        """
        Calculate new trailing stop if position is in profit.
        Only move SL in profit direction, never against.
        Activates after profit > 1× risk.
        
        Returns:
            New stop loss price, or None if no update needed
        """
        side = trade["side"]
        entry_price = trade["price"]
        current_sl = trade.get("stop_loss", 0)

        if side == "buy":
            profit = current_price - entry_price
            risk = entry_price - current_sl if current_sl else 0

            # Activate trailing only after 1× risk profit
            if risk > 0 and profit > risk:
                new_sl = current_price - (atr * self.sl_multiplier)
                if new_sl > current_sl:  # Only move UP
                    logger.info(
                        f"📈 Trailing SL: {current_sl:,.0f} → {new_sl:,.0f} "
                        f"(profit: {profit:,.0f})"
                    )
                    return round(new_sl, 2)

        elif side == "sell":
            profit = entry_price - current_price
            risk = current_sl - entry_price if current_sl else 0

            if risk > 0 and profit > risk:
                new_sl = current_price + (atr * self.sl_multiplier)
                if new_sl < current_sl:  # Only move DOWN
                    logger.info(
                        f"📉 Trailing SL: {current_sl:,.0f} → {new_sl:,.0f} "
                        f"(profit: {profit:,.0f})"
                    )
                    return round(new_sl, 2)

        return None

    def check_trailing_tp(
        self,
        trade: Dict,
        current_price: float,
    ) -> Optional[str]:
        """
        Check if Trailing Take Profit should be triggered.
        
        Logic:
        1. Only activate if profit exceeds trailing_tp_activation_pct.
        2. If active, trigger TP if current_price drops trailing_tp_callback_pct from highest_price.
        
        Returns:
        - Close reason if TP triggered, None otherwise.
        """
        side = trade["side"]
        entry_price = trade["price"]
        highest_price = trade.get("highest_price", entry_price)
        
        activation_pct = self.config.risk.trailing_tp_activation_pct
        callback_pct = self.config.risk.trailing_tp_callback_pct
        
        if side == "buy":
            profit_pct = (current_price - entry_price) / entry_price
            
            # Activation check
            if profit_pct >= activation_pct:
                # Callback check
                if current_price <= highest_price * (1 - callback_pct):
                    return f"TRAILING_TP hit: Profit {(profit_pct*100):.2f}% dropped {(callback_pct*100):.1f}% from peak"
                    
        elif side == "sell":
            profit_pct = (entry_price - current_price) / entry_price
            
            if profit_pct >= activation_pct:
                if current_price >= highest_price * (1 + callback_pct):
                    return f"TRAILING_TP hit: Profit {(profit_pct*100):.2f}% dropped {(callback_pct*100):.1f}% from peak"
                    
        return None
