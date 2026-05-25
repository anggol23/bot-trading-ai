import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from presentation.api.models import (
    PortfolioSummaryResponse, PositionResponse, SignalResponse,
    VolumeAnomalyResponse, ChartDataPoint, CandleResponse,
    TradeHistoryResponse, DailyTargetResponse
)
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("SUPABASE_DB_URL", "")

def get_db_connection():
    conn = psycopg2.connect(DB_URL)
    return conn

# ──────────────────────────────── Auth Helpers ────────────────────────────────

def create_user(email: str, password_hash: str) -> int:
    conn = get_db_connection()
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    try:
        c.execute("""
            INSERT INTO users (email, password_hash, created_at)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (email, password_hash, now))
        user_id = c.fetchone()[0]
        conn.commit()
        return user_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    try:
        c.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def update_user_keys(user_id: int, api_key: str, api_secret: str):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE users 
            SET api_key = %s, api_secret = %s 
            WHERE id = %s
        """, (api_key, api_secret, user_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def get_user_keys(user_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=RealDictCursor)
    try:
        c.execute("SELECT api_key, api_secret FROM users WHERE id = %s", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ─────────────────────────── Multi-User Data Helpers ───────────────────────────

def get_portfolio_summary(user_id: int) -> PortfolioSummaryResponse:
    if not DB_URL or "project-id" in DB_URL:
        return PortfolioSummaryResponse(
            total_equity=300000.0, available_balance=300000.0, unrealized_pnl=0.0,
            realized_pnl_today=0.0, open_positions=0, daily_drawdown_pct=0.0
        )

    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Realized PnL Today (Filtered by user_id or NULL fallback)
        c.execute("""
            SELECT SUM(pnl) as today_pnl 
            FROM trades 
            WHERE status = 'closed' AND (user_id = %s OR user_id IS NULL)
            AND SUBSTRING(closed_at, 1, 10) = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
        """, (user_id,))
        row = c.fetchone()
        realized_pnl = float(row['today_pnl']) if row and row['today_pnl'] else 0.0
        
        # 2. Open Positions (Filtered by user_id or NULL fallback)
        c.execute("SELECT * FROM trades WHERE status = 'open' AND (user_id = %s OR user_id IS NULL)", (user_id,))
        open_positions = c.fetchall()
        
        # 3. Snapshot (Filtered by user_id or NULL fallback)
        c.execute("SELECT * FROM portfolio_snapshots WHERE (user_id = %s OR user_id IS NULL) ORDER BY snapshot_at DESC LIMIT 1", (user_id,))
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
    except Exception as e:
        print(f"Error fetching portfolio summary from Supabase for user {user_id}: {e}")
        
    return PortfolioSummaryResponse(
        total_equity=300000.0,
        available_balance=300000.0,
        unrealized_pnl=0.0,
        realized_pnl_today=0.0,
        open_positions=0,
        daily_drawdown_pct=0.0
    )

def get_active_positions(user_id: int) -> List[PositionResponse]:
    if not DB_URL or "project-id" in DB_URL:
        return []
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM trades WHERE status = 'open' AND (user_id = %s OR user_id IS NULL) ORDER BY opened_at DESC", (user_id,))
        rows = c.fetchall()
        conn.close()
        
        import random
        positions = []
        for r in rows:
            # For simulation, slightly randomize current price around entry price
            current_p = r['price'] * random.uniform(0.99, 1.01)
            unrealized = (current_p - r['price']) * r['amount'] if r['side'] == 'buy' else (r['price'] - current_p) * r['amount']
            unrealized_pct = (unrealized / r['cost']) * 100 if r['cost'] > 0 else 0
            
            positions.append(PositionResponse(
                id=r['id'],
                symbol=r['symbol'],
                side=r['side'],
                entry_price=r['price'],
                current_price=current_p,
                stop_loss=r['stop_loss'] if r['stop_loss'] else 0.0,
                take_profit=r['take_profit'] if r['take_profit'] else 0.0,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=unrealized_pct
            ))
        return positions
    except Exception as e:
        print(f"Error fetching active positions for user {user_id}: {e}")
        return []

def get_recent_signals(limit: int = 10) -> List[SignalResponse]:
    """Signals represent public market scan events, no user_id filtering needed."""
    if not DB_URL or "project-id" in DB_URL:
        return []
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM signals ORDER BY created_at DESC LIMIT %s", (limit,))
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
    except Exception as e:
        print(f"Error fetching signals: {e}")
        return []

def get_volume_anomalies(limit: int = 10) -> List[VolumeAnomalyResponse]:
    """Volume anomalies are public market events."""
    if not DB_URL or "project-id" in DB_URL:
        return []
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("SELECT * FROM volume_anomalies ORDER BY timestamp DESC LIMIT %s", (limit,))
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
    except Exception as e:
        print(f"Error fetching anomalies: {e}")
        return []

def get_equity_curve(user_id: int, days: int = None) -> List[ChartDataPoint]:
    if not DB_URL or "project-id" in DB_URL:
        return []
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        
        query = "SELECT snapshot_at, total_equity FROM portfolio_snapshots WHERE (user_id = %s OR user_id IS NULL)"
        params = [user_id]
        
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query += " AND snapshot_at >= %s"
            params.append(cutoff.isoformat())
            
        query += " ORDER BY snapshot_at ASC"
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        return [ChartDataPoint(
            time=r['snapshot_at'],
            value=r['total_equity']
        ) for r in rows]
    except Exception as e:
        print(f"Error fetching equity curve for user {user_id}: {e}")
        return []

def get_latest_candles(symbol: str, timeframe: str = "1h", limit: int = 100) -> List[CandleResponse]:
    """Candles represent public market data."""
    if not DB_URL or "project-id" in DB_URL:
        return []
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("""
            SELECT timestamp, open, high, low, close, volume 
            FROM candles 
            WHERE symbol = %s AND timeframe = %s
            ORDER BY timestamp DESC LIMIT %s
        """, (symbol, timeframe, limit))
        rows = c.fetchall()
        conn.close()
        
        candles = []
        for r in reversed(rows):
            row_dict = dict(r)
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
    except Exception as e:
        print(f"Error fetching candles: {e}")
        return []

def get_trade_history(user_id: int, limit: int = 50) -> List[TradeHistoryResponse]:
    if not DB_URL or "project-id" in DB_URL:
        return []
    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute("""
            SELECT id, symbol, side, price, amount, cost,
                   stop_loss, take_profit, pnl, pnl_percent,
                   status, mode, close_reason,
                   opened_at, closed_at, close_price
            FROM trades
            WHERE user_id = %s OR user_id IS NULL
            ORDER BY opened_at DESC
            LIMIT %s
        """, (user_id, limit))
        rows = c.fetchall()
        conn.close()

        result = []
        for r in rows:
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
    except Exception as e:
        print(f"Error fetching trade history for user {user_id}: {e}")
        return []

def get_daily_target_status(user_id: int) -> DailyTargetResponse:
    from config.settings import Config
    config = Config()

    if not DB_URL or "project-id" in DB_URL:
        return DailyTargetResponse(
            target_pct=1.0, target_idr=0.0, realized_pnl_today=0.0, progress_pct=0.0,
            status="NO_TRADES", daily_drawdown_pct=0.0, drawdown_limit_pct=2.5, equity=300000.0
        )

    try:
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=RealDictCursor)

        # Realized PnL today
        c.execute("""
            SELECT SUM(pnl) as today_pnl
            FROM trades
            WHERE status = 'closed' AND (user_id = %s OR user_id IS NULL)
            AND SUBSTRING(closed_at, 1, 10) = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
        """, (user_id,))
        row = c.fetchone()
        realized_pnl_today = float(row['today_pnl']) if row and row['today_pnl'] else 0.0

        # Realized losses today (for drawdown calc)
        c.execute("""
            SELECT SUM(pnl) as today_loss
            FROM trades
            WHERE status = 'closed' AND (user_id = %s OR user_id IS NULL)
            AND SUBSTRING(closed_at, 1, 10) = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
            AND pnl < 0
        """, (user_id,))
        row2 = c.fetchone()
        realized_loss = abs(float(row2['today_loss']) if row2 and row2['today_loss'] else 0.0)

        # Latest equity from snapshot
        c.execute("SELECT total_equity FROM portfolio_snapshots WHERE (user_id = %s OR user_id IS NULL) ORDER BY snapshot_at DESC LIMIT 1", (user_id,))
        snap = c.fetchone()
        conn.close()

        equity = float(snap['total_equity']) if snap and snap['total_equity'] else 0.0

        target_pct = config.risk.daily_target_profit_pct * 100
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
    except Exception as e:
        print(f"Error fetching daily target status for user {user_id}: {e}")
        return DailyTargetResponse(
            target_pct=1.0, target_idr=0.0, realized_pnl_today=0.0, progress_pct=0.0,
            status="NO_TRADES", daily_drawdown_pct=0.0, drawdown_limit_pct=2.5, equity=300000.0
        )
