from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class OrderPlan:
    """Calculated order with risk-managed parameters."""
    symbol: str
    side: str           # "buy" or "sell"
    entry_price: float
    position_size: float  # Amount in base currency (e.g. BTC)
    cost: float          # Total cost in quote currency (e.g. IDR)
    stop_loss: float
    take_profit: float
    risk_amount: float   # Max loss in quote currency
    risk_percent: float  # Risk as % of equity
    rr_ratio: float      # Risk:Reward ratio

    approved: bool = True
    rejection_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_price": self.entry_price,
            "position_size": self.position_size,
            "cost": self.cost,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_amount": self.risk_amount,
            "risk_percent": self.risk_percent,
            "rr_ratio": self.rr_ratio,
            "approved": self.approved,
            "rejection_reason": self.rejection_reason,
        }
