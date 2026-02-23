import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any
from presentation.api.models import PortfolioSummaryResponse, PositionResponse, SignalResponse, VolumeAnomalyResponse, ChartDataPoint, CandleResponse

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
        timestamp=r['created_at']
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

def get_equity_curve() -> List[ChartDataPoint]:
    conn = get_db_connection()
    c = conn.cursor()
    # Assuming the main loop records equity periodically
    c.execute("SELECT snapshot_at, total_equity FROM portfolio_snapshots ORDER BY snapshot_at ASC")
    rows = c.fetchall()
    conn.close()
    
    return [ChartDataPoint(
        time=r['snapshot_at'].split('.')[0].replace('T', ' '),
        value=r['total_equity']
    ) for r in rows]

def get_latest_candles(symbol: str, timeframe: str = "15m", limit: int = 100) -> List[CandleResponse]:
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
