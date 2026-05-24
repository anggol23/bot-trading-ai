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
    ai_decision: Optional[str] = None
    ai_reasoning: Optional[str] = None

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
    time: str
    value: float

class CandleResponse(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

class TradeHistoryResponse(BaseModel):
    id: int
    symbol: str
    side: str
    entry_price: float
    exit_price: Optional[float] = None
    amount: float
    cost: float
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    status: str          # 'open' or 'closed'
    mode: str            # 'paper' or 'live'
    close_reason: Optional[str] = None
    opened_at: str
    closed_at: Optional[str] = None
    duration_minutes: Optional[float] = None

class DailyTargetResponse(BaseModel):
    target_pct: float           # e.g. 1.0 (%)
    target_idr: float           # e.g. 96.79 IDR (1% of 9679)
    realized_pnl_today: float   # sum of closed PnL today
    progress_pct: float         # realized / target * 100 (capped at 100)
    status: str                 # "HUNTING" | "TARGET_MET" | "DRAWDOWN_LIMIT" | "NO_TRADES"
    daily_drawdown_pct: float
    drawdown_limit_pct: float
    equity: float
