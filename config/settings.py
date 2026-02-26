"""
Configuration Management - AI Trading Agent
Loads and validates all settings from .env file.
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class IndodaxConfig:
    api_key: str = ""
    secret: str = ""


@dataclass
class VolumeAnomalyConfig:
    multiplier: float = 3.0
    min_usd_value: int = 5_000
    poll_interval_minutes: int = 10
    z_score_threshold: float = 3.0
    spoofing_window_seconds: int = 5
    spoofing_blacklist_seconds: int = 300


@dataclass
class RiskConfig:
    risk_per_trade: float = 0.02          # 2% max per position
    max_open_positions: int = 3
    daily_drawdown_limit: float = 0.05    # 5% daily max drawdown
    daily_target_profit_pct: float = 0.01  # 1% daily target profit minimum
    stop_loss_atr_multiplier: float = 1.5
    take_profit_rr_ratio: float = 2.0     # Risk:Reward = 1:2
    enable_pyramiding: bool = True
    pyramid_profit_threshold_pct: float = 5.0
    enable_volume_exhaustion: bool = True
    enable_sentiment_veto: bool = True

    # Trailing Take Profit
    trailing_tp_activation_pct: float = 0.015 # Activate trailing TP at 1.5% profit (Hard Mode)
    trailing_tp_callback_pct: float = 0.01    # Base callback 1% (Dynamic logic applies)

    # Expert Optimizations & Resilience
    enable_maker_only: bool = False  # If true, use limit orders to get Maker fees (0%)
    max_slippage_pct: float = 0.002  # Maximum allowed slippage (0.2%)


@dataclass
class NewsConfig:
    cryptopanic_api_key: str = ""


@dataclass
class TelegramConfig:
    bot_token: str = ""
    chat_id: str = ""
    enable_notifications: bool = False


@dataclass
class AIConfig:
    gemini_api_key: str = ""
    model_name: str = "gemini-1.5-flash"
    enable_llm_audit: bool = True


@dataclass
class TradingConfig:
    mode: str = "paper"                   # "paper" or "live"
    pairs: List[str] = field(default_factory=lambda: ["BTC/IDR", "ETH/IDR", "SOL/IDR", "ADA/IDR", "DOGE/IDR", "XRP/IDR", "PEPE/IDR"])
    timeframe: str = "1h"
    analysis_interval_minutes: int = 60


@dataclass
class LogConfig:
    level: str = "INFO"
    directory: str = "logs"


class Config:
    """Central configuration loaded from environment variables."""

    def __init__(self):
        self.indodax = IndodaxConfig(
            api_key=os.getenv("INDODAX_API_KEY", ""),
            secret=os.getenv("INDODAX_SECRET", ""),
        )

        self.news = NewsConfig(
            cryptopanic_api_key=os.getenv("CRYPTOPANIC_API_KEY", ""),
        )

        self.volume_anomaly = VolumeAnomalyConfig(
            multiplier=float(os.getenv("VOLUME_ANOMALY_MULTIPLIER", "3.0")),
            min_usd_value=int(os.getenv("VOLUME_ANOMALY_MIN_USD_VALUE", "5000")),
            poll_interval_minutes=int(os.getenv("VOLUME_POLL_INTERVAL_MINUTES", "10")),
            z_score_threshold=float(os.getenv("Z_SCORE_THRESHOLD", "3.0")),
            spoofing_window_seconds=int(os.getenv("SPOOFING_WINDOW_SECONDS", "5")),
            spoofing_blacklist_seconds=int(os.getenv("SPOOFING_BLACKLIST_SECONDS", "300")),
        )

        self.risk = RiskConfig(
            risk_per_trade=float(os.getenv("RISK_PER_TRADE", "0.02")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "3")),
            daily_drawdown_limit=float(os.getenv("DAILY_DRAWDOWN_LIMIT", "0.05")),
            daily_target_profit_pct=float(os.getenv("DAILY_TARGET_PROFIT", "0.01")),
            stop_loss_atr_multiplier=float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "1.5")),
            take_profit_rr_ratio=float(os.getenv("TAKE_PROFIT_RR_RATIO", "2.0")),
            enable_pyramiding=os.getenv("ENABLE_PYRAMIDING", "true").lower() == "true",
            pyramid_profit_threshold_pct=float(os.getenv("PYRAMID_PROFIT_THRESHOLD_PCT", "5.0")),
            enable_volume_exhaustion=os.getenv("ENABLE_VOLUME_EXHAUSTION", "true").lower() == "true",
            enable_sentiment_veto=os.getenv("ENABLE_SENTIMENT_VETO", "true").lower() == "true",
            trailing_tp_activation_pct=float(os.getenv("TRAILING_TP_ACTIVATION", "0.015")),
            trailing_tp_callback_pct=float(os.getenv("TRAILING_TP_CALLBACK", "0.01")),
            enable_maker_only=os.getenv("ENABLE_MAKER_ONLY", "false").lower() == "true",
            max_slippage_pct=float(os.getenv("MAX_SLIPPAGE_PCT", "0.002")),
        )

        pairs_str = os.getenv("TRADING_PAIRS", "BTC/IDR,ETH/IDR,SOL/IDR,ADA/IDR,DOGE/IDR,XRP/IDR,PEPE/IDR")
        self.trading = TradingConfig(
            mode=os.getenv("TRADING_MODE", "paper"),
            pairs=[p.strip() for p in pairs_str.split(",")],
            timeframe=os.getenv("TIMEFRAME", "1h"),
            analysis_interval_minutes=int(os.getenv("ANALYSIS_INTERVAL_MINUTES", "60")),
        )

        self.log = LogConfig(
            level=os.getenv("LOG_LEVEL", "INFO"),
            directory=os.getenv("LOG_DIR", "logs"),
        )

        self.telegram = TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            enable_notifications=os.getenv("ENABLE_TELEGRAM", "false").lower() == "true",
        )

        self.ai = AIConfig(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            enable_llm_audit=os.getenv("ENABLE_LLM_AUDIT", "true").lower() == "true",
        )

    def validate(self) -> List[str]:
        """Validate config and return list of warnings/errors."""
        issues = []

        if self.trading.mode == "live":
            if not self.indodax.api_key:
                issues.append("ERROR: INDODAX_API_KEY required for live trading")
            if not self.indodax.secret:
                issues.append("ERROR: INDODAX_SECRET required for live trading")



        if self.risk.risk_per_trade > 0.05:
            issues.append("WARNING: RISK_PER_TRADE > 5% — very aggressive risk level")

        if self.trading.timeframe not in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
            issues.append(f"WARNING: Timeframe '{self.trading.timeframe}' may not be supported")

        return issues

    def __repr__(self) -> str:
        mode_emoji = "📝" if self.trading.mode == "paper" else "💰"
        return (
            f"Config({mode_emoji} mode={self.trading.mode}, "
            f"pairs={self.trading.pairs}, "
            f"tf={self.trading.timeframe}, "
            f"risk={self.risk.risk_per_trade*100:.0f}%)"
        )
