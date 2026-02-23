"""
AI Trading Agent — Main Orchestrator
Lead Trading Strategist focused on Crypto (Indodax).

Strategy:
- Analyze OHLCV data via ccxt + whale movement detection
- Confirm macro trend with whale accumulation before entry
- Ignore retail panic (follow smart money)
- Max 2% risk per position, mandatory stop loss
"""

import sys
import time
import asyncio
import signal
import argparse
from datetime import datetime, timezone

from config.settings import Config
from infrastructure.storage.sqlite_repository import SqliteRepository as Database
from infrastructure.exchange.indodax_client import MarketDataFetcher
from infrastructure.exchange.ccxt_executor import OrderExecutor
from use_cases.analysis.volume_tracker import VolumeTracker
from use_cases.analysis.technical import TechnicalAnalyzer
from use_cases.analysis.volume_analyzer import VolumeAnalyzer
from use_cases.analysis.signal_generator import SignalGenerator
from use_cases.analysis.omni_scanner import OmniScanner
from use_cases.analysis.sentiment_analyzer import SentimentAnalyzer
from core.entities.trading_signal import TradingSignal
from use_cases.trading.risk_manager import RiskManager
from use_cases.trading.position_tracker import PositionTracker
from infrastructure.news.cryptopanic_client import CryptoPanicClient
from utils.logger import setup_logging, get_logger
from utils.dashboard import Dashboard, print_startup_banner

logger = get_logger(__name__)


class TradingAgent:
    """
    Main AI Trading Agent orchestrator.
    
    Runs the analysis → signal → risk → execution pipeline
    on a configurable schedule (default: every 1 hour).
    """

    def __init__(self, config: Config):
        self.config = config
        self.running = False

        # Initialize all components
        self.db = Database()
        self.market_data = MarketDataFetcher(config)
        self.volume_tracker = VolumeTracker(config, self.market_data, self.db)
        self.tech_analyzer = TechnicalAnalyzer()
        self.volume_analyzer = VolumeAnalyzer(config, self.db)
        self.signal_generator = SignalGenerator()
        self.omni_scanner = OmniScanner(config, self.market_data)
        self.news_client = CryptoPanicClient(config)
        self.sentiment_analyzer = SentimentAnalyzer(config, self.news_client)
        self.risk_manager = RiskManager(config, self.db)
        self.executor = OrderExecutor(config, self.market_data, self.db)
        self.position_tracker = PositionTracker(
            config, self.db, self.market_data,
            self.risk_manager, self.executor,
            self.volume_analyzer
        )
        self.dashboard = Dashboard()

        # State
        self.last_signals = {}
        self.last_volume_data = {}

    async def start(self):
        """Start the trading agent."""
        print_startup_banner(self.config)

        # Validate config
        issues = self.config.validate()
        for issue in issues:
            if issue.startswith("ERROR"):
                logger.error(issue)
                sys.exit(1)
            else:
                logger.warning(issue)

        # Validate trading pairs (Now using OmniScanner for async resolution)
        try:
            valid_pairs = await self.omni_scanner.get_liquid_pairs()
            if not valid_pairs:
                logger.error("❌ Tidak ada trading pairs yang valid atau liquid!")
                sys.exit(1)
            self.config.trading.pairs = valid_pairs
            logger.info(f"✅ Trading pairs aktif (Liquid): {len(valid_pairs)} markets")
        except Exception as e:
            logger.warning(f"⚠️ Could not validate pairs: {e}")
            logger.info("Using configured pairs as-is")

        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self.running = True
        logger.info("🚀 AI Trading Agent started!")

        # Run immediately on start
        await self._run_cycle()

        # Main Asynchronous Event Loop
        analysis_interval_sec = self.config.trading.analysis_interval_minutes * 60
        position_check_interval_sec = 5 * 60
        
        last_analysis_time = time.time()
        last_position_check_time = time.time()

        logger.info(
            f"📅 Scheduled: Analysis every {self.config.trading.analysis_interval_minutes} min | "
            f"Position check every 5 min"
        )

        while self.running:
            now = time.time()
            
            # Position Check Loop
            if now - last_position_check_time >= position_check_interval_sec:
                await self._check_positions()
                last_position_check_time = now
                
            # Full Analysis Cycle Loop
            if now - last_analysis_time >= analysis_interval_sec:
                # Refresh liquid pairs periodically (in case market shifts)
                logger.info("📡 Running Omni-Scanner to refresh liquid pairs...")
                self.config.trading.pairs = await self.omni_scanner.get_liquid_pairs()
                await self._run_cycle()
                last_analysis_time = now

            await asyncio.sleep(1) # Yield control back to loop avoiding CPU hog

        # Saat self.running = False (Signal handler triggered), jalankan cleanup
        await self._cleanup()

    async def _cleanup(self):
        """Clean up active connections gracefully before exiting."""
        logger.info("\n🧹 Membersihkan sesi dan koneksi asinkron...")
        try:
            if hasattr(self, 'market_data') and hasattr(self.market_data, 'close'):
                await self.market_data.close()
            if hasattr(self, 'news_client') and hasattr(self.news_client, 'close'):
                await self.news_client.close()
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
            
        # Terakhir baru matikan DB
        if hasattr(self, 'db') and hasattr(self.db, 'close'):
            self.db.close()
        logger.info("👋 Sesi ditutup. Bot Offline.")

    async def _run_cycle(self):
        """Run one complete analysis → signal → execution cycle for all pairs concurrently."""
        cycle_start = datetime.now(timezone.utc)
        logger.info(f"\n{'═' * 60}")
        logger.info(f"🔄 Analysis Cycle Start: {cycle_start.isoformat()}")
        logger.info(f"{'═' * 60}")

        try:
            # ──── Step 1: Analyze All Trading Pairs Concurrently ────
            # To avoid overloading the exchange, we can batch them.
            # But ccxt async_support handles internal connection pooling and rate limiting if enabled.
            # For 100+ pairs, we should probably chunk them. But assuming ~30 liquid pairs, gather is fine.
            tasks = []
            for symbol in self.config.trading.pairs:
                tasks.append(self._analyze_pair(symbol))
                
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for symbol, res in zip(self.config.trading.pairs, results):
                if isinstance(res, Exception):
                     logger.error(f"❌ Error analyzing {symbol}: {res}")

            # ──── Step 3: Display Dashboard ────
            await self._display_dashboard()

            duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(f"✅ Analysis cycle complete in {duration:.1f}s")

        except Exception as e:
            logger.error(f"❌ Fatal error in analysis cycle: {e}")

    async def _analyze_pair(self, symbol: str):
        """Analyze a single trading pair and execute if signal is strong."""
        logger.info(f"\n{'─' * 40}")
        logger.info(f"📊 Analyzing: {symbol}")
        logger.info(f"{'─' * 40}")

        # ──── Fetch OHLCV Data ────
        try:
            ohlcv_data = await self.market_data.fetch_multi_timeframe(
                symbol, ["1h", "4h"]
            )
        except Exception as e:
            logger.error(f"❌ Failed to fetch OHLCV for {symbol}: {e}")
            return

        # Save candles to database
        for tf, df in ohlcv_data.items():
            if not df.empty:
                candles = df.reset_index()[
                    ["timestamp", "open", "high", "low", "close", "volume"]
                ].values.tolist()
                self.db.save_candles(symbol, tf, candles)

        # ──── Technical Analysis (multi-timeframe) ────
        tech_signals = {}
        for tf, df in ohlcv_data.items():
            if not df.empty:
                tech = self.tech_analyzer.analyze(df, symbol, tf)
                if tech:
                    tech_signals[tf] = tech

        if not tech_signals:
            logger.warning(f"⚠️ No technical signals for {symbol}")
            return

        # ──── Volume & Imbalance Analysis ────
        # scan for large trades and orderbook walls (saves to DB)
        await self.volume_tracker.scan_anomalies(symbol)

        # Generate volume signal from recent DB events
        volume_signal = self.volume_analyzer.analyze(symbol)
        
        self.last_volume_data[symbol] = volume_signal.to_dict()

        # ──── Sentimen & News Analysis (Fundamental) ────
        sentiment_signal = await self.sentiment_analyzer.analyze_sentiment(symbol)
        
        # ──── Generate Combined Signal (Multi-TF) ────
        trading_signal = self.signal_generator.generate_multi_timeframe(
            tech_signals, volume_signal, sentiment_signal
        )

        # Save signal to database
        signal_dict = trading_signal.to_dict()
        signal_dict["symbol"] = symbol
        signal_dict["timeframe"] = self.config.trading.timeframe
        signal_id = self.db.save_signal(signal_dict)

        self.last_signals[symbol] = signal_dict

        logger.info(
            f"📡 {symbol} → {trading_signal.action} "
            f"(confidence: {trading_signal.confidence:.0%})"
        )
        logger.info(f"   Reason: {trading_signal.reason}")

        # ──── Execute Trading Decision ────
        await self._execute_signal(symbol, trading_signal, tech_signals, signal_id)

    async def _execute_signal(
        self,
        symbol: str,
        signal: TradingSignal,
        tech_signals: dict,
        signal_id: int,
    ):
        """Execute trading decision based on signal."""

        # Check open positions for this symbol
        open_trades = self.db.get_open_trades(symbol)

        # Handle SELL signals as Close operations only (Spot Market Enforcement)
        if signal.action in ("STRONG_SELL", "SELL"):
            if not open_trades:
                logger.info(f"📊 {symbol}: HOLD — Ignoring SELL signal (No active position to close on Spot Market)")
                return
            
            # We have open BUY positions, let's close them
            # Get current price
            try:
                ticker = await self.market_data.fetch_ticker(symbol)
                current_price = ticker["last"]
            except Exception as e:
                logger.error(f"❌ Cannot get price to close {symbol}: {e}")
                return

            for trade in open_trades:
                if trade["side"] == "buy":
                    reason = f"SIGNAL: {signal.action} (Confidence: {signal.confidence:.0%})"
                    await self.executor.close_position(trade, current_price, reason)
            return

        # Handle BUY signals
        if signal.action in ("STRONG_BUY", "BUY"):
            side = "buy"
        else:
            logger.info(f"📊 {symbol}: HOLD — No action taken")
            return

        # Get current price and ATR
        try:
            ticker = await self.market_data.fetch_ticker(symbol)
            entry_price = ticker["last"]
        except Exception as e:
            logger.error(f"❌ Cannot get price for {symbol}: {e}")
            return

        # Get ATR from primary timeframe
        primary_tf = list(tech_signals.keys())[0]
        atr = tech_signals[primary_tf].atr if primary_tf in tech_signals else 0

        if atr <= 0:
            logger.warning(f"⚠️ ATR is zero for {symbol} — cannot calculate stop loss")
            return

        # Get equity
        if self.config.trading.mode == "paper":
            equity = 300_000
        else:
            try:
                balance = await self.market_data.fetch_balance()
                equity = balance.get("free", {}).get("IDR", 0)
            except Exception:
                equity = 0

        # Calculate order with risk management
        order_plan = self.risk_manager.calculate_order(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            atr=atr,
            equity=equity,
        )

        if not order_plan.approved:
            logger.warning(
                f"🚫 {symbol}: Order rejected — {order_plan.rejection_reason}"
            )
            return

        # Add signal reference
        trade = await self.executor.execute(order_plan)

        if trade:
            # Update signal_id in trade
            cursor = self.db.conn.cursor()
            cursor.execute(
                "UPDATE trades SET signal_id = ? WHERE id = ?",
                (signal_id, trade["id"])
            )
            self.db.conn.commit()

            logger.trade(
                f"🎯 Trade executed for {symbol}: {side.upper()} | "
                f"Entry: {order_plan.entry_price:,.0f} | "
                f"SL: {order_plan.stop_loss:,.0f} | "
                f"TP: {order_plan.take_profit:,.0f} | "
                f"Risk: {order_plan.risk_amount:,.0f} IDR"
            )

    async def _check_positions(self):
        """Check open positions for SL/TP hits."""
        try:
            actions = await self.position_tracker.check_positions()
            summary = await self.position_tracker.get_portfolio_summary()
            if actions:
                for action in actions:
                    logger.trade(f"⚡ Position update: {action}")
        except Exception as e:
            logger.error(f"❌ Error checking positions: {e}")

    async def _display_dashboard(self):
        """Display the CLI dashboard."""
        try:
            portfolio = await self.position_tracker.get_portfolio_summary()
            self.dashboard.display(
                portfolio=portfolio,
                last_signals=self.last_signals,
                volume_summary=self.last_volume_data,
            )
        except Exception as e:
            logger.warning(f"⚠️ Dashboard display error: {e}")

    def _shutdown(self, signum, frame):
        """Graceful shutdown handler."""
        logger.info("\n🛑 Sinyal Terminasi diterima (Shutting down AI Trading Agent)...")
        self.running = False
        # Membiarkan asyncio event loop selesai natural untuk memanggil _cleanup()

def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="🤖 AI Trading Agent — Indodax Platform"
    )
    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default=None,
        help="Trading mode (overrides .env)"
    )
    parser.add_argument(
        "--pairs",
        type=str,
        default=None,
        help="Trading pairs, comma-separated (overrides .env)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default=None,
        help="Primary timeframe (overrides .env)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Analysis interval in minutes (overrides .env)"
    )

    args = parser.parse_args()

    # Load config
    config = Config()

    # Apply CLI overrides
    if args.mode:
        config.trading.mode = args.mode
    if args.pairs:
        config.trading.pairs = [p.strip() for p in args.pairs.split(",")]
    if args.timeframe:
        config.trading.timeframe = args.timeframe
    if args.interval:
        config.trading.analysis_interval_minutes = args.interval

    # Setup logging
    setup_logging(config.log.level, config.log.directory)

    # Start agent
    agent = TradingAgent(config)
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        logger.info("Shutdown by user.")


if __name__ == "__main__":
    main()
