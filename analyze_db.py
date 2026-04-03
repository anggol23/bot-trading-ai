import argparse
import sqlite3
from collections import defaultdict


def _print_section(title: str):
    print(f"\n{'=' * 12} {title} {'=' * 12}")


def _fetch_rows(conn: sqlite3.Connection, query: str, params=()):
    cursor = conn.execute(query, params)
    return cursor.fetchall()


def summarize_trades(conn: sqlite3.Connection, limit: int):
    closed_trades = _fetch_rows(
        conn,
        """
        SELECT id, symbol, side, price, close_price, pnl, pnl_percent, close_reason, opened_at, closed_at
        FROM trades
        WHERE pnl IS NOT NULL
        ORDER BY closed_at ASC
        """,
    )
    open_trades = _fetch_rows(
        conn,
        """
        SELECT id, symbol, side, price, stop_loss, take_profit, opened_at
        FROM trades
        WHERE status = 'open'
        ORDER BY opened_at ASC
        """,
    )

    _print_section("Trade Summary")
    print(f"Closed trades : {len(closed_trades)}")
    print(f"Open trades   : {len(open_trades)}")

    if not closed_trades:
        print("No closed trades found in database.")
        return

    total_pnl = sum((row[5] or 0.0) for row in closed_trades)
    wins = sum(1 for row in closed_trades if (row[5] or 0.0) > 0)
    losses = sum(1 for row in closed_trades if (row[5] or 0.0) < 0)
    avg_pnl = total_pnl / len(closed_trades)
    print(f"Total PnL     : Rp {total_pnl:,.2f}")
    print(f"Wins / Losses : {wins} / {losses}")
    print(f"Average PnL   : Rp {avg_pnl:,.2f}")

    by_symbol = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0, "losses": 0})
    by_reason = defaultdict(lambda: {"count": 0, "pnl": 0.0, "losses": 0})
    for row in closed_trades:
        pnl = row[5] or 0.0
        symbol = row[1]
        reason = row[7] or "UNKNOWN"
        by_symbol[symbol]["count"] += 1
        by_symbol[symbol]["pnl"] += pnl
        by_symbol[symbol]["wins"] += int(pnl > 0)
        by_symbol[symbol]["losses"] += int(pnl < 0)
        by_reason[reason]["count"] += 1
        by_reason[reason]["pnl"] += pnl
        by_reason[reason]["losses"] += int(pnl < 0)

    _print_section("PnL by Symbol")
    for symbol, stats in sorted(by_symbol.items(), key=lambda item: item[1]["pnl"]):
        print(
            f"{symbol:10} trades={stats['count']:2d} wins={stats['wins']:2d} "
            f"losses={stats['losses']:2d} pnl=Rp {stats['pnl']:,.2f}"
        )

    _print_section("PnL by Close Reason")
    for reason, stats in sorted(by_reason.items(), key=lambda item: item[1]["pnl"]):
        print(
            f"{reason} | trades={stats['count']} losses={stats['losses']} pnl=Rp {stats['pnl']:,.2f}"
        )

    _print_section(f"Worst {limit} Closed Trades")
    for row in sorted(closed_trades, key=lambda item: item[5] or 0.0)[:limit]:
        print(
            f"#{row[0]} {row[1]} {row[2]} pnl=Rp {(row[5] or 0.0):,.2f} "
            f"({(row[6] or 0.0):.2f}%) reason={row[7]} opened={row[8]} closed={row[9]}"
        )


def summarize_snapshots(conn: sqlite3.Connection, limit: int):
    rows = _fetch_rows(
        conn,
        """
        SELECT snapshot_at, total_equity, available_balance, unrealized_pnl, realized_pnl_today, open_positions
        FROM portfolio_snapshots
        ORDER BY snapshot_at ASC
        """,
    )

    _print_section("Portfolio Snapshots")
    print(f"Snapshots found: {len(rows)}")
    if len(rows) < 2:
        print("Not enough snapshots to analyze equity changes.")
        return

    drops = []
    previous_equity = None
    for row in rows:
        equity = row[1] or 0.0
        if previous_equity is not None:
            diff = equity - previous_equity
            drops.append((diff, row[0], equity, row[2], row[3], row[4], row[5]))
        previous_equity = equity

    for diff, snapshot_at, equity, available, unrealized, realized, open_positions in sorted(drops, key=lambda item: item[0])[:limit]:
        print(
            f"{snapshot_at} diff=Rp {diff:,.2f} equity=Rp {equity:,.2f} "
            f"available=Rp {available:,.2f} unrealized=Rp {unrealized:,.2f} "
            f"realized_today=Rp {realized:,.2f} open_positions={open_positions}"
        )


def main():
    parser = argparse.ArgumentParser(description="Analyze trading_agent.db trade and portfolio history")
    parser.add_argument("--db", default="trading_agent.db", help="Path to sqlite database")
    parser.add_argument("--limit", type=int, default=5, help="Number of worst trades and snapshot drops to show")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    try:
        summarize_trades(conn, args.limit)
        summarize_snapshots(conn, args.limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
