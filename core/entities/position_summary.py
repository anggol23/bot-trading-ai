from dataclasses import dataclass


@dataclass
class PositionSummary:
    """Summary of a single open position."""
    trade_id: int
    symbol: str
    side: str
    entry_price: float
    current_price: float
    amount: float
    cost: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    mode: str
