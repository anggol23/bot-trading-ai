from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from presentation.api.database import (
    get_portfolio_summary,
    get_active_positions,
    get_recent_signals,
    get_volume_anomalies,
    get_equity_curve,
    get_latest_candles
)
from presentation.api.models import (
    PortfolioSummaryResponse,
    PositionResponse,
    SignalResponse,
    VolumeAnomalyResponse,
    ChartDataPoint,
    CandleResponse
)
from typing import List

app = FastAPI(
    title="AI Trading Agent Dashboard API",
    description="Backend API for the AI Trading Web Dashboard",
    version="1.0.0"
)

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to localhost:5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/portfolio", response_model=PortfolioSummaryResponse)
def api_portfolio_summary():
    """Get the latest portfolio summary."""
    return get_portfolio_summary()

@app.get("/api/positions", response_model=List[PositionResponse])
def api_active_positions():
    """Get all open trading positions."""
    return get_active_positions()

@app.get("/api/signals", response_model=List[SignalResponse])
def api_recent_signals(limit: int = 20):
    """Get the most recent AI generated signals."""
    return get_recent_signals(limit)

@app.get("/api/volume", response_model=List[VolumeAnomalyResponse])
def api_volume_anomalies(limit: int = 20):
    """Get the most recent detected volume anomalies."""
    return get_volume_anomalies(limit)

@app.get("/api/equity", response_model=List[ChartDataPoint])
def api_equity_curve():
    """Get the historical equity curve data for charting."""
    return get_equity_curve()

@app.get("/api/candles/{symbol}", response_model=List[CandleResponse])
def api_candles(symbol: str, timeframe: str = "15m", limit: int = 100):
    """Get historical OHLCV candles for charting."""
    # Handle api paths like SOL-IDR converting it to SOL/IDR 
    symbol = symbol.replace('-', '/').upper()
    return get_latest_candles(symbol, timeframe, limit)
