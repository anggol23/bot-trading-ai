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
from use_cases.analysis.market_regime import MarketRegimeAnalyzer
from core.entities.trading_signal import TradingSignal
from use_cases.trading.risk_manager import RiskManager
from use_cases.trading.position_tracker import PositionTracker
from infrastructure.news.cryptopanic_client import CryptoPanicClient
from infrastructure.ai.llm_client import GeminiClient
from use_cases.analysis.llm_strategist import LLMStrategist
from infrastructure.notifications.telegram_bot import TelegramBot
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
        self.market_regime_analyzer = MarketRegimeAnalyzer(self.market_data, self.tech_analyzer)
        self.risk_manager = RiskManager(config, self.db)
        self.executor = OrderExecutor(config, self.market_data, self.db)
        self.position_tracker = PositionTracker(
            config, self.db, self.market_data,
            self.risk_manager, self.executor,
            self.volume_analyzer
        )
        self.dashboard = Dashboard()
        self.telegram = TelegramBot(config.telegram)

        # AI Analyst (LLM)
        self.gemini_client = GeminiClient(
            api_key=config.ai.gemini_api_key,
            model_name=config.ai.model_name
        )
        self.llm_strategist = LLMStrategist(self.gemini_client)

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
        
        # Telegram Setup
        self.telegram.register_stop_callback(self._telegram_stop_callback)
        asyncio.create_task(self.telegram.start_listening())
        await self.telegram.send_message(
            f"🚀 <b>AI Trading Agent Online</b>\n"
            f"Mode: {self.config.trading.mode.upper()}\n"
            f"Pairs: {len(self.config.trading.pairs)} active"
        )

        # Run immediately on start
        await self._run_cycle()

        # Main Asynchronous Event Loop
        analysis_interval_sec = self.config.trading.analysis_interval_minutes * 60
        position_check_interval_sec = 5 * 60
        
        last_analysis_time = time.time()
        last_position_check_time = time.time()
        last_report_date = datetime.now(timezone.utc).date()

        logger.info(
            f"📅 Scheduled: Analysis every {self.config.trading.analysis_interval_minutes} min | "
            f"Position check every 5 min"
        )

        error_count = 0
        base_backoff_sec = 2

        while self.running:
            try:
                now = time.time()
                current_date = datetime.now(timezone.utc).date()
                
                # Daily Report
                if current_date > last_report_date:
                    await self._send_daily_report()
                    last_report_date = current_date
                
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

                # Reset error count on successful loop iteration
                if error_count > 0:
                    logger.info("✅ Connection restored, resuming normal operations.")
                    error_count = 0

                await asyncio.sleep(1) # Yield control back to loop avoiding CPU hog
                
            except __import__('ccxt').NetworkError as e:
                error_count += 1
                backoff = min(base_backoff_sec ** error_count, 300) # Max 5 minutes backoff
                logger.error(f"🌐 🔌 API Connection lost: {e}")
                logger.info(f"⏳ Circuit Breaker Active: Retrying in {backoff} seconds... (Attempt {error_count})")
                await asyncio.sleep(backoff)
            except Exception as e:
                error_count += 1
                backoff = min(base_backoff_sec ** error_count, 300)
                logger.error(f"❌ Unexpected Error in Main Loop: {e}")
                logger.info(f"⏳ Circuit Breaker Active: Retrying in {backoff} seconds... (Attempt {error_count})")
                await asyncio.sleep(backoff)

        # Saat self.running = False (Signal handler triggered), jalankan cleanup
        await self._cleanup()

    async def _cleanup(self):
        """Clean up active connections gracefully before exiting."""
        logger.info("\n🧹 Membersihkan sesi dan koneksi asinkron...")
        try:
            await self.telegram.send_message("🛑 <b>Bot Offline</b>\nMemulai proses shutdown...")
            await self.telegram.close()
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
            # ──── Check Macro Market Status ────
            market_regime = await self.market_regime_analyzer.analyze()

            if self.config.trading.mode == "paper":
                today_trades = self.db.get_trades_today()
                realized_today = sum(t.get("pnl", 0) for t in today_trades if t.get("pnl") is not None)
                equity = 300_000 + realized_today
            else:
                try:
                    balance = await self.market_data.fetch_balance()
                    equity = balance.get("free", {}).get("IDR", 0)
                except Exception as e:
                    logger.warning(f"⚠️ Error fetching balance for equity: {e}")
                    equity = 0
            
            daily_target_met = self.risk_manager.check_daily_target_met(equity)
            if daily_target_met:
                logger.info("🎯 DAILY TARGET MET: Switching to strict / defensive mode")
            else:
                logger.info("🔥 DAILY TARGET NOT MET: Switching to aggressive / hunter mode")

            # ──── Step 1: Analyze All Trading Pairs Concurrently ────
            # To avoid overloading the exchange, we can batch them.
            # But ccxt async_support handles internal connection pooling and rate limiting if enabled.
            # For 100+ pairs, we should probably chunk them. But assuming ~30 liquid pairs, gather is fine.
            tasks = []
            for symbol in self.config.trading.pairs:
                tasks.append(self._analyze_pair(symbol, daily_target_met, market_regime, equity))
                
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

    async def _analyze_pair(self, symbol: str, daily_target_met: bool, market_regime: str, equity: float):
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
            tech_signals, volume_signal, sentiment_signal, daily_target_met, market_regime
        )

        # ──── AI (LLM) Strategic Audit ────
        if trading_signal.ai_decision == "AWAITING" and self.config.ai.enable_llm_audit:
            logger.info(f"🤖 Calling LLM Strategist ({self.config.ai.model_name}) for {symbol}...")
            
            # Prepare contextual data for LLM
            
            # Fetch orderbook for depth analysis
            orderbook_ratio = "N/A"
            try:
                ob = await self.market_data.fetch_order_book(symbol, limit=20)
                bids_vol = sum(amount for price, amount in ob.get('bids', []))
                asks_vol = sum(amount for price, amount in ob.get('asks', []))
                if asks_vol > 0:
                    ratio = bids_vol / asks_vol
                    if ratio > 2.0:
                        orderbook_ratio = f"{ratio:.2f} (Bids > Asks, Strong Buying Pressure or Spoofing)"
                    elif ratio < 0.5:
                        orderbook_ratio = f"{ratio:.2f} (Asks > Bids, Heavy Selling Wall)"
                    else:
                        orderbook_ratio = f"{ratio:.2f} (Balanced)"
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch orderbook for LLM Context: {e}")
            
            market_stats = {
                "technical": {tf: s.trend for tf, s in tech_signals.items()},
                "volume": volume_signal.to_dict(),
                "sentiment": sentiment_signal.get("status", "NEUTRAL"),
                "orderbook_ratio": orderbook_ratio
            }
            headlines = "\n".join(sentiment_signal.get("headlines", []))
            
            ai_result = await self.llm_strategist.analyze_signal(
                trading_signal, market_stats, headlines
            )
            
            trading_signal.ai_decision = ai_result.get("decision", "APPROVE")
            trading_signal.ai_reasoning = ai_result.get("reasoning", "No detail provided.")
            
            logger.info(f"👤 LLM Strategist Decision: {trading_signal.ai_decision}")
            logger.info(f"   Reason: {trading_signal.ai_reasoning}")
            
            if trading_signal.ai_decision == "REJECT":
                trading_signal.action = "HOLD"
                trading_signal.reason += f" | ❌ AI REJECTED: {trading_signal.ai_reasoning}"
                await self.telegram.send_message(
                    f"🚫 <b>LLM VETO: {symbol}</b>\n"
                    f"Sinyal Ditolak karena: {trading_signal.ai_reasoning}"
                )
            elif trading_signal.ai_decision == "WAIT":
                trading_signal.action = "HOLD"
                trading_signal.reason += f" | ⏳ AI WAIT: {trading_signal.ai_reasoning}"
            else:
                trading_signal.reason += f" | ✅ AI APPROVED: {trading_signal.ai_reasoning}"

        # Save signal to database
        signal_dict = trading_signal.to_dict()
        signal_dict["symbol"] = symbol
        signal_dict["timeframe"] = self.config.trading.timeframe
        signal_dict["ai_decision"] = trading_signal.ai_decision
        signal_dict["ai_reasoning"] = trading_signal.ai_reasoning
        signal_id = self.db.save_signal(signal_dict)

        self.last_signals[symbol] = signal_dict

        logger.info(
            f"📡 {symbol} → {trading_signal.action} "
            f"(confidence: {trading_signal.confidence:.0%})"
        )
        logger.info(f"   Reason: {trading_signal.reason}")

        # ──── Execute Trading Decision ────
        await self._execute_signal(symbol, trading_signal, tech_signals, signal_id, daily_target_met, market_regime, equity)

    async def _execute_signal(
        self,
        symbol: str,
        signal: TradingSignal,
        tech_signals: dict,
        signal_id: int,
        daily_target_met: bool,
        market_regime: str,
        equity: float,
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
            entry_price = ticker.get("last") or 0
        except Exception as e:
            logger.error(f"❌ Cannot get price for {symbol}: {e}")
            return

        # Guard: abort if price is still zero even after fallback
        if entry_price <= 0:
            logger.error(
                f"❌ {symbol}: entry_price={entry_price} — cannot place order with zero price. "
                f"Skipping this cycle."
            )
            return

        # Get ATR from primary timeframe
        primary_tf = list(tech_signals.keys())[0]
        atr = tech_signals[primary_tf].atr if primary_tf in tech_signals else 0

        if atr <= 0:
            # Fallback: estimate ATR as 0.5% of entry price.
            # This handles micro-price coins (e.g. PEPE in IDR) where float
            # precision shrinks the raw ATR to zero despite real price movement.
            atr_fallback = entry_price * 0.005
            logger.warning(
                f"⚠️ ATR is zero for {symbol} — using fallback ATR = 0.5% of price "
                f"({atr_fallback:,.6f} IDR). Execution will proceed with conservative SL."
            )
            atr = atr_fallback

        # Calculate order with risk management
        order_plan = self.risk_manager.calculate_order(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            atr=atr,
            equity=equity,
            market_regime=market_regime,
            daily_target_met=daily_target_met,
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
            await self.telegram.send_message(
                f"🟢 <b>NEW TRADE EXECUTED</b>\n"
                f"Symbol: <b>{symbol}</b>\n"
                f"Action: <b>{side.upper()}</b>\n"
                f"Entry Price: Rp {order_plan.entry_price:,.0f}\n"
                f"Target Proft: Rp {order_plan.take_profit:,.0f}\n"
                f"Stop Loss: Rp {order_plan.stop_loss:,.0f}\n"
                f"Alasan: {signal.reason}"
            )

    async def _check_positions(self):
        """Check open positions for SL/TP hits."""
        try:
            actions = await self.position_tracker.check_positions()
            summary = await self.position_tracker.get_portfolio_summary()
            if actions:
                for action in actions:
                    logger.trade(f"⚡ Position update: {action}")
                    if "Closed" in action:
                        await self.telegram.send_message(f"🔔 <b>POSITION CLOSED</b>\n{action}")
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

    def _telegram_stop_callback(self):
        """Callback from Telegram /stop command."""
        logger.warning("Memanggil Shutdown dari Telegram Kill Switch...")
        self.running = False
        
    async def _send_daily_report(self):
        """Send daily portfolio summary to Telegram."""
        try:
            summary = await self.position_tracker.get_portfolio_summary()
            emoji = "📈" if summary.realized_pnl_today >= 0 else "📉"
            msg = (
                f"📅 <b>DAILY REPORT</b>\n\n"
                f"Equity: Rp {summary.total_equity:,.0f}\n"
                f"Available: Rp {summary.available_balance:,.0f}\n"
                f"Open Positions: {summary.open_positions}\n"
                f"Unrealized PNL: Rp {summary.unrealized_pnl:,.0f}\n"
                f"{emoji} <b>Realized Today: Rp {summary.realized_pnl_today:,.0f}</b>\n\n"
                f"Max Drawdown: {summary.daily_drawdown_pct:.2f}%"
            )
            await self.telegram.send_message(msg)
        except Exception as e:
            logger.error(f"❌ Failed to send daily report: {e}")
            
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
