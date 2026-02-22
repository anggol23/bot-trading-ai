from dataclasses import dataclass
from typing import List

from core.entities.position_summary import PositionSummary


@dataclass
class PortfolioSummary:
    """Summary of entire portfolio state."""
    total_equity: float
    available_balance: float
    unrealized_pnl: float
    realized_pnl_today: float
    open_positions: int
    positions: List[PositionSummary]
    daily_drawdown_pct: float
    daily_drawdown_limit_pct: float
