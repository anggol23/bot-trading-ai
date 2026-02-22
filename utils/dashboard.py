"""
CLI Dashboard - Real-time trading status display.
"""

from tabulate import tabulate
from colorama import Fore, Style, init as colorama_init
from typing import Optional

from core.entities.portfolio_summary import PortfolioSummary
from utils.logger import get_logger

logger = get_logger(__name__)
colorama_init(autoreset=True)


class Dashboard:
    """CLI dashboard for monitoring trading agent status."""

    HEADER = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗
║  🤖  AI TRADING AGENT — INDODAX           Lead Trading Strategist ║
╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

    def display(
        self,
        portfolio: PortfolioSummary,
        last_signals: dict = None,
        volume_summary: dict = None,
    ):
        """Display full dashboard."""
        print("\033[2J\033[H")  # Clear screen
        print(self.HEADER)

        self._show_portfolio(portfolio)
        self._show_positions(portfolio)

        if last_signals:
            self._show_signals(last_signals)

        if volume_summary:
            self._show_volume_activity(volume_summary)

        print(f"\n{Fore.CYAN}{'─' * 68}{Style.RESET_ALL}")
        mode = portfolio.positions[0].mode if portfolio.positions else "paper"
        mode_display = f"{Fore.YELLOW}📝 PAPER{Style.RESET_ALL}" if mode == "paper" else f"{Fore.RED}💰 LIVE{Style.RESET_ALL}"
        print(f"  Mode: {mode_display} │ Last Update: now")

    def _show_portfolio(self, portfolio: PortfolioSummary):
        """Display portfolio summary."""
        pnl_color = Fore.GREEN if portfolio.unrealized_pnl >= 0 else Fore.RED
        rpnl_color = Fore.GREEN if portfolio.realized_pnl_today >= 0 else Fore.RED
        dd_color = Fore.GREEN if portfolio.daily_drawdown_pct < portfolio.daily_drawdown_limit_pct * 0.7 else Fore.RED

        print(f"  {Fore.WHITE}{'─' * 60}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}💰 PORTFOLIO{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}{'─' * 60}{Style.RESET_ALL}")

        data = [
            ["Total Equity", f"Rp {portfolio.total_equity:>15,.0f}"],
            ["Available", f"Rp {portfolio.available_balance:>15,.0f}"],
            ["Unrealized P&L", f"{pnl_color}Rp {portfolio.unrealized_pnl:>+15,.0f}{Style.RESET_ALL}"],
            ["Realized Today", f"{rpnl_color}Rp {portfolio.realized_pnl_today:>+15,.0f}{Style.RESET_ALL}"],
            ["Open Positions", f"{portfolio.open_positions:>16d}"],
            ["Daily Drawdown", f"{dd_color}{portfolio.daily_drawdown_pct:>15.2f}% / {portfolio.daily_drawdown_limit_pct:.0f}%{Style.RESET_ALL}"],
        ]

        print(tabulate(data, tablefmt="plain", colalign=("left", "right")))

    def _show_positions(self, portfolio: PortfolioSummary):
        """Display open positions table."""
        print(f"\n  {Fore.WHITE}📊 OPEN POSITIONS ({portfolio.open_positions}){Style.RESET_ALL}")
        print(f"  {Fore.WHITE}{'─' * 60}{Style.RESET_ALL}")

        if not portfolio.positions:
            print(f"  {Fore.YELLOW}  Tidak ada posisi terbuka{Style.RESET_ALL}")
            return

        headers = ["Symbol", "Side", "Entry", "Current", "SL", "TP", "P&L", "%"]
        rows = []

        for pos in portfolio.positions:
            pnl_c = Fore.GREEN if pos.unrealized_pnl >= 0 else Fore.RED
            side_c = Fore.GREEN if pos.side == "buy" else Fore.RED
            side_sym = "🟢 BUY" if pos.side == "buy" else "🔴 SELL"

            rows.append([
                pos.symbol,
                f"{side_c}{side_sym}{Style.RESET_ALL}",
                f"{pos.entry_price:,.0f}",
                f"{pos.current_price:,.0f}",
                f"{pos.stop_loss:,.0f}",
                f"{pos.take_profit:,.0f}",
                f"{pnl_c}{pos.unrealized_pnl:+,.0f}{Style.RESET_ALL}",
                f"{pnl_c}{pos.unrealized_pnl_pct:+.2f}%{Style.RESET_ALL}",
            ])

        print(tabulate(rows, headers=headers, tablefmt="simple"))

    def _show_signals(self, signals: dict):
        """Display latest trading signals."""
        print(f"\n  {Fore.WHITE}📡 LATEST SIGNALS{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}{'─' * 60}{Style.RESET_ALL}")

        headers = ["Symbol", "Action", "Confidence", "Reason"]
        rows = []

        for symbol, signal in signals.items():
            action = signal.get("action", "HOLD")
            conf = signal.get("confidence", 0)

            action_colors = {
                "STRONG_BUY": Fore.GREEN,
                "BUY": Fore.LIGHTGREEN_EX,
                "HOLD": Fore.YELLOW,
                "SELL": Fore.LIGHTYELLOW_EX,
                "STRONG_SELL": Fore.RED,
            }
            color = action_colors.get(action, Fore.WHITE)

            # Truncate reason
            reason = signal.get("reason", "")[:50]

            rows.append([
                symbol,
                f"{color}{action}{Style.RESET_ALL}",
                f"{conf:.0%}",
                reason,
            ])

        print(tabulate(rows, headers=headers, tablefmt="simple"))

    def _show_volume_activity(self, volume_data: dict):
        """Display volume anomaly summary."""
        print(f"\n  {Fore.WHITE}📊 VOLUME & IMBALANCE ANOMALY{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}{'─' * 60}{Style.RESET_ALL}")

        headers = ["Symbol", "Flow", "Imbalance", "Intensity", "Confidence"]
        rows = []

        for symbol, data in volume_data.items():
            flow = data.get("net_flow", "NEUTRAL")
            flow_colors = {
                "ACCUMULATING": Fore.GREEN,
                "DISTRIBUTING": Fore.RED,
                "NEUTRAL": Fore.YELLOW,
            }
            color = flow_colors.get(flow, Fore.WHITE)

            rows.append([
                symbol,
                f"{color}{flow}{Style.RESET_ALL}",
                f"{data.get('imbalance_score', 0):+.3f}",
                data.get("intensity", "LOW"),
                f"{data.get('confidence', 0):.0%}",
            ])

        print(tabulate(rows, headers=headers, tablefmt="simple"))


def print_startup_banner(config):
    """Print startup banner with configuration."""
    colorama_init(autoreset=True)

    mode_str = f"{Fore.YELLOW}📝 PAPER TRADING" if config.trading.mode == "paper" \
        else f"{Fore.RED}💰 LIVE TRADING"

    print(f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║    🤖  AI TRADING AGENT v1.0                                     ║
║    📊  Platform: INDODAX                                         ║
║    🎯  Strategy: Lead Trading Strategist                         ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║    Mode:     {mode_str:<52}{Fore.CYAN}║
║    Pairs:    {Fore.WHITE}{', '.join(config.trading.pairs):<52}{Fore.CYAN}║
║    TF:       {Fore.WHITE}{config.trading.timeframe:<52}{Fore.CYAN}║
║    Risk:     {Fore.WHITE}{config.risk.risk_per_trade*100:.0f}% per position{'':<38}{Fore.CYAN}║
║    Max Pos:  {Fore.WHITE}{config.risk.max_open_positions:<52}{Fore.CYAN}║
║    DD Limit: {Fore.WHITE}{config.risk.daily_drawdown_limit*100:.0f}%{'':<49}{Fore.CYAN}║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
""")
