import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from presentation.api.models import (
    PortfolioSummaryResponse, PositionResponse, SignalResponse,
    VolumeAnomalyResponse, ChartDataPoint, CandleResponse,
    TradeHistoryResponse, DailyTargetResponse
)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "trading_agent.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_portfolio_summary() -> PortfolioSummaryResponse:
    # Read the latest state from DB or calculate it
    # Since PortfolioSummary in main process calculates it dynamically via ccxt,
    # the web server should ideally read cached values from DB.
    # We will fetch latest closed trades for realized PnL and active trades for unrealized.
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Realized PnL Today
    c.execute("""
        SELECT SUM(pnl) as today_pnl 
        FROM trades 
        WHERE status = 'closed' 
        AND DATE(closed_at) = DATE('now')
    """)
    row = c.fetchone()
    realized_pnl = float(row['today_pnl']) if row and row['today_pnl'] else 0.0
    
    # 2. Open Positions
    c.execute("""
        SELECT * FROM trades WHERE status = 'open'
    """)
    open_positions = c.fetchall()
    
    # Since we can't easily fetch live price from ccxt synchronously in this API 
    # without delaying response, we'll return the DB state. 
    # Unrealized PNL requires live prices. The Trading Agent main loop will update 
    # a new table `portfolio_snapshots` which we will query instead.
    
    c.execute("SELECT * FROM portfolio_snapshots ORDER BY snapshot_at DESC LIMIT 1")
    snap = c.fetchone()
    
    conn.close()
    
    if snap:
        return PortfolioSummaryResponse(
            total_equity=snap['total_equity'],
            available_balance=snap['available_balance'],
            unrealized_pnl=snap['unrealized_pnl'],
            realized_pnl_today=realized_pnl,
            open_positions=len(open_positions),
            daily_drawdown_pct=0.0
        )
    else:
        return PortfolioSummaryResponse(
            total_equity=300000.0,
            available_balance=300000.0,
            unrealized_pnl=0,
            realized_pnl_today=realized_pnl,
            open_positions=len(open_positions),
            daily_drawdown_pct=0.0
        )

def get_active_positions() -> List[PositionResponse]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at DESC")
    rows = c.fetchall()
    conn.close()
    
    import random
    positions = []
    for r in rows:
        # For simulation, slightly randomize current price around entry price
        current_p = r['price'] * random.uniform(0.95, 1.05)
        unrealized = (current_p - r['price']) * r['amount'] if r['side'] == 'buy' else (r['price'] - current_p) * r['amount']
        unrealized_pct = (unrealized / r['cost']) * 100 if r['cost'] > 0 else 0
        
        positions.append(PositionResponse(
            id=r['id'],
            symbol=r['symbol'],
            side=r['side'],
            entry_price=r['price'],
            current_price=current_p,
            stop_loss=r['stop_loss'],
            take_profit=r['take_profit'],
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=unrealized_pct
        ))
    return positions

def get_recent_signals(limit: int = 10) -> List[SignalResponse]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM signals ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    return [SignalResponse(
        id=r['id'],
        symbol=r['symbol'],
        action=r['combined_action'],
        confidence=r['combined_confidence'],
        reason=f"Tech: {r['technical_trend']} | Vol: {r['volume_flow']}",
        timestamp=r['created_at'],
        ai_decision=r['ai_decision'],
        ai_reasoning=r['ai_reasoning']
    ) for r in rows]

def get_volume_anomalies(limit: int = 10) -> List[VolumeAnomalyResponse]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM volume_anomalies ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    anomalies = []
    for r in rows:
        row_dict = dict(r)
        anomalies.append(VolumeAnomalyResponse(
            id=row_dict['id'],
            symbol=row_dict['symbol'],
            type=row_dict['anomaly_type'],
            side=row_dict['side'],
            amount_usd=row_dict['amount_usd'],
            z_score=row_dict.get('z_score', 0.0),
            imbalance_ratio=0.0,
            timestamp=datetime.fromtimestamp(row_dict['timestamp']/1000.0).isoformat() if isinstance(row_dict['timestamp'], (int, float)) else str(row_dict['timestamp'])
        ))
    return anomalies

def get_equity_curve(days: int = None) -> List[ChartDataPoint]:
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT snapshot_at, total_equity FROM portfolio_snapshots"
    params = []
    
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query += " WHERE snapshot_at >= ?"
        params.append(cutoff.isoformat())
        
    query += " ORDER BY snapshot_at ASC"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return [ChartDataPoint(
        time=r['snapshot_at'],
        value=r['total_equity']
    ) for r in rows]

def get_latest_candles(symbol: str, timeframe: str = "1h", limit: int = 100) -> List[CandleResponse]:
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT timestamp, open, high, low, close, volume 
        FROM candles 
        WHERE symbol = ? AND timeframe = ?
        ORDER BY timestamp DESC LIMIT ?
    """, (symbol, timeframe, limit))
    rows = c.fetchall()
    conn.close()
    
    # Needs to be returned in ascending order for the chart (from oldest to newest)
    candles = []
    for r in reversed(rows):
        row_dict = dict(r)
        
        # Convert millis timestamp to ISO string if needed by apexcharts,
        # or just pass timestamp if chart formatter handles it
        t_ms = row_dict['timestamp']
        if isinstance(t_ms, str):
            t_iso = t_ms
        else:
            t_iso = datetime.fromtimestamp(t_ms/1000.0).isoformat()
            
        candles.append(CandleResponse(
            timestamp=t_iso,
            open=row_dict['open'],
            high=row_dict['high'],
            low=row_dict['low'],
            close=row_dict['close'],
            volume=row_dict['volume']
        ))
        
    return candles


def get_trade_history(limit: int = 50) -> List[TradeHistoryResponse]:
    """Get all trades (open + closed) ordered by most recent first."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, symbol, side, price, amount, cost,
               stop_loss, take_profit, pnl, pnl_percent,
               status, mode, close_reason,
               opened_at, closed_at, close_price
        FROM trades
        ORDER BY opened_at DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    result = []
    for r in rows:
        # Calculate duration
        duration_minutes = None
        if r['closed_at'] and r['opened_at']:
            try:
                opened = datetime.fromisoformat(r['opened_at'].replace('Z', '+00:00'))
                closed = datetime.fromisoformat(r['closed_at'].replace('Z', '+00:00'))
                duration_minutes = round((closed - opened).total_seconds() / 60, 1)
            except Exception:
                duration_minutes = None

        result.append(TradeHistoryResponse(
            id=r['id'],
            symbol=r['symbol'],
            side=r['side'],
            entry_price=float(r['price'] or 0),
            exit_price=float(r['close_price']) if r['close_price'] else None,
            amount=float(r['amount'] or 0),
            cost=float(r['cost'] or 0),
            pnl=float(r['pnl']) if r['pnl'] is not None else None,
            pnl_percent=float(r['pnl_percent']) if r['pnl_percent'] is not None else None,
            status=r['status'],
            mode=r['mode'],
            close_reason=r['close_reason'],
            opened_at=str(r['opened_at']),
            closed_at=str(r['closed_at']) if r['closed_at'] else None,
            duration_minutes=duration_minutes,
        ))
    return result


def get_daily_target_status() -> DailyTargetResponse:
    """Calculate daily target progress based on today's realized PnL."""
    from config.settings import Config
    config = Config()

    conn = get_db_connection()
    c = conn.cursor()

    # Realized PnL today
    c.execute("""
        SELECT SUM(pnl) as today_pnl
        FROM trades
        WHERE status = 'closed'
        AND DATE(closed_at) = DATE('now')
    """)
    row = c.fetchone()
    realized_pnl_today = float(row['today_pnl']) if row and row['today_pnl'] else 0.0

    # Realized losses today (for drawdown calc)
    c.execute("""
        SELECT SUM(pnl) as today_loss
        FROM trades
        WHERE status = 'closed'
        AND DATE(closed_at) = DATE('now')
        AND pnl < 0
    """)
    row2 = c.fetchone()
    realized_loss = abs(float(row2['today_loss']) if row2 and row2['today_loss'] else 0.0)

    # Latest equity from snapshot
    c.execute("SELECT total_equity FROM portfolio_snapshots ORDER BY snapshot_at DESC LIMIT 1")
    snap = c.fetchone()
    conn.close()

    equity = float(snap['total_equity']) if snap and snap['total_equity'] else 0.0

    target_pct = config.risk.daily_target_profit_pct * 100  # e.g. 1.0
    target_idr = max(
        equity * config.risk.daily_target_profit_pct,
        config.risk.daily_target_profit_min_idr,
    )

    drawdown_limit_pct = config.risk.daily_drawdown_limit * 100
    daily_drawdown_pct = (realized_loss / equity * 100) if equity > 0 else 0.0

    # Determine status
    if daily_drawdown_pct >= drawdown_limit_pct:
        status = "DRAWDOWN_LIMIT"
    elif target_idr > 0 and realized_pnl_today >= target_idr:
        status = "TARGET_MET"
    elif realized_pnl_today == 0:
        status = "NO_TRADES"
    else:
        status = "HUNTING"

    progress_pct = min(100.0, (realized_pnl_today / target_idr * 100) if target_idr > 0 else 0.0)

    return DailyTargetResponse(
        target_pct=round(target_pct, 2),
        target_idr=round(target_idr, 2),
        realized_pnl_today=round(realized_pnl_today, 2),
        progress_pct=round(progress_pct, 2),
        status=status,
        daily_drawdown_pct=round(daily_drawdown_pct, 2),
        drawdown_limit_pct=round(drawdown_limit_pct, 2),
        equity=round(equity, 2),
    )
