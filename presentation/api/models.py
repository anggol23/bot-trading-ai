from pydantic import BaseModel
from typing import List, Optional, Any

class PortfolioSummaryResponse(BaseModel):
    total_equity: float
    available_balance: float
    unrealized_pnl: float
    realized_pnl_today: float
    open_positions: int
    daily_drawdown_pct: float

class PositionResponse(BaseModel):
    id: int
    symbol: str
    side: str
    entry_price: float
    current_price: float
    stop_loss: float
    take_profit: float
    unrealized_pnl: float
    unrealized_pnl_pct: float

class SignalResponse(BaseModel):
    id: int
    symbol: str
    action: str
    confidence: float
    reason: str
    timestamp: str

class VolumeAnomalyResponse(BaseModel):
    id: int
    symbol: str
    type: str # 'TRADE_SPIKE' or 'ORDERBOOK_IMBALANCE'
    side: str
    amount_usd: float
    z_score: float
    imbalance_ratio: float
    timestamp: str

class ChartDataPoint(BaseModel):
    time: str # Format "YYYY-MM-DD" or timestamp
    value: float # Equity or PnL
